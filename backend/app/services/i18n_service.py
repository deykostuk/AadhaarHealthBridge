import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "locales")

SUPPORTED_LANGUAGES = [
    {"code": "en", "label": "English", "native": "English"},
    {"code": "hi", "label": "Hindi", "native": "हिन्दी"},
    {"code": "bn", "label": "Bengali", "native": "বাংলা"},
    {"code": "ta", "label": "Tamil", "native": "தமிழ்"},
    {"code": "te", "label": "Telugu", "native": "తెలుగు"},
    {"code": "mr", "label": "Marathi", "native": "मराठी"}
]


class I18nService:
    """
    Modular Server-Side Internationalization Framework.
    Loads and caches locale JSON dictionaries, resolves Accept-Language headers,
    and performs variable interpolation and fallback lookups.
    """

    def __init__(self, locales_dir: str = LOCALES_DIR):
        self.locales_dir = locales_dir
        self._cache: Dict[str, Dict[str, str]] = {}
        self._load_all_locales()

    def _load_all_locales(self):
        """Preloads all supported JSON dictionaries into memory."""
        for lang in SUPPORTED_LANGUAGES:
            code = lang["code"]
            file_path = os.path.join(self.locales_dir, f"{code}.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self._cache[code] = json.load(f)
                except Exception as e:
                    logger.error(f"[I18nService] Failed to load locale {code}: {e}")
                    self._cache[code] = {}
            else:
                self._cache[code] = {}

    def get_supported_languages(self) -> List[Dict[str, str]]:
        """Returns metadata list of all supported languages."""
        return SUPPORTED_LANGUAGES

    def get_locale_dictionary(self, lang: str = "en") -> Dict[str, str]:
        """Returns the dictionary for the given language code, falling back to English."""
        normalized = lang.lower().split("-")[0].split("_")[0]
        if normalized in self._cache and self._cache[normalized]:
            return self._cache[normalized]
        return self._cache.get("en", {})

    def resolve_language_from_header(self, accept_language: Optional[str]) -> str:
        """Parses the HTTP Accept-Language header and determines best match."""
        if not accept_language:
            return "en"

        supported_codes = {l["code"] for l in SUPPORTED_LANGUAGES}
        for item in accept_language.split(","):
            part = item.split(";")[0].strip().lower()
            code = part.split("-")[0]
            if code in supported_codes:
                return code
        return "en"

    def translate(self, key: str, lang: str = "en", **kwargs) -> str:
        """
        Translates a given translation key into the target language with variable interpolation.
        Falls back to English or the key name if missing.
        """
        normalized = lang.lower().split("-")[0].split("_")[0]
        dict_data = self._cache.get(normalized, {})
        text = dict_data.get(key) or self._cache.get("en", {}).get(key, key)

        if kwargs:
            for k, v in kwargs.items():
                text = text.replace(f"{{{k}}}", str(v))

        return text

    def t(self, key: str, lang: str = "en", **kwargs) -> str:
        """Alias for translate."""
        return self.translate(key, lang=lang, **kwargs)


# Global Singleton
i18n_service = I18nService()
