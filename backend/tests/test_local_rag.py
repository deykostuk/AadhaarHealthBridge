import pytest
import os
from app.models.patient import User, VaultProfile, Document
from app.services.semantic_service import generate_local_embedding, _chunk_text, index_document, semantic_query
from app.services.chat_service import ChatService

def test_local_embedding_generation():
    text1 = "Patient diagnosed with Type 2 Diabetes Mellitus."
    text2 = "Patient diagnosed with Type 2 Diabetes Mellitus."
    text3 = "Normal kidney function with creatinine 0.9 mg/dL."

    # 1. Deterministic vector size
    vec1 = generate_local_embedding(text1, dim=1536)
    assert len(vec1) == 1536
    assert isinstance(vec1[0], float)

    # 2. Deterministic reproducibility
    vec2 = generate_local_embedding(text2, dim=1536)
    assert vec1 == vec2

    # 3. Semantic differentiation
    vec3 = generate_local_embedding(text3, dim=1536)
    assert vec1 != vec3


def test_sliding_window_chunking():
    sample_text = (
        "Patient presented with persistent fever and dry cough. "
        "Laboratory investigations revealed normal Hemoglobin and elevated CRP. "
        "Prescribed Azithromycin 500mg once daily for 5 days. "
        "Follow-up scheduled after one week."
    )

    chunks = _chunk_text(sample_text, chunk_size=80, overlap=20)
    assert len(chunks) >= 2
    assert "Patient presented" in chunks[0]


def test_local_chroma_indexing_and_vault_isolation(tmp_path):
    test_chroma_dir = str(tmp_path / "test_local_chroma")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("CHROMA_DIR", test_chroma_dir)
        mp.setenv("RAG_MODE", "local")

        # Index document for Vault 1
        success_v1 = index_document(
            vault_id=101,
            document_id=1,
            text="Prescription: Take Metformin 500mg twice daily with meals.",
            file_name="diabetes_rx.pdf"
        )
        assert success_v1 is True

        # Index document for Vault 2
        success_v2 = index_document(
            vault_id=202,
            document_id=2,
            text="Radiology Report: Chest X-ray clear. No active pulmonary lesions.",
            file_name="chest_xray.pdf"
        )
        assert success_v2 is True

        # Query Vault 1
        results_v1 = semantic_query(vault_id=101, query="Metformin dosage")
        assert len(results_v1) >= 1
        assert "Metformin" in results_v1[0]["document"]

        # Ensure Vault 1 query does not return Vault 2 documents
        assert "Chest X-ray" not in results_v1[0]["document"]


def test_local_rag_chat_execution(db, tmp_path):
    test_chroma_dir = str(tmp_path / "test_chat_chroma")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("CHROMA_DIR", test_chroma_dir)
        mp.setenv("RAG_MODE", "local")

        user = User(username="local_rag_user", password_hash="hash")
        db.add(user)
        db.commit()

        vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Arjun Roy")
        db.add(vault)
        db.commit()

        doc = Document(
            vault_id=vault.id,
            file_name="discharge_summary.pdf",
            file_path="uploads/discharge.pdf",
            ocr_text="Discharge Instructions: Avoid heavy lifting for 2 weeks. Take Paracetamol for pain."
        )
        db.add(doc)
        db.commit()

        # Index in Local ChromaDB
        index_document(vault_id=vault.id, document_id=doc.id, text=doc.ocr_text, file_name=doc.file_name)

        chat_service = ChatService(db)
        res = chat_service.process_chat_query(vault_id=vault.id, query="What are my discharge instructions?")

        assert res["answer"] is not None
        assert "Local RAG" in res["ai_source"] or "Ollama" in res["ai_source"]
        assert len(res["sources"]) >= 1
        assert res["sources"][0]["file_name"] == "discharge_summary.pdf"


def test_sentence_transformer_manager():
    from app.services.semantic_service import SentenceTransformerManager
    
    mgr = SentenceTransformerManager.get_instance()
    texts = [
        "Patient fasting blood glucose is 95 mg/dL.",
        "Kidney profile creatinine level is within normal limit."
    ]
    
    embeddings = mgr.encode(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 384  # Standard 384-dimensional Sentence Transformer vector
    assert isinstance(embeddings[0][0], float)

