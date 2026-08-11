import os
import logging
import requests
from typing import Optional, List, Dict, Any

from config import settings

logger = logging.getLogger(__name__)

class OllamaService:
    """
    Local LLM Engine service communicating directly with on-device Ollama.
    Supports:
    - /api/tags: Probing daemon health and listing locally pulled models
    - /api/generate: Generating focused clinical prompt completions
    - /api/chat: Multi-turn clinical reasoning with role messages
    - Automatic fallback resilience when Ollama is offline
    """

    def __init__(
        self,
        host: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        self.host = host or os.environ.get("OLLAMA_HOST") or getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        self.default_model = default_model or os.environ.get("OLLAMA_MODEL") or getattr(settings, "OLLAMA_MODEL", "gemma2:2b")
        self.timeout = timeout or getattr(settings, "OLLAMA_TIMEOUT", 15)

    def check_health(self) -> Dict[str, Any]:
        """Probes the Ollama daemon and returns status and available models."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return {
                    "status": "online",
                    "host": self.host,
                    "default_model": self.default_model,
                    "available_models": models,
                    "model_ready": any(self.default_model in m for m in models)
                }
        except Exception as e:
            logger.debug(f"Ollama health check failed: {e}")

        return {
            "status": "offline",
            "host": self.host,
            "default_model": self.default_model,
            "available_models": [],
            "model_ready": False
        }

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> Optional[str]:
        """Executes a single prompt completion via /api/generate."""
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            logger.warning(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.debug(f"Ollama generate request failed: {e}")

        return None

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> Optional[str]:
        """Executes a multi-turn chat completion via /api/chat."""
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            if resp.status_code == 200:
                msg = resp.json().get("message", {})
                return msg.get("content", "").strip()
            logger.warning(f"Ollama chat returned HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.debug(f"Ollama chat request failed: {e}")

        return None

    def summarize_medical_document(self, ocr_text: str, model: Optional[str] = None) -> str:
        """Generates a concise clinical summary for an ingested medical report."""
        if not ocr_text or len(ocr_text.strip()) < 20:
            return "No readable text extracted from document."

        system_prompt = (
            "You are a clinical AI specialist. Provide a 2-3 sentence executive medical summary "
            "highlighting diagnoses, abnormal lab values, key medications, or critical doctor recommendations. "
            "Do not add conversational filler."
        )
        prompt = f"Medical Document Content:\n{ocr_text[:3000]}\n\nExecutive Clinical Summary:"

        summary = self.generate(prompt=prompt, system_prompt=system_prompt, model=model, temperature=0.1)
        if summary:
            return summary

        # Deterministic fallback summary
        lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        return " | ".join(lines[:3])[:300]


# Singleton Instance
ollama_service = OllamaService()
