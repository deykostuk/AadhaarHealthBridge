import pytest
from app.services.i18n_service import I18nService, i18n_service

def test_supported_languages_list():
    languages = i18n_service.get_supported_languages()
    codes = [l["code"] for l in languages]
    assert "en" in codes
    assert "hi" in codes
    assert "bn" in codes
    assert "ta" in codes
    assert "te" in codes
    assert "mr" in codes


def test_locale_dictionary_integrity():
    for code in ["en", "hi", "bn", "ta", "te", "mr"]:
        dictionary = i18n_service.get_locale_dictionary(code)
        assert isinstance(dictionary, dict)
        assert len(dictionary) >= 20
        assert "app.name" in dictionary
        assert "auth.title" in dictionary
        assert "vault.export_fhir" in dictionary


def test_server_side_translation_and_interpolation():
    service = I18nService()
    
    # 1. English translation
    en_app = service.translate("app.name", lang="en")
    assert en_app == "Aadhaar Health Bridge"

    # 2. Hindi translation
    hi_app = service.translate("app.name", lang="hi")
    assert "आधार" in hi_app

    # 3. Bengali translation
    bn_app = service.translate("app.name", lang="bn")
    assert "আধার" in bn_app

    # 4. Fallback on missing key
    fallback = service.translate("non_existent_key_xyz", lang="hi")
    assert fallback == "non_existent_key_xyz"


def test_resolve_language_from_header():
    assert i18n_service.resolve_language_from_header("hi-IN,hi;q=0.9,en;q=0.8") == "hi"
    assert i18n_service.resolve_language_from_header("bn-BD,bn;q=0.9") == "bn"
    assert i18n_service.resolve_language_from_header("ta-IN,ta;q=0.9") == "ta"
    assert i18n_service.resolve_language_from_header("fr-FR,fr;q=0.9") == "en"  # fallback


def test_locales_api_endpoints(client):
    # 1. List locales
    res_list = client.get("/api/v1/locales")
    assert res_list.status_code == 200
    languages = res_list.json()
    assert len(languages) >= 6

    # 2. Get English locale dictionary
    res_en = client.get("/api/v1/locales/en")
    assert res_en.status_code == 200
    en_dict = res_en.json()
    assert en_dict["app.name"] == "Aadhaar Health Bridge"

    # 3. Get Hindi locale dictionary
    res_hi = client.get("/api/v1/locales/hi")
    assert res_hi.status_code == 200
    hi_dict = res_hi.json()
    assert "आधार" in hi_dict["app.name"]
