import pytest
import os
from unittest.mock import patch, MagicMock
from app.models.patient import User, VaultProfile
from app.services.chat_service import ChatService
from app.services.semantic_service import _embed_texts
from config import settings

def test_ai_cost_guardrail_blocks_cloud_apis_by_default(db):
    user = User(username="cost_guard_user", password_hash="hash")
    db.add(user)
    db.commit()

    vault = VaultProfile(owner_user_id=user.id, relation="Self", full_name="Cost Guardrail Patient")
    db.add(vault)
    db.commit()

    chat_service = ChatService(db)

    # Simulate environment where external cloud API keys are present, but ALLOW_EXTERNAL_AI_APIS is False
    with patch.dict(os.environ, {
        "ALLOW_EXTERNAL_AI_APIS": "false",
        "AI_API_MODE": "local",
        "XAI_API_KEY": "xai-dummy-paid-key",
        "GROQ_API_KEY": "gsk-dummy-paid-key",
        "OPENAI_API_KEY": "sk-dummy-paid-key"
    }):
        # Mock Ollama as offline to see if it falls back locally or attempts paid APIs
        with patch("app.services.ollama_service.ollama_service.generate", return_value=None):
            with patch("openai.OpenAI") as mock_openai:
                result = chat_service.process_chat_query(
                    vault_id=vault.id,
                    query="What is normal fasting blood sugar?",
                    custom_context="[report.pdf] Blood sugar is 90 mg/dL."
                )

                # 1. Assert external paid OpenAI / Grok / Groq client was NEVER invoked
                assert mock_openai.call_count == 0

                # 2. Assert local deterministic synthesizer answered with $0 cost
                assert result["answer"] is not None
                assert "Local RAG Engine (On-Device)" in result["ai_source"]


def test_zero_cost_local_embeddings():
    # Verify embeddings are computed purely locally without touching OpenAI
    with patch.dict(os.environ, {
        "ALLOW_EXTERNAL_AI_APIS": "false",
        "OPENAI_API_KEY": "sk-dummy-paid-key"
    }):
        with patch("openai.OpenAI") as mock_openai:
            vecs = _embed_texts(["Patient presented with mild fever."])
            assert len(vecs) == 1
            assert len(vecs[0]) == 384
            # External OpenAI client must never be instantiated
            assert mock_openai.call_count == 0
