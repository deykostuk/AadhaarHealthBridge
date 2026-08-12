import pytest
from app.models.patient import User, VaultProfile, Document, DocumentEmbedding
from app.services.vector_store_service import (
    ChromaVectorStore,
    PgVectorStore,
    VectorStoreFactory,
    cosine_similarity
)
from app.services.semantic_service import _embed_texts

def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-5
    assert abs(cosine_similarity(v1, v3) - 0.0) < 1e-5


def test_chroma_vector_store_crud(tmp_path):
    store = ChromaVectorStore(chroma_dir=str(tmp_path / "chroma_crud"))
    vault_id = 999
    doc_id = 55
    chunks = ["Fasting blood sugar is 110 mg/dL.", "HbA1c level is 6.2% indicating pre-diabetes."]
    embeddings = _embed_texts(chunks)

    # 1. Index Chunks
    success = store.index_chunks(
        vault_id=vault_id,
        document_id=doc_id,
        chunks=chunks,
        embeddings=embeddings,
        file_name="lab_report.pdf"
    )
    assert success is True

    # 2. Search
    query_emb = _embed_texts(["blood sugar test"])[0]
    results = store.search(vault_id=vault_id, query_embedding=query_emb, top_k=2)
    assert len(results) >= 1
    assert "blood sugar" in results[0]["document"].lower() or "hba1c" in results[0]["document"].lower()

    # 3. Delete
    del_ok = store.delete_document(vault_id=vault_id, document_id=doc_id)
    assert del_ok is True


def test_pgvector_store_crud(db):
    user = User(username="pgv_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="PgVector Patient")
    db.add(vault)
    db.commit()

    doc = Document(
        vault_id=vault.id,
        file_name="renal_profile.pdf",
        file_path="uploads/renal.pdf",
        ocr_text="Serum Creatinine is 1.1 mg/dL. Blood Urea Nitrogen is 18 mg/dL."
    )
    db.add(doc)
    db.commit()

    store = PgVectorStore(db)
    chunks = ["Serum Creatinine is 1.1 mg/dL.", "Blood Urea Nitrogen is 18 mg/dL."]
    embeddings = _embed_texts(chunks)

    # 1. Index Chunks in database
    success = store.index_chunks(
        vault_id=vault.id,
        document_id=doc.id,
        chunks=chunks,
        embeddings=embeddings,
        file_name=doc.file_name
    )
    assert success is True

    # Verify rows in DB table
    rows = db.query(DocumentEmbedding).filter(DocumentEmbedding.vault_id == vault.id).all()
    assert len(rows) == 2

    # 2. Search with cosine distance
    query_emb = _embed_texts(["creatinine level"])[0]
    results = store.search(vault_id=vault.id, query_embedding=query_emb, top_k=2)
    assert len(results) == 2
    assert "Creatinine" in results[0]["document"] or "Urea" in results[0]["document"]

    # 3. Delete document embeddings
    del_ok = store.delete_document(vault_id=vault.id, document_id=doc.id)
    assert del_ok is True
    rows_after = db.query(DocumentEmbedding).filter(DocumentEmbedding.vault_id == vault.id).all()
    assert len(rows_after) == 0


def test_vector_store_factory(db):
    # Default without params
    s1 = VectorStoreFactory.get_vector_store()
    assert isinstance(s1, ChromaVectorStore)

    # With DB session (SQLite/MVP fallback)
    s2 = VectorStoreFactory.get_vector_store(db)
    assert isinstance(s2, (ChromaVectorStore, PgVectorStore))
