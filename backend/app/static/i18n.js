/**
 * Aadhaar Health Bridge - Modular Localized i18n Framework
 * Supports: English (en), Hindi (hi), Bengali (bn), Tamil (ta), Telugu (te), Marathi (mr)
 * Loads JSON locale files asynchronously with in-memory caching and DOM auto-binding.
 */

window.AHB_I18N = (function () {
  const SUPPORTED_LANGUAGES = [
    { code: 'en', label: 'EN', native: 'English', full: 'English' },
    { code: 'hi', label: 'हि', native: 'हिन्दी', full: 'Hindi' },
    { code: 'bn', label: 'বাং', native: 'বাংলা', full: 'Bengali' },
    { code: 'ta', label: 'தமி', native: 'தமிழ்', full: 'Tamil' },
    { code: 'te', label: 'తెలు', native: 'తెలుగు', full: 'Telugu' },
    { code: 'mr', label: 'मरा', native: 'मराठी', full: 'Marathi' }
  ];

  let currentLang = localStorage.getItem('hb_lang') || 'en';
  const localeCache = {};

  // Fallback inline strings for critical app boot
  const defaultEnglish = {
    'app.name': 'Aadhaar Health Bridge',
    'app.tagline': 'Universal Digital Health Vault & AI Clinical Assistant',
    'nav.overview': 'Overview & Vitals',
    'nav.biomarkers': 'Lab Biomarkers',
    'nav.documents': 'Medical Records',
    'nav.chat': 'Local RAG AI',
    'nav.audit': 'Audit Trail',
    'nav.emergency': 'Emergency QR',
    'nav.logout': 'Logout'
  };

  localeCache['en'] = defaultEnglish;

  async function loadLocaleDictionary(lang) {
    if (localeCache[lang] && Object.keys(localeCache[lang]).length > 10) {
      return localeCache[lang];
    }

    try {
      const resp = await fetch(`/static/locales/${lang}.json`);
      if (resp.ok) {
        const data = await resp.json();
        localeCache[lang] = data;
        return data;
      }
    } catch (e) {
      console.warn(`[i18n] Could not load /static/locales/${lang}.json, trying API:`, e);
    }

    try {
      const apiResp = await fetch(`/api/v1/locales/${lang}`);
      if (apiResp.ok) {
        const apiData = await apiResp.json();
        localeCache[lang] = apiData;
        return apiData;
      }
    } catch (e) {
      console.warn(`[i18n] Could not fetch locale from API for ${lang}:`, e);
    }

    return localeCache['en'] || defaultEnglish;
  }

  function t(key, params = {}) {
    const dict = localeCache[currentLang] || localeCache['en'] || defaultEnglish;
    let text = dict[key] || localeCache['en']?.[key] || key;

    if (params && typeof params === 'object') {
      Object.keys(params).forEach((paramKey) => {
        text = text.replace(new RegExp(`{${paramKey}}`, 'g'), params[paramKey]);
      });
    }

    return text;
  }

  async function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('hb_lang', lang);
    await loadLocaleDictionary(lang);
    applyTranslations();
    document.dispatchEvent(new CustomEvent('ahb:language-changed', { detail: { lang } }));
  }

  function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      const translated = t(key);
      if (el.tagName === 'INPUT' && el.hasAttribute('placeholder')) {
        el.placeholder = translated;
      } else {
        el.textContent = translated;
      }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.placeholder = t(key);
    });

    document.documentElement.lang = currentLang;
    document.querySelectorAll('.ahb-lang-btn').forEach((btn) => {
      btn.classList.toggle('active-lang', btn.dataset.lang === currentLang);
    });
  }

  function injectLanguageSelector() {
    if (document.getElementById('ahb-lang-wrapper')) return;

    const wrapper = document.createElement('div');
    wrapper.id = 'ahb-lang-wrapper';
    wrapper.style.cssText = 'display:inline-flex;align-items:center;gap:4px;background:rgba(15,23,42,0.7);border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:3px 6px;margin-right:8px;backdrop-filter:blur(10px);';

    SUPPORTED_LANGUAGES.forEach((lang) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ahb-lang-btn';
      btn.dataset.lang = lang.code;
      btn.title = `${lang.full} (${lang.native})`;
      btn.style.cssText = 'padding:3px 7px;border-radius:6px;border:none;font-size:11px;font-weight:700;cursor:pointer;background:transparent;color:#94a3b8;font-family:inherit;transition:all 0.2s ease;';
      btn.textContent = lang.label;

      btn.addEventListener('click', async () => {
        await setLanguage(lang.code);
      });

      if (lang.code === currentLang) {
        btn.style.background = '#0f766e';
        btn.style.color = '#ffffff';
      }

      wrapper.appendChild(btn);
    });

    const navActions = document.querySelector('.nav-actions');
    if (navActions) {
      navActions.insertBefore(wrapper, navActions.firstChild);
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await loadLocaleDictionary(currentLang);
    injectLanguageSelector();
    applyTranslations();
  });

  return {
    t,
    setLanguage,
    applyTranslations,
    getSupportedLanguages: () => SUPPORTED_LANGUAGES,
    getCurrentLanguage: () => currentLang
  };
})();
