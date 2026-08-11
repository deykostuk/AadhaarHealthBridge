from fastapi import APIRouter, Header, HTTPException
from typing import Optional, List, Dict, Any

from app.services.i18n_service import i18n_service

router = APIRouter(prefix="/locales", tags=["Internationalization"])


@router.get("", summary="List Supported Locales & Languages")
def list_locales():
    """Returns list of supported Indian languages and metadata."""
    return i18n_service.get_supported_languages()


@router.get("/{lang}", summary="Get Complete Locale JSON Dictionary")
def get_locale_dictionary(lang: str):
    """Returns the full key-value translation dictionary for a specific language code."""
    dictionary = i18n_service.get_locale_dictionary(lang)
    if not dictionary:
        raise HTTPException(status_code=404, detail=f"Locale '{lang}' not found.")
    return dictionary
