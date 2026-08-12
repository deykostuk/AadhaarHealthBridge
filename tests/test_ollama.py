import pytest
from unittest.mock import patch, MagicMock
from app.services.ollama_service import OllamaService

def test_ollama_health_check_online():
    service = OllamaService(host="http://localhost:11434", default_model="gemma2:2b")
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [{"name": "gemma2:2b:latest"}, {"name": "llama3.2:3b:latest"}]
        }
        mock_get.return_value = mock_resp

        health = service.check_health()
        assert health["status"] == "online"
        assert health["model_ready"] is True
        assert len(health["available_models"]) == 2


def test_ollama_health_check_offline():
    service = OllamaService(host="http://localhost:11434", default_model="gemma2:2b")
    with patch("requests.get", side_effect=Exception("Connection refused")):
        health = service.check_health()
        assert health["status"] == "offline"
        assert health["model_ready"] is False


def test_ollama_generate_completion():
    service = OllamaService(host="http://localhost:11434", default_model="gemma2:2b")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Fasting blood sugar is within normal reference range."}
        mock_post.return_value = mock_resp

        res = service.generate(prompt="Explain glucose level 95 mg/dL")
        assert res == "Fasting blood sugar is within normal reference range."


def test_ollama_chat_completion():
    service = OllamaService(host="http://localhost:11434", default_model="gemma2:2b")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"role": "assistant", "content": "Creatinine level of 1.0 mg/dL is normal."}
        }
        mock_post.return_value = mock_resp

        messages = [
            {"role": "system", "content": "You are a clinical AI assistant."},
            {"role": "user", "content": "Is creatinine 1.0 mg/dL normal?"}
        ]
        res = service.chat(messages=messages)
        assert res == "Creatinine level of 1.0 mg/dL is normal."


def test_ollama_document_summary():
    service = OllamaService(host="http://localhost:11434", default_model="gemma2:2b")
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "Patient underwent routine health check. All vital signs and metabolic markers are normal."
        }
        mock_post.return_value = mock_resp

        ocr_text = "Comprehensive Metabolic Panel: Glucose 92 mg/dL. Creatinine 0.9 mg/dL. Calcium 9.5 mg/dL."
        summary = service.summarize_medical_document(ocr_text=ocr_text)
        assert "routine health check" in summary
