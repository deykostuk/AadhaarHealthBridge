import os
import json
import math
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from config import settings
from app.models.patient import DocumentEmbedding

logger = logging.getLogger(__name__)

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two float vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return dot / (norm_a * norm_b)


class BaseVectorStore(ABC):
    """Abstract interface for pluggable vector stores."""

    @abstractmethod
    def index_chunks(
        self,
        vault_id: int,
        document_id: int,
        chunks: List[str],
        embeddings: List[List[float]],
        file_name: Optional[str] = None
    ) -> bool:
        """Indexes text chunks with their vector embeddings."""
        pass

    @abstractmethod
    def search(
        self,
        vault_id: int,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Searches for top_k most similar chunks for a vault."""
        pass

    @abstractmethod
    def delete_document(self, vault_id: int, document_id: int) -> bool:
        """Deletes all vector embeddings for a specific document."""
        pass


class ChromaVectorStore(BaseVectorStore):
    """
    MVP & Local Development Vector Store.
    Operates using local embedded ChromaDB instances in chroma_db/ partitioned by vault.
    """

    def __init__(self, chroma_dir: Optional[str] = None):
        self.chroma_dir = chroma_dir or os.environ.get("CHROMA_DIR") or os.path.join(os.getcwd(), "chroma_db")
        self._client = None

    def _get_client(self):
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.chroma_dir)
        return self._client

    def _get_collection(self, vault_id: int):
        client = self._get_client()
        collection_name = f"vault_{vault_id}"
        return client.get_or_create_collection(name=collection_name)

    def index_chunks(
        self,
        vault_id: int,
        document_id: int,
        chunks: List[str],
        embeddings: List[List[float]],
        file_name: Optional[str] = None
    ) -> bool:
        try:
            collection = self._get_collection(vault_id)
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]
            metadatas = [
                {"doc_id": document_id, "file_name": file_name or "document", "chunk_index": i}
                for i in range(len(chunks))
            ]
            collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=chunks)
            logger.info(f"[ChromaVectorStore] Indexed {len(chunks)} chunks for doc {document_id} in vault {vault_id}")
            return True
        except Exception as e:
            logger.warning(f"[ChromaVectorStore] Indexing failed: {e}")
            return False

    def search(
        self,
        vault_id: int,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            collection = self._get_collection(vault_id)
            res = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            results = []
            if res and res.get("ids") and len(res["ids"]) > 0:
                for i in range(len(res["ids"][0])):
                    results.append({
                        "id": res["ids"][0][i],
                        "document": res["documents"][0][i],
                        "metadata": res["metadatas"][0][i],
                        "distance": res["distances"][0][i]
                    })
            return results
        except Exception as e:
            logger.warning(f"[ChromaVectorStore] Search failed: {e}")
            return []

    def delete_document(self, vault_id: int, document_id: int) -> bool:
        try:
            collection = self._get_collection(vault_id)
            collection.delete(where={"doc_id": document_id})
            return True
        except Exception as e:
            logger.warning(f"[ChromaVectorStore] Delete failed: {e}")
            return False


class PgVectorStore(BaseVectorStore):
    """
    Production Enterprise Vector Store.
    Stores embeddings in PostgreSQL table document_embeddings and computes cosine similarity.
    """

    def __init__(self, db: Session):
        self.db = db

    def index_chunks(
        self,
        vault_id: int,
        document_id: int,
        chunks: List[str],
        embeddings: List[List[float]],
        file_name: Optional[str] = None
    ) -> bool:
        try:
            # Clear existing chunks for document
            self.db.query(DocumentEmbedding).filter(
                DocumentEmbedding.vault_id == vault_id,
                DocumentEmbedding.document_id == document_id
            ).delete()

            # Insert new chunk embeddings
            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                rec = DocumentEmbedding(
                    vault_id=vault_id,
                    document_id=document_id,
                    chunk_index=idx,
                    chunk_text=chunk,
                    file_name=file_name or "document",
                    embedding_json=json.dumps(emb)
                )
                self.db.add(rec)

            self.db.commit()
            logger.info(f"[PgVectorStore] Indexed {len(chunks)} chunks for doc {document_id} in vault {vault_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.exception(f"[PgVectorStore] Indexing failed: {e}")
            return False

    def search(
        self,
        vault_id: int,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            records = self.db.query(DocumentEmbedding).filter(
                DocumentEmbedding.vault_id == vault_id
            ).all()

            scored = []
            for r in records:
                try:
                    vec = json.loads(r.embedding_json)
                    sim = cosine_similarity(query_embedding, vec)
                    distance = 1.0 - sim
                    scored.append((distance, r))
                except Exception:
                    continue

            scored.sort(key=lambda x: x[0])
            top = scored[:top_k]

            return [
                {
                    "id": f"{r.document_id}_{r.chunk_index}",
                    "document": r.chunk_text,
                    "metadata": {
                        "doc_id": r.document_id,
                        "file_name": r.file_name,
                        "chunk_index": r.chunk_index
                    },
                    "distance": dist
                }
                for dist, r in top
            ]
        except Exception as e:
            logger.exception(f"[PgVectorStore] Search failed: {e}")
            return []

    def delete_document(self, vault_id: int, document_id: int) -> bool:
        try:
            self.db.query(DocumentEmbedding).filter(
                DocumentEmbedding.vault_id == vault_id,
                DocumentEmbedding.document_id == document_id
            ).delete()
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.exception(f"[PgVectorStore] Delete failed: {e}")
            return False


class VectorStoreFactory:
    """Factory to provide the appropriate Vector Store implementation."""

    @staticmethod
    def get_vector_store(db: Optional[Session] = None) -> BaseVectorStore:
        configured_store = getattr(settings, "VECTOR_STORE", "auto").lower()

        # Explicit configuration
        if configured_store == "pgvector":
            if db is not None:
                return PgVectorStore(db)
            logger.warning("PgVectorStore requested without DB session, falling back to ChromaVectorStore.")
            return ChromaVectorStore()

        if configured_store == "chroma":
            return ChromaVectorStore()

        # Auto detection: If running in production with PostgreSQL, use PgVectorStore
        if db is not None:
            bind = db.get_bind()
            dialect = bind.dialect.name if bind else ""
            if dialect == "postgresql" or getattr(settings, "ENVIRONMENT", "development") == "production":
                return PgVectorStore(db)

        # Default to ChromaVectorStore for MVP/Dev
        return ChromaVectorStore()
