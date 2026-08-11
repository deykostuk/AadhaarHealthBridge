import os
import re
import logging
import requests
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.patient import Document
from app.services import semantic_service
from app.services.metric_service import HealthMetricService

logger = logging.getLogger(__name__)

class ChatService:
    """Modular service orchestrating RAG context retrieval and tiered LLM fallback answering."""

    def __init__(self, db: Session):
        self.db = db
        self.metric_service = HealthMetricService(db)

    def process_chat_query(
        self,
        vault_id: int,
        query: str,
        document_id: Optional[int] = None,
        custom_context: Optional[str] = None,
        client_sources: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Main chat orchestration pipeline."""
        query = query.strip()
        if not query:
            return {"answer": "Empty question.", "sources": [], "ai_source": ""}

        # 1. AI Security: Prompt Injection Defense Shield
        from app.services.ai_security_service import ai_security_service
        is_injection, injection_reason = ai_security_service.inspect_prompt_injection(query)
        if is_injection:
            return {
                "answer": "I cannot process this request because it violates clinical safety and security policies.",
                "sources": [],
                "source_attributions": [],
                "ai_source": "AI Security Shield (Blocked)",
                "security_alert": injection_reason
            }

        # 2. Check if structured biomarker question
        if semantic_service.is_trend_query(query):
            trend_resp = self.metric_service.build_trend_response_for_query(vault_id, query)
            if trend_resp:
                return {
                    "answer": trend_resp["answer"],
                    "sources": [],
                    "source_attributions": [],
                    "ai_source": "Structured Biomarker Engine",
                    "metric_response": trend_resp
                }

        # 3. Context Retrieval
        if custom_context:
            context = custom_context
            top_chunks = client_sources or []
        else:
            top_chunks, context = self._retrieve_relevant_context(vault_id, query, document_id)

        # 4. XML-Fenced Structural Prompt Formulation
        prompt = self._build_prompt(context, query)

        # 5. Multi-LLM Tiered Execution
        answer, ai_source = self._execute_tiered_llm(prompt, context, query, top_chunks)

        # 6. Source Attribution & Grounding Verification
        source_attributions = ai_security_service.verify_source_attribution(answer, top_chunks)

        sources = [
            {"doc_id": c.get("doc_id"), "file_name": c.get("file_name", "document"), "excerpt": c.get("text", "")[:300]}
            for c in top_chunks
        ]

        return {
            "answer": answer,
            "sources": sources,
            "source_attributions": source_attributions,
            "ai_source": ai_source
        }

    def _retrieve_relevant_context(self, vault_id: int, query: str, document_id: Optional[int]) -> Tuple[List[Dict[str, Any]], str]:
        """Retrieves semantic chunks from Chroma with keyword matching fallback."""
        docs_q = self.db.query(Document).filter(Document.vault_id == vault_id)
        if document_id:
            docs_q = docs_q.filter(Document.id == document_id)
        docs = docs_q.all()

        chunks = []
        for d in docs:
            if not d.ocr_text:
                continue
            parts = re.split(r"\n{2,}|\r\n{2,}", d.ocr_text)
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                for i in range(0, len(p), 1000):
                    chunks.append({"doc_id": d.id, "file_name": d.file_name, "text": p[i:i+1000]})

        top_chunks = []
        try:
            sem_results = semantic_service.semantic_query(vault_id, query, top_k=5)
            for r in sem_results:
                md = r.get('metadata', {}) or {}
                top_chunks.append({
                    'doc_id': md.get('doc_id'),
                    'file_name': md.get('file_name'),
                    'text': r.get('document')
                })
        except Exception:
            top_chunks = []

        if not top_chunks:
            top_chunks = self._simple_retrieve(query, chunks, top_n=5)

        context = "\n\n".join([f"[{c.get('file_name')}] {c.get('text')}" for c in top_chunks])
        return top_chunks, context

    @staticmethod
    def _simple_retrieve(query: str, chunks: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
        """Fallback keyword overlap retrieval."""
        if not query or not chunks:
            return []
        q_tokens = re.findall(r"\w+", query.lower())
        synonym_groups = [
            {"sugar", "glucose", "hba1c", "diabetes", "fbs", "rbs", "sugars"},
            {"kidney", "creatinine", "urea", "uric", "renal", "kidneys", "gfr", "egfr", "uric_acid"},
            {"blood", "hemoglobin", "hb", "hgb", "urea", "sugar", "pressure"},
            {"anemia", "hemoglobin", "hb", "hgb", "rbc", "iron"},
            {"heart", "pressure", "bp", "pulse", "cholesterol", "hypertension"},
        ]
        expanded_tokens = list(q_tokens)
        for token in q_tokens:
            for group in synonym_groups:
                if token in group:
                    expanded_tokens.extend(group)

        scores = []
        for c in chunks:
            text = c.get("text", "").lower()
            score = sum(text.count(t) for t in expanded_tokens)
            scores.append((score, c))
        scores.sort(key=lambda x: x[0], reverse=True)
        results = [c for s, c in scores if s > 0]
        return results[:top_n] if results else chunks[:top_n]

    @staticmethod
    def _build_prompt(context: str, query: str) -> str:
        from app.services.ai_security_service import AISecurityService
        system_rules = (
            "You are a precise and concise clinical document assistant. Analyze the provided medical context and answer the user's question directly, clearly, and as briefly as possible. Avoid introductory fluff and unnecessary explanations.\n"
            "Rules:\n"
            "1. Keep answers short, direct, and focused only on what the user asked.\n"
            "2. If the user asks about abnormalities, specific parameters, or if values are normal, list the values as a clean Markdown bulleted list where EACH item is on a new, separate line. Include current value and reference interval.\n"
            "3. Cite the source document next to the value in brackets like [filename.pdf].\n"
            "4. Always start each bullet point on its own line using standard Markdown list syntax (* Test Name: Value (Normal Range: X - Y) [source.pdf])."
        )
        return AISecurityService.build_secure_fenced_prompt(system_instructions=system_rules, context=context, user_query=query)


    def _execute_tiered_llm(self, prompt: str, context: str, query: str, top_chunks: List[Dict[str, Any]]) -> Tuple[str, str]:
        """Executes Local RAG pipeline (Ollama local inference + on-device fallback) with optional cloud tiers."""
        from config import settings
        answer = ""
        ai_source = ""

        # 1. Local LLM: Execute via OllamaService
        from app.services.ollama_service import ollama_service
        gen_answer = ollama_service.generate(prompt=prompt, temperature=0.2)
        if gen_answer:
            answer = gen_answer
            ai_source = f"Local Ollama ({ollama_service.default_model})"

        # 2. If Cloud RAG mode is explicitly enabled AND external paid APIs are allowed
        if not answer and getattr(settings, "ALLOW_EXTERNAL_AI_APIS", False) and getattr(settings, "RAG_MODE", "local") == "cloud":
            xai_key = os.environ.get("XAI_API_KEY")
            groq_key = os.environ.get("GROQ_API_KEY")

            if groq_key and not answer:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=groq_key.strip(), base_url="https://api.groq.com/openai/v1")
                    resp = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=300,
                        temperature=0.2
                    )
                    answer = resp.choices[0].message.content.strip()
                    ai_source = "Groq (llama-3.1-8b-instant)"
                except Exception:
                    pass

        # 3. Local RAG On-Device Deterministic Synthesizer Fallback
        if not answer:
            ai_source = "Local RAG Engine (On-Device)"
            if top_chunks:
                snippets = ["**Local RAG Clinical Context:**\n"]
                for c in top_chunks:
                    txt = c.get("text", "").strip()
                    if len(txt) > 500:
                        txt = txt[:500].rsplit(" ", 1)[0] + "..."
                    snippets.append(f"• From **{c.get('file_name', 'document')}**:\n  \"{txt}\"")
                answer = "\n\n".join(snippets)
            else:
                answer = "No relevant clinical records or document excerpts found matching the query."

        return answer, ai_source

