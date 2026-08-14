/**
 * Aadhaar Health Bridge - Client-Side PWA Single Page Application (app.js)
 * Interacts asynchronously with RESTful /api/v1/ endpoints.
 * Provides offline caching, biometric/emergency pass generation, local RAG AI chat,
 * drag-and-drop report processing, and multilingual translation support.
 */

// Determine API base endpoint (uses current host/port by default or explicit window.AHB_API_BASE_URL)
const BACKEND_BASE = window.AHB_API_BASE_URL || "";
const API_BASE = `${BACKEND_BASE}/api/v1`;

/**
 * LocalVaultDB: Client-Side IndexedDB Storage Engine for Hybrid Architecture
 * - Stores full PDF documents as binary Blobs directly on the user's phone.
 * - Enables 100% offline document viewing, downloading, and WhatsApp sharing.
 * - Works synchronously with the encrypted cloud API for cross-device & emergency recovery.
 */
class LocalVaultDB {
  constructor() {
    this.dbName = 'ahb_local_vault_db';
    this.version = 1;
    this.db = null;
    this.initPromise = this.init();
  }

  async init() {
    if (typeof window === 'undefined' || !window.indexedDB) return null;
    return new Promise((resolve) => {
      const req = indexedDB.open(this.dbName, this.version);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains('documents')) {
          const store = db.createObjectStore('documents', { keyPath: 'docId' });
          store.createIndex('vaultId', 'vaultId', { unique: false });
        }
      };
      req.onsuccess = (e) => {
        this.db = e.target.result;
        resolve(this.db);
      };
      req.onerror = (e) => {
        console.warn('[IndexedDB] Could not open local vault DB:', e);
        resolve(null);
      };
    });
  }

  async cacheDocumentBlob(docId, vaultId, blob, meta = {}) {
    await this.initPromise;
    if (!this.db) return false;
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction('documents', 'readwrite');
        const store = tx.objectStore('documents');
        store.put({
          docId: String(docId),
          vaultId: String(vaultId),
          blob: blob,
          fileName: meta.fileName || 'report.pdf',
          category: meta.category || 'Diagnostic Report',
          cachedAt: new Date().toISOString(),
          sizeBytes: blob.size || 0
        });
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => resolve(false);
      } catch (err) {
        console.warn('[IndexedDB] Cache put failed:', err);
        resolve(false);
      }
    });
  }

  async getCachedDocumentBlob(docId) {
    await this.initPromise;
    if (!this.db) return null;
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction('documents', 'readonly');
        const store = tx.objectStore('documents');
        const req = store.get(String(docId));
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => resolve(null);
      } catch (err) {
        resolve(null);
      }
    });
  }

  async deleteCachedDocument(docId) {
    await this.initPromise;
    if (!this.db) return false;
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction('documents', 'readwrite');
        const store = tx.objectStore('documents');
        store.delete(String(docId));
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => resolve(false);
      } catch (err) {
        resolve(false);
      }
    });
  }

  async getAllCachedDocs(vaultId) {
    await this.initPromise;
    if (!this.db) return [];
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction('documents', 'readonly');
        const store = tx.objectStore('documents');
        const index = store.index('vaultId');
        const req = index.getAll(String(vaultId));
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => resolve([]);
      } catch (err) {
        resolve([]);
      }
    });
  }

  async clearAll() {
    await this.initPromise;
    if (!this.db) return false;
    return new Promise((resolve) => {
      try {
        const tx = this.db.transaction('documents', 'readwrite');
        const store = tx.objectStore('documents');
        store.clear();
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => resolve(false);
      } catch (err) {
        resolve(false);
      }
    });
  }
}

class HealthBridgePWA {
  constructor() {
    this.token = localStorage.getItem('hb_token') || sessionStorage.getItem('hb_token') || null;
    this.currentUser = null;
    this.vaults = [];
    this.activeVaultId = null;
    this.activeVault = null;
    this.localDB = new LocalVaultDB();
    this.cachedDocIds = new Set();
    this.qrMode = 'crypto';
    this.cameraFacing = 'environment';
    this.cameraStream = null;
    this.isScanning = false;
    this.signedQrPayload = null;

    this.init();
  }

  async init() {
    this.bindEvents();
    this.registerServiceWorker();
    this.handleInstallPrompt();
    this.initNetworkMonitoring();

    if (this.token) {
      await this.loadUserProfile();
    } else {
      this.showView('auth');
    }
  }

  // 1. Toast Notification System
  showToast(message, type = 'info') {
    const container = document.getElementById('ahb-toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `ahb-toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '⚠️';

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // 2. Network Status Monitoring
  initNetworkMonitoring() {
    const statusEl = document.getElementById('network-status');
    const textEl = document.getElementById('network-text');

    const updateStatus = () => {
      const isOnline = navigator.onLine;
      if (statusEl && textEl) {
        if (isOnline) {
          statusEl.className = 'network-status-indicator online';
          textEl.textContent = 'Online';
        } else {
          statusEl.className = 'network-status-indicator offline';
          textEl.textContent = 'Offline';
          this.showToast('Network disconnected. Offline Emergency mode active.', 'error');
        }
      }
    };

    window.addEventListener('online', () => {
      updateStatus();
      this.showToast('Network connection restored.', 'success');
    });
    window.addEventListener('offline', () => {
      updateStatus();
    });

    updateStatus();
  }

  // 3. Service Worker Registration
  registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
          .then((reg) => console.log('[PWA] Service Worker registered with scope:', reg.scope))
          .catch((err) => console.warn('[PWA] Service Worker registration failed:', err));
      });
    }
  }

  // 4. PWA Install Prompt Listener
  handleInstallPrompt() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.deferredInstallPrompt = e;
      const installBtn = document.getElementById('pwa-install-btn');
      if (installBtn) {
        installBtn.style.display = 'inline-flex';
        installBtn.classList.add('pulse-glow');
      }
    });

    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn) {
      installBtn.addEventListener('click', async () => {
        if (this.deferredInstallPrompt) {
          this.deferredInstallPrompt.prompt();
          const { outcome } = await this.deferredInstallPrompt.userChoice;
          console.log('[PWA] User response to install prompt:', outcome);
          this.deferredInstallPrompt = null;
          installBtn.style.display = 'none';
        }
      });
    }
  }

  // 5. Event Listeners & Handlers
  bindEvents() {
    // Auth Forms
    const loginForm = document.getElementById('login-form');
    if (loginForm) loginForm.addEventListener('submit', (e) => this.handleLogin(e));

    const signupForm = document.getElementById('signup-form');
    if (signupForm) signupForm.addEventListener('submit', (e) => this.handleSignup(e));

    // Nav Switcher
    document.querySelectorAll('[data-tab]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const tab = e.currentTarget.getAttribute('data-tab');
        this.switchTab(tab);
      });
    });

    // Vault Selector
    const vaultSelect = document.getElementById('vault-select');
    if (vaultSelect) {
      vaultSelect.addEventListener('change', (e) => {
        this.activeVaultId = parseInt(e.target.value, 10);
        this.loadActiveVaultData();
        this.syncCustomVaultDropdown();
      });
    }

    // Custom dropdown trigger toggle and click outside logic
    const trigger = document.getElementById('vault-dropdown-trigger');
    const container = document.getElementById('vault-dropdown-container');
    const options = document.getElementById('vault-dropdown-options');
    if (trigger && options) {
      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        if (this._closeBiomarkerDateDropdown) {
          this._closeBiomarkerDateDropdown();
        }
        const profileOptions = document.getElementById('profile-dropdown-options');
        if (profileOptions) profileOptions.style.display = 'none';
        document.getElementById('header-profile-menu')?.classList.remove('open');

        const isOpen = options.style.display === 'block';
        options.style.display = isOpen ? 'none' : 'block';
        container?.classList.toggle('open', !isOpen);
      });
      document.addEventListener('click', () => {
        options.style.display = 'none';
        container?.classList.remove('open');
      });
    }

    // Profile dropdown trigger toggle and click outside logic
    const profileTrigger = document.getElementById('profile-dropdown-trigger');
    const profileContainer = document.getElementById('header-profile-menu');
    const profileOptions = document.getElementById('profile-dropdown-options');
    if (profileTrigger && profileOptions) {
      profileTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        if (this._closeBiomarkerDateDropdown) {
          this._closeBiomarkerDateDropdown();
        }
        const vaultOptions = document.getElementById('vault-dropdown-options');
        if (vaultOptions) vaultOptions.style.display = 'none';
        document.getElementById('vault-dropdown-container')?.classList.remove('open');

        const isOpen = profileOptions.style.display === 'block';
        profileOptions.style.display = isOpen ? 'none' : 'block';
        profileContainer?.classList.toggle('open', !isOpen);
      });
      document.addEventListener('click', () => {
        profileOptions.style.display = 'none';
        profileContainer?.classList.remove('open');
      });
    }

    // Chat Query Form
    const chatForm = document.getElementById('chat-form');
    if (chatForm) chatForm.addEventListener('submit', (e) => this.handleChatSubmit(e));

    // Document Upload Form
    const docForm = document.getElementById('upload-doc-form');
    if (docForm) docForm.addEventListener('submit', (e) => this.handleDocUpload(e));

    // Drag and Drop
    this.initDragAndDrop();

    // Biomarker Search
    const searchInput = document.getElementById('biomarker-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => this.filterBiomarkers(e.target.value));
    }

    // Emergency Toggle
    const emergencyToggle = document.getElementById('emergency-toggle');
    if (emergencyToggle) {
      emergencyToggle.addEventListener('change', (e) => this.handleEmergencyToggle(e.target.checked));
    }

    // Add Family Member Form
    const addMemberForm = document.getElementById('add-member-form');
    if (addMemberForm) {
      addMemberForm.addEventListener('submit', (e) => this.handleAddFamilyMember(e));
    }

    // Edit Profile Form
    const editProfileForm = document.getElementById('edit-profile-form');
    if (editProfileForm) {
      editProfileForm.addEventListener('submit', (e) => this.handleProfileUpdate(e));
    }

    // Dynamic Language Switch Listener
    document.addEventListener('ahb:language-changed', () => {
      if (window.HealthBridgeI18n) {
        window.HealthBridgeI18n.applyTranslations();
      }
      this.populateVaultSelector();
      if (this.activeVault) {
        this.renderVaultOverview(this.activeVault);
      }
      if (this.allMetrics) {
        this.renderBiomarkers(this.allMetrics);
      }
      if (this.documents) {
        this.renderFiles(this.documents);
      }
      if (this.auditLogs) {
        this.renderAuditTrail(this.auditLogs);
      }
    });

    // Logout
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) logoutBtn.addEventListener('click', () => this.handleLogout());

    // Export FHIR Bundle
    const exportFhirBtn = document.getElementById('export-fhir-btn');
    if (exportFhirBtn) exportFhirBtn.addEventListener('click', () => this.exportFHIRBundle());
  }

  // 6. Drag and Drop Zone
  initDragAndDrop() {
    const dropzone = document.getElementById('doc-dropzone');
    const fileInput = document.getElementById('doc-file-input');
    if (!dropzone || !fileInput) return;

    ['dragenter', 'dragover'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        this.showToast(`Selected: ${e.dataTransfer.files[0].name}`, 'info');
      }
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        this.showToast(`Selected: ${fileInput.files[0].name}`, 'info');
      }
    });
  }

  // 7. API Request Helper with JWT Auth
  async apiRequest(endpoint, options = {}) {
    const headers = {
      ...options.headers
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const resp = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
      });

      const data = await resp.json().catch(() => ({}));

      if (!resp.ok) {
        if (resp.status === 401 && !endpoint.includes('/auth/login')) {
          this.handleLogout();
          throw new Error('Session expired. Please log in again.');
        }
        const errorMsg = (typeof data.detail === 'object' ? data.detail?.message : data.detail) || data.message || `HTTP ${resp.status}`;
        throw new Error(errorMsg || 'Request failed.');
      }

      return data;
    } catch (err) {
      console.error(`[API Error ${endpoint}]:`, err);
      throw err;
    }
  }

  // 8. Auth Handlers
  async handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    if (errorEl) errorEl.textContent = '';

    try {
      const res = await this.apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      });

      this.token = res.access_token || res.token;
      localStorage.setItem('hb_token', this.token);
      this.showToast('Successfully authenticated!', 'success');
      await this.loadUserProfile();
    } catch (err) {
      if (errorEl) errorEl.textContent = err.message || 'Invalid credentials.';
      this.showToast(err.message || 'Login failed', 'error');
    }
  }

  async handleSignup(e) {
    e.preventDefault();
    const username = document.getElementById('signup-username').value.trim();
    const password = document.getElementById('signup-password').value;
    const errorEl = document.getElementById('signup-error');
    if (errorEl) errorEl.textContent = '';

    try {
      await this.apiRequest('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      });

      this.showToast('Account created! Authenticating...', 'success');

      // Auto login after signup
      const loginRes = await this.apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      });
      this.token = loginRes.access_token || loginRes.token;
      localStorage.setItem('hb_token', this.token);
      await this.loadUserProfile();
    } catch (err) {
      if (errorEl) errorEl.textContent = err.message || 'Signup failed.';
      this.showToast(err.message || 'Signup failed', 'error');
    }
  }

  handleLogout() {
    this.token = null;
    this.currentUser = null;
    this.vaults = [];
    this.activeVaultId = null;
    this.activeVault = null;
    this.selectedBiomarkerDate = null;
    this.sortedBiomarkerDates = [];
    this.biomarkerDatesMap = {};
    if (this._closeBiomarkerDateDropdown) {
      this._closeBiomarkerDateDropdown();
    }
    localStorage.removeItem('hb_token');
    sessionStorage.removeItem('hb_token');

    // Secure Service Worker Cache Purge
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ action: 'PURGE_SECURE_CACHE' });
    }

    this.showView('auth');
    this.showToast('Logged out securely.', 'info');
  }

  // 9. Profile & Vault Loading
  async loadUserProfile() {
    try {
      this.currentUser = await this.apiRequest('/auth/me');
      const userDisplay = document.getElementById('user-display-name');
      if (userDisplay && this.currentUser) {
        userDisplay.textContent = `👤 ${this.currentUser.username || 'User'}`;
      }

      const profileDisplay = document.getElementById('profile-display-name');
      if (profileDisplay && this.currentUser) {
        profileDisplay.textContent = this.currentUser.username || 'User';
      }

      this.vaults = await this.apiRequest('/vaults');

      if (this.vaults.length > 0) {
        this.activeVaultId = this.vaults[0].id;
      }

      this.populateVaultSelector();
      this.showView('app');
      await this.loadActiveVaultData();
      this.switchTab('documents');
    } catch (err) {
      console.warn('Failed to load profile:', err);
      this.handleLogout();
    }
  }

  populateVaultSelector() {
    const selector = document.getElementById('vault-select');
    if (!selector) return;
    selector.innerHTML = '';
    const translateRel = (rel) => (window.AHB_I18N ? window.AHB_I18N.translateRelation(rel) : rel);
    this.vaults.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = `${v.full_name || 'Patient'} (${translateRel(v.relation || 'Self')})`;
      selector.appendChild(opt);
    });
    if (this.activeVaultId) selector.value = this.activeVaultId;

    // Sync to custom dropdown UI
    this.syncCustomVaultDropdown();
  }

  syncCustomVaultDropdown() {
    const selector = document.getElementById('vault-select');
    const selectedText = document.getElementById('vault-dropdown-selected-text');
    const optionsContainer = document.getElementById('vault-dropdown-options');
    if (!selector || !selectedText || !optionsContainer) return;

    optionsContainer.innerHTML = '';
    
    // Set text on trigger button
    const selectedOpt = selector.options[selector.selectedIndex];
    if (selectedOpt) {
      selectedText.textContent = selectedOpt.textContent;
      
      // Update top-left profile display name
      const profileDisplay = document.getElementById('profile-display-name');
      if (profileDisplay) {
        profileDisplay.textContent = selectedOpt.textContent.split(' (')[0];
      }
    }

    // Build custom dropdown options list
    Array.from(selector.options).forEach((opt) => {
      const div = document.createElement('div');
      div.className = `custom-dropdown-option${opt.value == selector.value ? ' selected' : ''}`;
      div.textContent = opt.textContent;
      div.dataset.value = opt.value;
      div.addEventListener('click', (e) => {
        selector.value = opt.value;
        selector.dispatchEvent(new Event('change'));
        optionsContainer.style.display = 'none';
        document.getElementById('vault-dropdown-container')?.classList.remove('open');
      });
      optionsContainer.appendChild(div);
    });
  }

  async loadActiveVaultData() {
    if (!this.activeVaultId) return;
    this.selectedBiomarkerDate = null;

    try {
      this.activeVault = await this.apiRequest(`/vaults/${this.activeVaultId}`);
      this.renderVaultOverview(this.activeVault);
      this.cacheEmergencyData(this.activeVault);

      // Load tabs in parallel
      await Promise.all([
        this.loadMetrics(),
        this.loadDocuments(),
        this.loadAuditTrail()
      ]);
    } catch (err) {
      console.error('Failed to load vault data:', err);
    }
  }

  // 10. Render Views
  renderVaultOverview(vault) {
    const t = (key) => (window.AHB_I18N ? window.AHB_I18N.t(key) : key);
    const translateRel = (rel) => (window.AHB_I18N ? window.AHB_I18N.translateRelation(rel) : rel);

    const nameEl = document.getElementById('patient-name');
    const relationPill = document.getElementById('patient-relation-pill');
    const bloodEl = document.getElementById('patient-blood-group');
    const emergencyEl = document.getElementById('patient-emergency-contact');
    const emergencyCall = document.getElementById('patient-emergency-call');
    const allergiesEl = document.getElementById('patient-allergies-text');
    const conditionsEl = document.getElementById('patient-conditions-text');
    const medicationsEl = document.getElementById('patient-medications-text');
    const emergencyToggle = document.getElementById('emergency-toggle');
    const emergencyStatusText = document.getElementById('emergency-ready-status');

    if (nameEl) nameEl.textContent = vault.full_name || 'Anonymous Patient';
    if (relationPill) relationPill.textContent = translateRel(vault.relation || 'Self');
    if (bloodEl) bloodEl.textContent = vault.blood_group || 'O+';

    const emergencyPhone = vault.emergency_1_phone || vault.personal_contact || 'N/A';
    if (emergencyEl) emergencyEl.textContent = emergencyPhone;
    if (emergencyCall) {
      emergencyCall.href = emergencyPhone !== 'N/A' ? `tel:${emergencyPhone}` : '#';
      emergencyCall.style.display = emergencyPhone !== 'N/A' ? 'inline-flex' : 'none';
      emergencyCall.innerHTML = `📞 <span>${t('overview.call_primary')}</span>`;
    }

    if (allergiesEl) allergiesEl.textContent = vault.allergies || t('overview.none_reported');
    if (conditionsEl) conditionsEl.textContent = vault.medical_conditions || t('overview.none_reported');
    if (medicationsEl) medicationsEl.textContent = vault.medications || t('overview.none_reported');

    if (emergencyToggle) {
      emergencyToggle.checked = vault.is_emergency_ready !== false;
    }
    if (emergencyStatusText) {
      emergencyStatusText.textContent = vault.is_emergency_ready !== false ? t('status.active') : t('status.disabled');
      emergencyStatusText.style.color = vault.is_emergency_ready !== false ? '#34d399' : '#fb7185';
    }

    // Render Caregiver Emergency Contacts Grid (At least 2 contacts)
    const contactsContainer = document.getElementById('overview-contacts-container');
    if (contactsContainer) {
      const contacts = [
        { name: vault.emergency_1_name, rel: vault.emergency_1_relation || 'Primary Caregiver', phone: vault.emergency_1_phone, priorityKey: 'contact.primary' },
        { name: vault.emergency_2_name, rel: vault.emergency_2_relation || 'Secondary Caregiver', phone: vault.emergency_2_phone, priorityKey: 'contact.secondary' },
        { name: vault.emergency_3_name, rel: vault.emergency_3_relation || 'Alternative / Doctor', phone: vault.emergency_3_phone, priorityKey: 'contact.alternative' }
      ].filter(c => c.name || c.phone);

      if (contacts.length === 0) {
        contactsContainer.innerHTML = `
          <div class="glass-card" style="grid-column: 1/-1; text-align: center; border: 1px dashed rgba(239, 68, 68, 0.4); padding: 1.5rem;">
            <p style="color: #fb7185; font-weight: 700; font-size: 0.95rem;">⚠️ ${t('overview.no_contacts_warning')}</p>
            <p class="text-muted" style="font-size: 0.82rem; margin-top: 0.35rem;">${t('overview.no_contacts_desc')}</p>
            <button class="btn btn-sm btn-primary" style="margin-top: 0.75rem;" onclick="window.healthBridgeApp.openEditProfileModal()">+ ${t('overview.add_contacts_btn')}</button>
          </div>
        `;
      } else {
        contactsContainer.innerHTML = contacts.map((c, idx) => `
          <div class="glass-card" style="display: flex; flex-direction: column; justify-content: space-between; gap: 0.75rem;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
              <div>
                <h4 style="font-size: 1rem; font-weight: 800;">${c.name || t('overview.emergency_contact')}</h4>
                <span class="badge" style="margin-top: 0.35rem; display: inline-block;">${translateRel(c.rel)}</span>
              </div>
              <span class="badge" style="background: ${idx === 0 ? 'rgba(239, 68, 68, 0.15); color: #fb7185;' : 'rgba(99, 102, 241, 0.15); color: #a5b4fc;'}">${t(c.priorityKey)}</span>
            </div>
            <div>
              <p style="font-family: monospace; font-size: 1.05rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.5rem;">${c.phone || t('overview.no_phone')}</p>
              ${c.phone ? `<a href="tel:${c.phone}" class="btn btn-sm ${idx === 0 ? 'btn-danger' : 'btn-primary'}" style="width: 100%;">📞 ${t('contact.call')} ${c.name ? c.name.split(' ')[0] : t('contact.caregiver')}</a>` : ''}
            </div>
          </div>
        `).join('');
      }
    }

    // Render QR Code for Emergency Access
    this.renderEmergencyQRCode(vault);
  }

  async switchQrMode(mode) {
    this.qrMode = mode;
    const cryptoBtn = document.getElementById('qr-mode-crypto-btn');
    const urlBtn = document.getElementById('qr-mode-url-btn');
    const sealBadge = document.getElementById('qr-crypto-seal-badge');

    if (cryptoBtn && urlBtn) {
      if (mode === 'crypto') {
        cryptoBtn.className = 'btn btn-sm btn-primary';
        urlBtn.className = 'btn btn-sm';
        if (sealBadge) sealBadge.style.display = 'block';
      } else {
        cryptoBtn.className = 'btn btn-sm';
        urlBtn.className = 'btn btn-sm btn-primary';
        if (sealBadge) sealBadge.style.display = 'none';
      }
    }

    if (this.activeVault) {
      await this.renderEmergencyQRCode(this.activeVault);
    }
  }

  async renderEmergencyQRCode(vault) {
    const qrContainer = document.getElementById('emergency-qr-code');
    if (!qrContainer || !window.QRCode) return;
    qrContainer.innerHTML = '';

    const token = vault.qr_token || vault.id;
    const emergencyUrl = `${window.location.origin}/static/offline_emergency.html?token=${token}`;

    let qrText = emergencyUrl;

    if (this.qrMode === 'crypto') {
      try {
        if (!this.signedQrPayload || this.signedQrVaultId !== vault.id) {
          const res = await this.apiRequest(`/vaults/${vault.id}/crypto-qr`);
          this.signedQrPayload = res.signed_qr_payload;
          this.signedQrVaultId = vault.id;
        }
        if (this.signedQrPayload) {
          qrText = this.signedQrPayload;
        }
      } catch (err) {
        console.warn('Could not fetch signed offline QR payload, falling back to emergency URL:', err);
        qrText = emergencyUrl;
      }
    }

    new QRCode(qrContainer, {
      text: qrText,
      width: 170,
      height: 170,
      colorDark: this.qrMode === 'crypto' ? '#047857' : '#0f766e',
      colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.M
    });

    const offlineCardLink = document.getElementById('offline-card-link');
    if (offlineCardLink) {
      offlineCardLink.href = emergencyUrl;
    }
  }

  // 10b. Edit Profile & Emergency Contacts Modal
  openEditProfileModal() {
    if (!this.activeVault) return;
    const v = this.activeVault;

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || '';
    };

    setVal('edit-full-name', v.full_name);
    setVal('edit-blood-group', v.blood_group || 'O+');
    setVal('edit-personal-phone', v.personal_contact);
    setVal('edit-em1-name', v.emergency_1_name);
    setVal('edit-em1-rel', v.emergency_1_relation || 'Father');
    setVal('edit-em1-phone', v.emergency_1_phone);
    setVal('edit-em2-name', v.emergency_2_name);
    setVal('edit-em2-rel', v.emergency_2_relation || 'Mother');
    setVal('edit-em2-phone', v.emergency_2_phone);
    setVal('edit-allergies', v.allergies);
    setVal('edit-conditions', v.medical_conditions);
    setVal('edit-medications', v.medications);

    const modal = document.getElementById('edit-profile-modal');
    if (modal) modal.style.display = 'flex';
  }

  async handleProfileUpdate(e) {
    e.preventDefault();
    if (!this.activeVaultId) return;

    const getVal = (id) => {
      const el = document.getElementById(id);
      return el ? el.value.trim() : '';
    };

    const payload = {
      full_name: getVal('edit-full-name'),
      blood_group: getVal('edit-blood-group'),
      personal_contact: getVal('edit-personal-phone'),
      emergency_1_name: getVal('edit-em1-name'),
      emergency_1_relation: getVal('edit-em1-rel'),
      emergency_1_phone: getVal('edit-em1-phone'),
      emergency_2_name: getVal('edit-em2-name'),
      emergency_2_relation: getVal('edit-em2-rel'),
      emergency_2_phone: getVal('edit-em2-phone'),
      allergies: getVal('edit-allergies'),
      medical_conditions: getVal('edit-conditions'),
      medications: getVal('edit-medications')
    };

    try {
      await this.apiRequest(`/vaults/${this.activeVaultId}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
      });

      this.showToast('Patient Profile & Emergency Contacts updated successfully!', 'success');
      const modal = document.getElementById('edit-profile-modal');
      if (modal) modal.style.display = 'none';

      await this.loadActiveVaultData();
    } catch (err) {
      this.showToast(`Failed to update profile: ${err.message}`, 'error');
    }
  }

  // 11. Handle Emergency Toggle
  async handleEmergencyToggle(isReady) {
    if (!this.activeVaultId) return;

    try {
      await this.apiRequest(`/vaults/${this.activeVaultId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_emergency_ready: isReady })
      });

      const statusText = document.getElementById('emergency-ready-status');
      if (statusText) {
        statusText.textContent = isReady ? 'Active' : 'Disabled';
        statusText.style.color = isReady ? '#34d399' : '#fb7185';
      }

      this.showToast(`Emergency QR access ${isReady ? 'enabled' : 'disabled'}`, isReady ? 'success' : 'info');
    } catch (err) {
      this.showToast(`Failed to update emergency readiness: ${err.message}`, 'error');
    }
  }

  // 12. Offline Emergency Caching
  cacheEmergencyData(vault) {
    try {
      localStorage.setItem(`emergency_vault_${vault.id}`, JSON.stringify({
        id: vault.id,
        qr_token: vault.qr_token,
        full_name: vault.full_name,
        blood_group: vault.blood_group,
        personal_contact: vault.personal_contact,
        allergies: vault.allergies,
        medical_conditions: vault.medical_conditions,
        medications: vault.medications,
        emergency_1_name: vault.emergency_1_name,
        emergency_1_relation: vault.emergency_1_relation,
        emergency_1_phone: vault.emergency_1_phone,
        emergency_2_name: vault.emergency_2_name,
        emergency_2_relation: vault.emergency_2_relation,
        emergency_2_phone: vault.emergency_2_phone,
        emergency_3_name: vault.emergency_3_name,
        emergency_3_relation: vault.emergency_3_relation,
        emergency_3_phone: vault.emergency_3_phone,
        cached_at: new Date().toISOString()
      }));
    } catch (e) {
      console.warn('Emergency caching error:', e);
    }
  }

  // 13. Metrics Tab
  async loadMetrics() {
    if (!this.activeVaultId) return;
    const container = document.getElementById('metrics-list');
    const badge = document.getElementById('biomarker-count-badge');
    if (!container) return;

    try {
      const resp = await this.apiRequest(`/vaults/${this.activeVaultId}/metrics`);
      this.allMetrics = Array.isArray(resp) ? resp : (resp?.metrics || []);
      
      if (badge) badge.textContent = this.allMetrics.length;

      // Group metrics by observed date
      this.biomarkerDatesMap = {};
      this.allMetrics.forEach(m => {
        const dateStr = m.observed_date ? m.observed_date.split('T')[0] : 'recent';
        if (!this.biomarkerDatesMap[dateStr]) {
          this.biomarkerDatesMap[dateStr] = [];
        }
        this.biomarkerDatesMap[dateStr].push(m);
      });

      this.sortedBiomarkerDates = Object.keys(this.biomarkerDatesMap).sort((a, b) => {
        if (a === 'recent') return 1;
        if (b === 'recent') return -1;
        return new Date(b) - new Date(a);
      });

      // Set default selected date to the latest available
      if (!this.selectedBiomarkerDate || !this.sortedBiomarkerDates.includes(this.selectedBiomarkerDate)) {
        this.selectedBiomarkerDate = this.sortedBiomarkerDates[0] || 'recent';
      }

      this.renderDateSelector();
      this.applyBiomarkerFilters();
    } catch (err) {
      container.innerHTML = '<p style="color: #fb7185;">Failed to load health metrics.</p>';
    }
  }

  getMetricDetails(name, value) {
    const BIOMARKER_METADATA = {
      creatinine: { displayName: 'Creatinine', min: 0.5, max: 1.3, category: 'Kidney Function' },
      urea: { displayName: 'Urea (BUN)', min: 7.0, max: 20.0, category: 'Kidney Function' },
      uric_acid: { displayName: 'Uric Acid', min: 3.5, max: 7.2, category: 'Kidney Function' },
      hemoglobin: { displayName: 'Hemoglobin', min: 12.0, max: 17.5, category: 'Blood Count' },
      sugar: { displayName: 'Blood Sugar', min: 70, max: 140, category: 'Metabolic' },
      glucose: { displayName: 'Blood Sugar', min: 70, max: 140, category: 'Metabolic' },
      hba1c: { displayName: 'HbA1c', min: 4.0, max: 5.6, category: 'Metabolic' },
      cholesterol: { displayName: 'Total Cholesterol', min: 100, max: 200, category: 'Lipid Profile' },
      platelets: { displayName: 'Platelet Count', min: 150000, max: 450000, category: 'Blood Count' },
      wbc: { displayName: 'WBC Count', min: 4000, max: 11000, category: 'Blood Count' },
      rbc: { displayName: 'RBC Count', min: 4.2, max: 6.1, category: 'Blood Count' },
      bilirubin: { displayName: 'Total Bilirubin', min: 0.1, max: 1.2, category: 'Liver Function' },
      sgot: { displayName: 'SGOT (AST)', min: 5.0, max: 40.0, category: 'Liver Function' },
      ast: { displayName: 'SGOT (AST)', min: 5.0, max: 40.0, category: 'Liver Function' },
      sgpt: { displayName: 'SGPT (ALT)', min: 7.0, max: 56.0, category: 'Liver Function' },
      alt: { displayName: 'SGPT (ALT)', min: 7.0, max: 56.0, category: 'Liver Function' },
      alkaline_phosphatase: { displayName: 'Alkaline Phosphatase', min: 44, max: 147, category: 'Liver Function' },
      alp: { displayName: 'Alkaline Phosphatase', min: 44, max: 147, category: 'Liver Function' },
      albumin: { displayName: 'Albumin', min: 3.4, max: 5.4, category: 'Liver Function' },
      sodium: { displayName: 'Sodium', min: 135, max: 145, category: 'Electrolytes' },
      potassium: { displayName: 'Potassium', min: 3.5, max: 5.1, category: 'Electrolytes' },
      calcium: { displayName: 'Calcium', min: 8.5, max: 10.5, category: 'Electrolytes' }
    };

    const cleanKey = name.toLowerCase().replace(/[\s_-]+/g, '');
    let meta = null;
    for (const k in BIOMARKER_METADATA) {
      if (cleanKey.includes(k)) {
        meta = BIOMARKER_METADATA[k];
        break;
      }
    }

    let displayName = name.split(/[\s_-]+/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    displayName = displayName.replace(/\bHba1c\b/i, 'HbA1c')
                             .replace(/\bWbc\b/i, 'WBC')
                             .replace(/\bRbc\b/i, 'RBC')
                             .replace(/\bBun\b/i, 'BUN')
                             .replace(/\bSgot\b/i, 'SGOT')
                             .replace(/\bSgpt\b/i, 'SGPT')
                             .replace(/\bAlp\b/i, 'ALP')
                             .replace(/\bAst\b/i, 'AST')
                             .replace(/\bAlt\b/i, 'ALT');

    let min = null, max = null, category = 'General';
    if (meta) {
      displayName = meta.displayName;
      min = meta.min;
      max = meta.max;
      category = meta.category;
    }

    let statusClass = 'normal';
    let statusText = 'Normal Range';
    const numVal = parseFloat(value);
    
    if (!isNaN(numVal) && min !== null && max !== null) {
      if (numVal < min) {
        statusClass = 'low';
        statusText = 'Low';
      } else if (numVal > max) {
        statusClass = 'high';
        statusText = 'High';
      }
    }

    return { displayName, min, max, category, statusClass, statusText };
  }

  renderDateSelector() {
    const headerFlex = document.querySelector('#tab-biomarkers > div:first-child');
    if (!headerFlex) return;

    // Clean up any existing dropdown and listener
    if (this._closeBiomarkerDateDropdown) {
      this._closeBiomarkerDateDropdown();
    }

    // Remove any existing date wrapper to prevent duplicates
    const oldWrapper = document.getElementById('biomarker-date-selector-wrapper');
    if (oldWrapper) oldWrapper.remove();

    if (!this.sortedBiomarkerDates || this.sortedBiomarkerDates.length === 0) return;

    const wrapper = document.createElement('div');
    wrapper.id = 'biomarker-date-selector-wrapper';
    wrapper.style.cssText = 'position: relative; margin-left: auto;';

    const formatDate = (dateStr) => {
      if (dateStr === 'recent') return 'Recent Observation';
      const d = new Date(dateStr);
      if (isNaN(d)) return dateStr;
      return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    };

    const selectedText = formatDate(this.selectedBiomarkerDate);
    const hasMultiple = this.sortedBiomarkerDates.length > 1;

    wrapper.innerHTML = `
      <div id="biomarker-report-date-badge" style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 0.5rem 1rem; display: flex; align-items: center; gap: 0.5rem; font-size: 0.88rem; font-weight: 700; cursor: ${hasMultiple ? 'pointer' : 'default'}; box-shadow: var(--panel-shadow);">
        📅 <span style="margin-left: 0.25rem;">${selectedText}</span> ${hasMultiple ? '<span style="font-size: 0.65rem; color: var(--text-muted); margin-left: 0.25rem;">▼</span>' : ''}
      </div>
      <div id="biomarker-date-dropdown-menu" style="display: none; position: absolute; top: calc(100% + 6px); right: 0; background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); z-index: 1000; min-width: 160px; overflow: hidden; padding: 0.3rem 0;">
      </div>
    `;

    headerFlex.appendChild(wrapper);

    const badge = wrapper.querySelector('#biomarker-report-date-badge');
    const menu = wrapper.querySelector('#biomarker-date-dropdown-menu');

    if (badge && menu && hasMultiple) {
      const closeMenu = () => {
        menu.style.display = 'none';
        document.removeEventListener('click', closeMenu);
        this._closeBiomarkerDateDropdown = null;
      };

      badge.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = menu.style.display === 'block';
        if (isOpen) {
          closeMenu();
        } else {
          // Close other custom dropdowns in the app if they are open
          const vaultOptions = document.getElementById('vault-dropdown-options');
          if (vaultOptions) vaultOptions.style.display = 'none';
          document.getElementById('vault-dropdown-container')?.classList.remove('open');

          const profileOptions = document.getElementById('profile-dropdown-options');
          if (profileOptions) profileOptions.style.display = 'none';
          document.getElementById('header-profile-menu')?.classList.remove('open');

          menu.style.display = 'block';
          this._closeBiomarkerDateDropdown = closeMenu;
          document.addEventListener('click', closeMenu);
        }
      });

      this.sortedBiomarkerDates.forEach(dateStr => {
        const item = document.createElement('div');
        item.className = `biomarker-date-item ${dateStr === this.selectedBiomarkerDate ? 'active' : ''}`;
        item.textContent = formatDate(dateStr);
        item.addEventListener('click', (e) => {
          e.stopPropagation();
          this.selectedBiomarkerDate = dateStr;
          closeMenu();
          this.renderDateSelector();
          this.applyBiomarkerFilters();
        });
        menu.appendChild(item);
      });
    }
  }

  renderBiomarkers(metrics) {
    const container = document.getElementById('metrics-list');
    const summaryContainer = document.getElementById('biomarkers-summary-container');
    if (!container) return;

    if (!metrics || metrics.length === 0) {
      container.innerHTML = '<div class="glass-card" style="grid-column: 1/-1; text-align: center;"><p class="text-muted">No health metrics match the active filters.</p></div>';
      if (summaryContainer) summaryContainer.innerHTML = '';
      return;
    }

    // Categories status map
    const categoryStatus = {
      'Kidney Function': 'Good',
      'General Health': 'Good',
      'Blood Count': 'Good',
      'Metabolic': 'Good'
    };

    let totalAbnormal = 0;

    container.innerHTML = metrics.map((m) => {
      const details = this.getMetricDetails(m.metric_name, m.metric_value);
      
      if (details.statusClass !== 'normal') {
        totalAbnormal++;
        if (details.category === 'Kidney Function') categoryStatus['Kidney Function'] = 'Review';
        else if (details.category === 'Blood Count') categoryStatus['Blood Count'] = 'Review';
        else if (details.category === 'Metabolic') categoryStatus['Metabolic'] = 'Review';
        else categoryStatus['General Health'] = 'Review';
      }

      // Determine visual range slider track parameters
      let rangeHtml = '';
      const numVal = parseFloat(m.metric_value);
      if (!isNaN(numVal) && details.min !== null && details.max !== null) {
        const minVal = details.min;
        const maxVal = details.max;
        const diff = maxVal - minVal;
        
        const trackMin = Math.max(0, minVal - diff * 0.4);
        const trackMax = maxVal + diff * 0.4;
        const trackRange = trackMax - trackMin;
        
        const minPercent = ((minVal - trackMin) / trackRange) * 100;
        const maxPercent = ((maxVal - trackMin) / trackRange) * 100;
        
        let valuePercent = ((numVal - trackMin) / trackRange) * 100;
        valuePercent = Math.max(0, Math.min(100, valuePercent));
        
        rangeHtml = `
          <div style="margin-top: 0.8rem; padding-left: 3.5rem;">
            <div class="biomarker-range-track" style="height: 10px; background: var(--slate-700); border-radius: 5px; position: relative; margin-bottom: 0.4rem;">
              <div class="biomarker-range-bar" style="position: absolute; height: 100%; background: #10b981; opacity: 0.25; border-radius: 5px; left: ${minPercent}%; width: ${maxPercent - minPercent}%;"></div>
              <div class="biomarker-value-indicator ${details.statusClass}" style="position: absolute; top: 50%; transform: translate(-50%, -50%); width: 14px; height: 14px; border-radius: 50%; border: 3px solid var(--panel-bg); background: #0d9488; left: ${valuePercent}%;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); font-weight: 600;">
              <span>Min: ${minVal}</span>
              <span>Max: ${maxVal}</span>
            </div>
          </div>
        `;
      } else {
        rangeHtml = `
          <div style="margin-top: 0.8rem; padding-left: 3.5rem;">
            <div style="border-top: 1px dashed var(--border-glow); margin-bottom: 0.4rem; opacity: 0.6;"></div>
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">
              <span>Reference range</span>
              <span>-</span>
            </div>
          </div>
        `;
      }

      // Map icons for display
      let iconBg = '#f1f3f4';
      let iconColor = '#5f6368';
      let iconSvg = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M10 2v8L4.7 18.2a2 2 0 0 0 1.7 2.8h11.2a2 2 0 0 0 1.7-2.8L14 10V2" />
        </svg>
      `;

      const cleanKey = m.metric_name.toLowerCase().replace(/[\s_-]+/g, '');
      if (cleanKey.includes('creatinine')) {
        iconBg = 'rgba(16, 185, 129, 0.1)';
        iconColor = '#10b981';
        iconSvg = `
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 21a9 9 0 0 0 9-9c0-5-9-10-9-10S3 7 3 12a9 9 0 0 0 9 9z" />
            <path d="M12 7c-2 2-3 4-3 5.5s1 2.5 3 2.5 3-1 3-2.5S14 9 12 7z" opacity="0.3" fill="currentColor"/>
          </svg>
        `;
      } else if (cleanKey.includes('urea')) {
        iconBg = 'rgba(56, 189, 248, 0.1)';
        iconColor = '#0ea5e9';
        iconSvg = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 22a7 7 0 0 0 7-7c0-4.3-7-13-7-13S5 10.7 5 15a7 7 0 0 0 7 7z" />
          </svg>
        `;
      } else if (cleanKey.includes('uric')) {
        iconBg = 'rgba(139, 92, 246, 0.1)';
        iconColor = '#8b5cf6';
        iconSvg = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="5" r="2.5" />
            <circle cx="6" cy="12" r="2.5" />
            <circle cx="18" cy="12" r="2.5" />
            <circle cx="12" cy="19" r="2.5" />
            <line x1="12" y1="7.5" x2="12" y2="16.5" />
            <line x1="7.5" y1="11" x2="16.5" y2="11" />
          </svg>
        `;
      } else if (cleanKey.includes('hemoglobin')) {
        iconBg = 'rgba(239, 68, 68, 0.1)';
        iconColor = '#ef4444';
        iconSvg = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L4 10a8 8 0 1 0 16 0L12 2z" />
          </svg>
        `;
      }

      const statusColor = details.statusClass === 'normal' ? '#10b981' : '#ef4444';
      const statusTextLabel = details.statusClass === 'normal' ? 'Within normal range' : 'Requires attention';

      return `
        <div class="biomarker-card" style="box-shadow: var(--panel-shadow); border: 1px solid var(--card-border); border-radius: 16px; padding: 1.25rem; background: var(--card-bg); display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.75rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem;">
              <div style="width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: ${iconBg}; color: ${iconColor};">
                ${iconSvg}
              </div>
              <div>
                <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary); margin: 0; line-height: 1.25;">${details.displayName}</h4>
                <small style="font-size: 0.78rem; color: var(--text-muted); font-weight: 600;">${details.category}</small>
              </div>
            </div>
            <span class="biomarker-badge ${details.statusClass}" style="display: flex; align-items: center; gap: 0.25rem; font-size: 0.68rem; font-weight: 800; border-radius: 20px; padding: 4px 10px;">
              <span style="font-size: 0.75rem; font-weight: 900;">✓</span> ${details.statusText}
            </span>
          </div>
          <div style="display: flex; align-items: baseline; gap: 0.35rem; margin-top: 1rem; margin-bottom: 0.5rem; padding-left: 3.5rem;">
            <span style="font-size: 2.2rem; font-weight: 800; color: #0d9488; line-height: 1;">${m.metric_value}</span>
            <span style="font-size: 0.95rem; color: var(--text-muted); font-weight: 600;">${m.metric_unit || ''}</span>
          </div>
          ${rangeHtml}
          <div style="margin: 1.25rem -1.25rem -1.25rem -1.25rem; padding: 0.65rem 1.25rem; background: var(--slate-900); border-top: 1px solid var(--border-glow); border-bottom-left-radius: 16px; border-bottom-right-radius: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 0.76rem; margin-top: auto;">
            <span style="color: ${statusColor}; font-weight: 700; display: flex; align-items: center; gap: 0.25rem;">
              ✓ ${statusTextLabel}
            </span>
            <span style="color: var(--text-muted); font-weight: 600; opacity: 0.8;">HL7 Observation</span>
          </div>
        </div>
      `;
    }).join('');

    // Set title and subtitle inside biomarkers tab
    const titleBlock = document.querySelector('#tab-biomarkers h2[data-i18n="biomarkers.title"]');
    if (titleBlock) {
      const hasKidney = metrics.some(m => m.metric_name.toLowerCase().includes('creatinine') || m.metric_name.toLowerCase().includes('urea'));
      titleBlock.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <div style="width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: rgba(16, 185, 129, 0.1); color: #10b981;">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10 2v8L4.7 18.2a2 2 0 0 0 1.7 2.8h11.2a2 2 0 0 0 1.7-2.8L14 10V2" />
              <path d="M8.5 2h7M7 14h10" />
            </svg>
          </div>
          <div>
            <div style="font-size: 1.6rem; font-weight: 800; line-height: 1.2;">${hasKidney ? 'Kidney Health Report' : 'Clinical Health Report'}</div>
            <div style="font-size: 0.9rem; color: var(--text-muted); font-weight: 500;">Lab Test Summary</div>
          </div>
        </div>
      `;
      const sub = titleBlock.nextElementSibling;
      if (sub && sub.tagName.toLowerCase() === 'p') {
        sub.style.display = 'none';
      }
    }

    // Build the Overall Summary Section
    if (summaryContainer) {
      const allNormal = totalAbnormal === 0;
      const statusColor = allNormal ? '#10b981' : '#ef4444';
      const summaryText = allNormal 
        ? 'All parameters are in <span style="color: #10b981; font-weight: 700;">normal range</span>.'
        : 'Some parameters <span style="color: #ef4444; font-weight: 700;">require attention</span>.';
      const overallStatusText = allNormal ? 'Normal' : 'Attention';

      const getStatusItemHtml = (title, status) => {
        const isGood = status === 'Good';
        const color = isGood ? '#10b981' : '#f59e0b';
        return `
          <div style="display: flex; flex-direction: column; gap: 0.15rem; min-width: 110px;">
            <div style="display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; font-weight: 600; color: var(--text-muted);">
              <span style="color: ${color};">✓</span> ${title}
            </div>
            <div style="font-size: 0.95rem; font-weight: 800; color: ${color};">${status}</div>
          </div>
        `;
      };

      summaryContainer.innerHTML = `
        <div class="glass-card" style="margin-top: 2rem; padding: 1.25rem 1.5rem; display: flex; justify-content: space-between; align-items: center; gap: 1.5rem; flex-wrap: wrap; background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.15); border-radius: 16px;">
          <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: rgba(16, 185, 129, 0.1); color: #10b981;">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div>
              <h4 style="font-size: 1.1rem; font-weight: 800; color: var(--text-primary); margin: 0; line-height: 1.2;">Overall Summary</h4>
              <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0.15rem 0 0 0; font-weight: 500;">${summaryText}</p>
            </div>
          </div>
          
          <div class="summary-divider" style="width: 1px; height: 42px; background: rgba(16, 185, 129, 0.2);"></div>
          
          <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; flex: 1; justify-content: space-around; min-width: 280px;">
            ${getStatusItemHtml('Kidney Function', categoryStatus['Kidney Function'])}
            ${getStatusItemHtml('General Health', categoryStatus['General Health'])}
            ${getStatusItemHtml('Blood Count', categoryStatus['Blood Count'])}
            <div style="display: flex; flex-direction: column; gap: 0.15rem; min-width: 110px;">
              <div style="display: flex; align-items: center; gap: 0.25rem; font-size: 0.8rem; font-weight: 600; color: var(--text-muted);">
                <span>✓</span> Overall Status
              </div>
              <div style="font-size: 0.95rem; font-weight: 800; color: ${statusColor};">${overallStatusText}</div>
            </div>
          </div>
        </div>
        
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 1rem; padding: 0 0.5rem; font-size: 0.78rem; color: var(--text-muted); font-weight: 600;">
          <span style="font-size: 0.85rem; color: var(--indigo-600);">ⓘ</span> Note: This report is for informational purposes only. Please consult your doctor for medical advice.
        </div>
      `;
    }
  }

  applyBiomarkerFilters() {
    const query = (document.getElementById('biomarker-search')?.value || '').toLowerCase().trim();
    const selectedDate = this.selectedBiomarkerDate || 'recent';

    // Get metrics of the selected date
    let filtered = this.biomarkerDatesMap[selectedDate] || [];

    if (query) {
      filtered = filtered.filter(m => {
        const details = this.getMetricDetails(m.metric_name, m.metric_value);
        return details.displayName.toLowerCase().includes(query) ||
               m.metric_name.toLowerCase().includes(query) ||
               (m.metric_unit && m.metric_unit.toLowerCase().includes(query));
      });
    }

    this.renderBiomarkers(filtered);
  }

  filterBiomarkers(query) {
    this.applyBiomarkerFilters();
  }

  // 14. Documents & Files Tabs
  async loadDocuments() {
    if (!this.activeVaultId) return;
    const container = document.getElementById('files-grid');
    const badge = document.getElementById('doc-count-badge');

    try {
      const docs = await this.apiRequest(`/vaults/${this.activeVaultId}/documents`);
      this.documents = docs || [];
      this.allFiles = this.documents;

      if (badge) badge.textContent = this.documents.length;

      this.renderFiles(this.documents);
    } catch (err) {
      if (container) container.innerHTML = '<p style="color: #fb7185;">Failed to load documents.</p>';
    }
  }

  async renderFiles(docs) {
    const container = document.getElementById('files-grid');
    const badge = document.getElementById('file-count-badge');
    if (!container) return;
    const t = (key) => (window.AHB_I18N ? window.AHB_I18N.t(key) : key);

    this.allFiles = docs || [];
    if (badge) badge.textContent = this.allFiles.length;

    if (!docs || docs.length === 0) {
      container.innerHTML = `
        <div class="glass-card" style="grid-column: 1/-1; text-align: center; padding: 2.5rem 1.5rem;">
          <span style="font-size: 3rem; display: block; margin-bottom: 0.75rem;">📁</span>
          <h4 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 0.35rem;">${t('files.empty')}</h4>
          <p class="text-muted" style="font-size: 0.85rem; max-width: 420px; margin: 0 auto 1.25rem;">Upload blood tests, prescriptions, or medical reports to view and share them.</p>
          <button class="btn btn-primary btn-sm" onclick="document.getElementById('doc-file-input').click()">+ ${t('documents.upload_btn')}</button>
        </div>
      `;
      return;
    }

    // Check on-device cached documents from IndexedDB
    const cachedDocs = await this.localDB.getAllCachedDocs(this.activeVaultId);
    const cachedSet = new Set(cachedDocs.map(c => String(c.docId)));

    container.innerHTML = docs.map((d) => {
      const dateStr = d.upload_date ? new Date(d.upload_date).toLocaleDateString() : 'Today';
      const cleanName = d.file_name || 'Medical Report';
      const cat = d.category || 'Clinical Report';
      const isCached = cachedSet.has(String(d.id));

      const storageBadge = isCached
        ? `<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-size: 0.7rem; font-weight: 700;">⚡ On-Device & Cloud Synced</span>`
        : `<span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; font-size: 0.7rem; font-weight: 700;">☁️ Cloud Synced</span>`;

      return `
        <div class="glass-card" style="display: flex; flex-direction: column; justify-content: space-between; gap: 1rem; border: 1px solid rgba(255, 255, 255, 0.08); transition: transform 0.2s ease, box-shadow 0.2s ease;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 2rem;">📄</span>
                <div>
                  <span class="badge" style="background: rgba(20, 184, 166, 0.15); color: #2dd4bf; border-radius: 6px; font-size: 0.72rem; font-weight: 700;">${cat}</span>
                </div>
              </div>
              ${storageBadge}
            </div>

            <h4 style="font-size: 1.05rem; font-weight: 800; word-break: break-word; color: var(--text-primary); margin-bottom: 0.35rem;">${cleanName}</h4>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: var(--text-muted);">
              <span>📅 ${dateStr}</span>
              <span>🔒 Zero-Egress Encrypted</span>
            </div>
          </div>

          <!-- Interactive Action Buttons -->
          <div style="display: flex; flex-direction: column; gap: 0.5rem; border-top: 1px solid var(--border-glow); padding-top: 0.75rem;">
            <div style="display: flex; gap: 0.5rem;">
              <button class="btn btn-sm btn-primary" style="flex: 1; display: flex; align-items: center; justify-content: center; gap: 0.35rem;" onclick="window.healthBridgeApp.openPdfViewer(${d.id}, '${cleanName.replace(/'/g, "\\'")}', '${cat.replace(/'/g, "\\'")}')">
                👁️ <span>${t('files.open_pdf')}</span>
              </button>
              <button class="btn btn-sm" style="background: #25D366; color: white; border: none; font-weight: 800; display: flex; align-items: center; justify-content: center; gap: 0.35rem;" onclick="window.healthBridgeApp.sharePdfWhatsApp(${d.id}, '${cleanName.replace(/'/g, "\\'")}', '${cat.replace(/'/g, "\\'")}', '${d.upload_date || ''}')" title="Share via WhatsApp">
                💬 <span>WhatsApp</span>
              </button>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-top: 0.25rem;">
              <button class="btn btn-sm" style="flex: 1; text-align: center; font-size: 0.75rem; padding: 0.3rem 0.5rem;" onclick="window.healthBridgeApp.downloadDocumentLocally(${d.id}, '${cleanName.replace(/'/g, "\\'")}')">
                💾 <span>Save to Phone</span>
              </button>
              <button class="btn btn-sm btn-danger" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="window.healthBridgeApp.deleteDocument(${d.id})">
                🗑️
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  filterFiles(query) {
    const q = (query || '').toLowerCase().trim();
    if (!q) {
      this.renderFiles(this.allFiles);
      return;
    }
    const filtered = (this.allFiles || []).filter((d) =>
      (d.file_name && d.file_name.toLowerCase().includes(q)) ||
      (d.category && d.category.toLowerCase().includes(q))
    );
    this.renderFiles(filtered);
  }

  async openPdfViewer(docId, docName, docCategory) {
    if (!this.activeVaultId) return;

    const modal = document.getElementById('pdf-viewer-modal');
    const iframe = document.getElementById('pdf-viewer-iframe');
    const titleEl = document.getElementById('pdf-viewer-title');
    const catEl = document.getElementById('pdf-viewer-category');
    const newtabBtn = document.getElementById('pdf-viewer-newtab');
    const downloadBtn = document.getElementById('pdf-viewer-download');
    const whatsappBtn = document.getElementById('pdf-viewer-whatsapp');

    if (titleEl) titleEl.textContent = docName || 'Medical Report PDF';
    if (catEl) catEl.textContent = docCategory || 'Diagnostic Report';
    if (modal) modal.style.display = 'flex';

    try {
      // 1. Check local on-device IndexedDB cache first
      let cached = await this.localDB.getCachedDocumentBlob(docId);
      let blob = cached ? cached.blob : null;

      if (blob) {
        this.showToast('📱 Loaded instantly from Phone Storage (Offline Ready)', 'info');
      } else {
        // 2. Fetch from encrypted backend API and cache on-device for future offline use
        const fallbackUrl = `${API_BASE}/vaults/${this.activeVaultId}/documents/${docId}/serve`;
        const resp = await fetch(fallbackUrl, {
          headers: this.token ? { 'Authorization': `Bearer ${this.token}` } : {}
        });
        if (!resp.ok) throw new Error(`Could not load report (HTTP ${resp.status})`);
        blob = await resp.blob();

        // Cache into IndexedDB
        await this.localDB.cacheDocumentBlob(docId, this.activeVaultId, blob, {
          fileName: docName,
          category: docCategory
        });
        this.showToast('⚡ Report cached to Phone Storage for offline access', 'success');
        // Refresh grid badge
        this.renderFiles(this.allFiles);
      }

      const blobUrl = URL.createObjectURL(blob);
      if (iframe) iframe.src = blobUrl;
      if (newtabBtn) newtabBtn.href = blobUrl;
      if (downloadBtn) {
        downloadBtn.href = blobUrl;
        downloadBtn.download = docName || 'medical-report.pdf';
      }
      if (whatsappBtn) {
        whatsappBtn.onclick = () => this.sharePdfWhatsApp(docId, docName, docCategory, new Date().toISOString());
      }
    } catch (err) {
      console.error('Failed to open PDF:', err);
      this.showToast(`Error opening PDF: ${err.message}`, 'error');
    }
  }

  async downloadDocumentLocally(docId, fileName) {
    if (!this.activeVaultId) return;
    try {
      let cached = await this.localDB.getCachedDocumentBlob(docId);
      let blob = cached ? cached.blob : null;

      if (!blob) {
        const url = `${API_BASE}/vaults/${this.activeVaultId}/documents/${docId}/serve`;
        const resp = await fetch(url, {
          headers: this.token ? { 'Authorization': `Bearer ${this.token}` } : {}
        });
        if (!resp.ok) throw new Error('Download failed');
        blob = await resp.blob();
        await this.localDB.cacheDocumentBlob(docId, this.activeVaultId, blob, { fileName });
      }

      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = fileName || 'medical-report.pdf';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
      }, 500);

      this.showToast(`Saved "${fileName}" to Phone Storage!`, 'success');
    } catch (err) {
      this.showToast(`Save to phone failed: ${err.message}`, 'error');
    }
  }

  async exportAllLocalVaultFiles() {
    if (!this.activeVaultId) return;
    try {
      const docs = this.allFiles || [];
      if (docs.length === 0) {
        this.showToast('No documents found in vault to export.', 'info');
        return;
      }
      this.showToast(`Saving ${docs.length} records to your phone storage...`, 'info');
      for (const d of docs) {
        await this.downloadDocumentLocally(d.id, d.file_name || `report-${d.id}.pdf`);
        await new Promise(r => setTimeout(r, 400));
      }
      this.showToast('✅ All vault records saved to Phone Downloads!', 'success');
    } catch (err) {
      this.showToast(`Export failed: ${err.message}`, 'error');
    }
  }

  async clearDeviceCache() {
    if (!confirm('Clear on-device local document cache to free up phone storage? (Your encrypted records in the cloud vault will remain safe).')) return;
    try {
      await this.localDB.clearAll();
      this.showToast('Device document cache cleared successfully!', 'info');
      if (this.allFiles) {
        this.renderFiles(this.allFiles);
      }
    } catch (err) {
      this.showToast(`Failed to clear cache: ${err.message}`, 'error');
    }
  }

  closePdfViewer() {
    const modal = document.getElementById('pdf-viewer-modal');
    const iframe = document.getElementById('pdf-viewer-iframe');
    if (iframe) iframe.src = '';
    if (modal) modal.style.display = 'none';
  }

  sharePdfWhatsApp(docId, docName, docCategory, date) {
    if (!this.activeVaultId) return;
    const vaultName = this.activeVault?.full_name || 'Patient';
    const docUrl = `${window.location.origin}/api/v1/vaults/${this.activeVaultId}/documents/${docId}/serve`;
    const formattedDate = date ? new Date(date).toLocaleDateString() : 'Recent';

    const message = `🩺 *Aadhaar Health Bridge - Clinical Record*\n\n` +
      `👤 *Patient:* ${vaultName}\n` +
      `📄 *Report:* ${docName || 'Medical Report PDF'}\n` +
      `🏷️ *Category:* ${docCategory || 'Diagnostic Lab Report'}\n` +
      `📅 *Date:* ${formattedDate}\n\n` +
      `🔒 *Secure Report Link:*\n${docUrl}\n\n` +
      `_Encrypted & verified via Aadhaar Health Bridge PHR_`;

    const whatsappUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
    this.showToast('Opening WhatsApp with report summary...', 'info');
  }

  // 15. Document Upload with Automatic On-Device IndexedDB Caching
  async handleDocUpload(e) {
    e.preventDefault();
    if (!this.activeVaultId) return;

    const fileInput = document.getElementById('doc-file-input');
    const categorySelect = document.getElementById('doc-category-select');
    const statusEl = document.getElementById('upload-status');
    const uploadBtn = document.getElementById('upload-btn');

    if (!fileInput || !fileInput.files[0]) {
      this.showToast('Please select a PDF report to upload.', 'error');
      return;
    }
    const file = fileInput.files[0];

    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', categorySelect ? categorySelect.value : 'Diagnostic Lab Report');
    formData.append('file_name', file.name);

    if (statusEl) {
      statusEl.innerHTML = '<span class="typing-dot" style="display:inline-block;"></span> Ingesting PDF & Extracting FHIR Observations...';
      statusEl.style.color = '#38bdf8';
    }
    if (uploadBtn) uploadBtn.disabled = true;

    try {
      const docRes = await this.apiRequest(`/vaults/${this.activeVaultId}/documents`, {
        method: 'POST',
        body: formData
      });

      // Cache raw uploaded file directly into phone IndexedDB
      if (docRes && docRes.id) {
        await this.localDB.cacheDocumentBlob(docRes.id, this.activeVaultId, file, {
          fileName: file.name,
          category: categorySelect ? categorySelect.value : 'Diagnostic Lab Report'
        });
      }

      this.showToast(`Document "${file.name}" saved locally & synced to vault!`, 'success');
      if (statusEl) {
        statusEl.textContent = '✅ Document stored on-device, synced with vault & indexed in local RAG!';
        statusEl.style.color = '#34d399';
      }
      fileInput.value = '';
      await this.loadDocuments();
      await this.loadMetrics();
      await this.loadAuditTrail();
    } catch (err) {
      if (statusEl) {
        statusEl.textContent = `❌ Upload failed: ${err.message}`;
        statusEl.style.color = '#fb7185';
      }
      this.showToast(`Upload failed: ${err.message}`, 'error');
    } finally {
      if (uploadBtn) uploadBtn.disabled = false;
    }
  }

  async deleteDocument(docId) {
    if (!confirm('Are you sure you want to delete this document from the vault?')) return;
    try {
      await this.apiRequest(`/vaults/${this.activeVaultId}/documents/${docId}`, {
        method: 'DELETE'
      });
      await this.localDB.deleteCachedDocument(docId);
      this.showToast('Document deleted from cloud and device storage.', 'info');
      await Promise.all([
        this.loadDocuments(),
        this.loadMetrics(),
        this.loadAuditTrail()
      ]);
    } catch (err) {
      this.showToast(`Delete failed: ${err.message}`, 'error');
    }
  }

  // 16. Local RAG Chat Assistant
  async handleChatSubmit(e) {
    e.preventDefault();
    if (!this.activeVaultId) return;

    const input = document.getElementById('chat-input');
    const query = input.value.trim();
    if (!query) return;

    await this.sendChatQuery(query);
    input.value = '';
  }

  sendQuickPrompt(promptText) {
    const input = document.getElementById('chat-input');
    if (input) {
      input.value = promptText;
      this.sendChatQuery(promptText);
      input.value = '';
    }
  }

  async sendChatQuery(query) {
    if (!this.activeVaultId) return;

    // Append User Message
    this.appendChatMessage('user', query);

    // Append Loading Assistant Placeholder
    const loadingId = this.appendChatMessage('assistant', '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div> Analyzing medical records with Local RAG...', true);

    try {
      const res = await this.apiRequest(`/vaults/${this.activeVaultId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ query })
      });

      this.updateChatMessage(loadingId, res.answer, res.ai_source, res.source_attributions);
    } catch (err) {
      this.updateChatMessage(loadingId, `⚠️ Error: ${err.message}`, 'Error');
    }
  }

  appendChatMessage(role, text, isLoading = false) {
    const container = document.getElementById('chat-messages');
    if (!container) return null;

    const id = `msg-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-msg ${role} ${isLoading ? 'loading' : ''}`;
    msgDiv.id = id;
    msgDiv.innerHTML = `
      <div class="msg-content">${text}</div>
    `;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
    return id;
  }

  updateChatMessage(id, text, aiSource = '', attributions = []) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('loading');

    let attrHtml = '';
    if (attributions && attributions.length > 0) {
      attrHtml = `
        <div class="source-attributions">
          ${attributions.filter(a => a.grounded !== false).map(a => `
            <span class="attr-tag">📑 ${a.file_name} (Chunk #${a.chunk_index})</span>
          `).join('')}
        </div>
      `;
    }

    el.innerHTML = `
      <div class="msg-content">${text}</div>
      <div class="chat-msg-footer">
        <span>🛡️ ${aiSource || 'Local Engine'}</span>
        <button class="btn btn-sm" style="padding: 0.15rem 0.4rem; font-size: 0.7rem;" onclick="window.healthBridgeApp.speakText('${escape(text.replace(/<[^>]*>?/gm, ''))}')">🔊 Read Aloud</button>
      </div>
      ${attrHtml}
    `;
    const container = document.getElementById('chat-messages');
    if (container) container.scrollTop = container.scrollHeight;
  }

  speakText(escapedText) {
    const raw = unescape(escapedText);
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(raw);
      utterance.rate = 1.0;
      window.speechSynthesis.speak(utterance);
      this.showToast('Reading response aloud...', 'info');
    } else {
      this.showToast('Speech synthesis not supported in this browser.', 'error');
    }
  }

  clearChat() {
    const container = document.getElementById('chat-messages');
    if (container) {
      container.innerHTML = `
        <div class="chat-msg assistant">
          <div class="msg-content">
            Chat cleared. How can I assist you with your medical records?
          </div>
        </div>
      `;
    }
  }

  // 17. Add Family Member
  async handleAddFamilyMember(e) {
    e.preventDefault();
    const name = document.getElementById('member-name').value.trim();
    const username = document.getElementById('member-username').value.trim();
    const password = document.getElementById('member-password').value;
    const relation = document.getElementById('member-relation').value;
    const bloodGroup = document.getElementById('member-blood-group').value;
    const phone = document.getElementById('member-phone').value.trim();

    try {
      await this.apiRequest('/vaults/family', {
        method: 'POST',
        body: JSON.stringify({
          full_name: name,
          username: username,
          password: password,
          relation: relation,
          blood_group: bloodGroup,
          emergency_1_phone: phone
        })
      });

      this.showToast(`Family vault created for ${name}!`, 'success');
      closeAddMemberModal();
      document.getElementById('add-member-form').reset();
      await this.loadUserProfile();
    } catch (err) {
      this.showToast(`Failed to add family member: ${err.message}`, 'error');
    }
  }

  // 18. Audit Trail
  async loadAuditTrail() {
    if (!this.activeVaultId) return;
    const container = document.getElementById('audit-list');
    if (!container) return;

    try {
      const logs = await this.apiRequest(`/vaults/${this.activeVaultId}/audit-trail`);
      if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="glass-card"><p class="text-muted">No audit logs recorded yet.</p></div>';
        return;
      }

      container.innerHTML = logs.map((l) => `
        <div class="glass-card" style="padding: 0.75rem 1.25rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; font-weight: 700;">${l.action || 'ACCESS'}</span>
            <span style="font-size: 0.88rem; font-weight: 600;">${l.details || l.event_type || 'Patient Vault Access'}</span>
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">
            ${l.timestamp ? new Date(l.timestamp).toLocaleString() : 'Just now'}
          </div>
        </div>
      `).join('');
    } catch (err) {
      container.innerHTML = '<p class="text-muted">Audit trail ready.</p>';
    }
  }

  // 19. Export FHIR Bundle
  async exportFHIRBundle() {
    if (!this.activeVaultId) return;
    try {
      const bundle = await this.apiRequest(`/vaults/${this.activeVaultId}/fhir`);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/fhir+json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fhir-patient-bundle-vault-${this.activeVaultId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      this.showToast('FHIR R4 Bundle downloaded successfully!', 'success');
    } catch (err) {
      this.showToast(`FHIR Export error: ${err.message}`, 'error');
    }
  }

  // 20. Print Emergency Card
  printEmergencyCard() {
    window.print();
  }

  // 21. View / Tab Management
  showView(viewName) {
    const authView = document.getElementById('auth-view');
    const appView = document.getElementById('app-view');
    const userControls = document.getElementById('user-controls');
    const profileMenu = document.getElementById('header-profile-menu');
    const navbarLangSelect = document.getElementById('ahb-lang-select');
    const navbarThemeBtn = document.querySelector('.nav-actions .theme-toggle-btn') || document.querySelector('.theme-toggle-btn');

    if (viewName === 'auth') {
      if (authView) authView.style.display = 'flex';
      if (appView) appView.style.display = 'none';
      if (userControls) userControls.style.display = 'none';
      if (profileMenu) profileMenu.style.display = 'none';
      if (navbarLangSelect) navbarLangSelect.style.display = 'inline-block';
      if (navbarThemeBtn) navbarThemeBtn.style.display = 'inline-flex';
    } else {
      if (authView) authView.style.display = 'none';
      if (appView) appView.style.display = 'grid';
      if (userControls) userControls.style.display = 'flex';
      if (profileMenu) profileMenu.style.display = 'inline-block';
      if (navbarLangSelect) navbarLangSelect.style.display = 'none';
      if (navbarThemeBtn) navbarThemeBtn.style.display = 'none';
    }
  }

  switchTab(tabName) {
    document.querySelectorAll('[data-tab]').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
    });

    document.querySelectorAll('.tab-content').forEach((pane) => {
      pane.classList.toggle('active', pane.id === `tab-${tabName}`);
    });
  }

  // 22. Instant Emergency Contact SOS & GPS Alert System
  async triggerEmergencySOS() {
    if (!this.activeVaultId) {
      this.showToast('Please select an active patient vault first.', 'error');
      return;
    }

    if (!confirm('🚨 BROADCAST EMERGENCY SOS ALERT?\n\nThis will immediately capture your current GPS coordinates and dispatch urgent alerts to all registered emergency contacts via SMS and WhatsApp.')) {
      return;
    }

    this.showToast('📍 Acquiring high-accuracy GPS coordinates...', 'info');

    const getGPSPosition = () => new Promise((resolve) => {
      if (!navigator.geolocation) {
        resolve(null);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy_meters: pos.coords.accuracy
        }),
        (err) => {
          console.warn('Geolocation failed or denied:', err);
          resolve(null);
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
      );
    });

    const coords = await getGPSPosition();

    try {
      const payload = {
        latitude: coords ? coords.latitude : null,
        longitude: coords ? coords.longitude : null,
        accuracy_meters: coords ? coords.accuracy_meters : null,
        trigger_source: 'one_tap_pwa'
      };

      const result = await this.apiRequest(`/vaults/${this.activeVaultId}/sos`, 'POST', payload);
      this.showToast(`🚨 SOS Broadcast Dispatched to ${result.contacts_notified_count || 0} Emergency Contacts!`, 'success');

      // Open WhatsApp Dispatch if links exist
      if (result.whatsapp_dispatch_links && result.whatsapp_dispatch_links.length > 0) {
        const firstContact = result.whatsapp_dispatch_links[0];
        if (confirm(`Open WhatsApp to send instant emergency broadcast to ${firstContact.contact_name} (${firstContact.relation})?`)) {
          window.open(firstContact.whatsapp_url, '_blank');
        }
      }
    } catch (err) {
      this.showToast(`Emergency SOS broadcast error: ${err.message}`, 'error');
    }
  }

  // 23. Live WebRTC Camera QR Scanner & Offline Triage System
  async openCameraScanner() {
    const modal = document.getElementById('camera-scanner-modal');
    if (modal) modal.style.display = 'flex';
    const statusEl = document.getElementById('scanner-status');
    if (statusEl) {
      statusEl.textContent = '⚡ Initializing camera stream...';
      statusEl.style.color = '#34d399';
    }
    await this.startCameraStream();
  }

  closeCameraScanner() {
    this.stopCameraStream();
    const modal = document.getElementById('camera-scanner-modal');
    if (modal) modal.style.display = 'none';
  }

  async flipCamera() {
    this.cameraFacing = (this.cameraFacing === 'environment') ? 'user' : 'environment';
    this.stopCameraStream();
    await this.startCameraStream();
  }

  async startCameraStream() {
    const video = document.getElementById('camera-stream');
    const statusEl = document.getElementById('scanner-status');
    if (!video) return;

    try {
      if (this.cameraStream) {
        this.cameraStream.getTracks().forEach(t => t.stop());
      }

      this.cameraStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: this.cameraFacing },
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      });

      video.srcObject = this.cameraStream;
      await video.play();

      this.isScanning = true;
      if (statusEl) {
        statusEl.textContent = '🟢 Camera live. Position QR pass in frame...';
      }
      this.scanCameraLoop();
    } catch (err) {
      console.warn('Camera access denied or unavailable:', err);
      if (statusEl) {
        statusEl.textContent = '⚠️ Camera unavailable. Use "Scan Image / Photo" below.';
        statusEl.style.color = '#fb7185';
      }
      this.showToast('Could not access camera. Please check permissions or upload a photo.', 'error');
    }
  }

  stopCameraStream() {
    this.isScanning = false;
    if (this.cameraStream) {
      this.cameraStream.getTracks().forEach(t => t.stop());
      this.cameraStream = null;
    }
    const video = document.getElementById('camera-stream');
    if (video) video.srcObject = null;
  }

  async scanCameraLoop() {
    if (!this.isScanning) return;
    const video = document.getElementById('camera-stream');
    const canvas = document.getElementById('camera-canvas');
    if (!video || !canvas || video.readyState !== video.HAVE_ENOUGH_DATA) {
      requestAnimationFrame(() => this.scanCameraLoop());
      return;
    }

    // Use native BarcodeDetector API if available (high-speed hardware decoding)
    if ('BarcodeDetector' in window) {
      try {
        const detector = new BarcodeDetector({ formats: ['qr_code'] });
        const barcodes = await detector.detect(video);
        if (barcodes.length > 0) {
          const rawVal = barcodes[0].rawValue;
          this.closeCameraScanner();
          await this.processScannedQrPayload(rawVal);
          return;
        }
      } catch (e) {}
    }

    // Fallback Canvas Frame Capture
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    if (this.isScanning) {
      setTimeout(() => requestAnimationFrame(() => this.scanCameraLoop()), 200);
    }
  }

  async handleQrPhotoUpload(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    this.showToast('Analyzing QR photo image...', 'info');
    const img = new Image();
    img.src = URL.createObjectURL(file);

    img.onload = async () => {
      if ('BarcodeDetector' in window) {
        try {
          const detector = new BarcodeDetector({ formats: ['qr_code'] });
          const barcodes = await detector.detect(img);
          if (barcodes.length > 0) {
            this.closeCameraScanner();
            await this.processScannedQrPayload(barcodes[0].rawValue);
            return;
          }
        } catch (err) {
          console.warn('BarcodeDetector photo scan error:', err);
        }
      }

      this.showToast('Could not automatically detect QR in photo. Please ensure clear lighting.', 'error');
    };
  }

  async processScannedQrPayload(rawText) {
    if (!rawText) return;
    const cleanText = rawText.trim();

    // 1. Check for Offline Cryptographic Pass (AHB1.<payload>.<sig>)
    if (cleanText.startsWith('AHB1.')) {
      try {
        this.showToast('🔐 Cryptographically verifying ECDSA-P256 offline seal...', 'info');
        const verifier = window.cryptoQRVerifier || new CryptoQRVerifier();
        const res = await verifier.verifySignedPayload(cleanText);

        this.showToast('✅ Cryptographic Digital Signature Authenticated!', 'success');
        this.renderEmergencyTriageModal(res.data);
      } catch (err) {
        console.error('Offline signature verification failed:', err);
        this.showToast(`⚠️ Signature Verification FAILED: ${err.message}`, 'error');
      }
      return;
    }

    // 2. Check for Online Emergency Web URL
    if (cleanText.includes('/offline_emergency.html') || cleanText.includes('/scan/')) {
      window.open(cleanText, '_blank');
      return;
    }

    // Generic QR Text display
    alert(`Scanned Content:\n\n${cleanText}`);
  }

  renderEmergencyTriageModal(profile) {
    const modal = document.getElementById('emergency-triage-modal');
    if (!modal) return;

    const nameEl = document.getElementById('triage-patient-name');
    const bloodEl = document.getElementById('triage-blood-badge');
    const algEl = document.getElementById('triage-allergies');
    const condEl = document.getElementById('triage-conditions');
    const medsEl = document.getElementById('triage-meds');
    const contactsEl = document.getElementById('triage-contacts-list');

    if (nameEl) nameEl.textContent = profile.name || 'Emergency Patient';
    if (bloodEl) bloodEl.textContent = profile.bg || 'Unknown';
    if (algEl) algEl.textContent = profile.alg || 'None recorded';
    if (condEl) condEl.textContent = profile.cnd || 'None recorded';
    if (medsEl) medsEl.textContent = profile.med || 'None recorded';

    if (contactsEl) {
      const contacts = [];
      if (profile.c1_name || profile.c1_ph) {
        contacts.push({ name: profile.c1_name, rel: profile.c1_rel || 'Primary Caregiver', phone: profile.c1_ph, isPrimary: true });
      }
      if (profile.c2_name || profile.c2_ph) {
        contacts.push({ name: profile.c2_name, rel: profile.c2_rel || 'Secondary Caregiver', phone: profile.c2_ph, isPrimary: false });
      }

      if (contacts.length === 0) {
        contactsEl.innerHTML = '<div class="text-muted" style="font-size: 0.85rem;">No emergency caregiver contacts provided in pass.</div>';
      } else {
        contactsEl.innerHTML = contacts.map(c => `
          <div class="glass-card" style="padding: 0.75rem 1rem; display: flex; justify-content: space-between; align-items: center; gap: 0.75rem;">
            <div>
              <div style="font-weight: 800; font-size: 0.92rem;">${c.name || 'Emergency Contact'} <span class="badge" style="font-size: 0.68rem;">${c.rel}</span></div>
              <div style="font-family: monospace; font-size: 0.85rem; color: var(--text-muted); margin-top: 0.15rem;">${c.phone || 'No phone'}</div>
            </div>
            ${c.phone ? `<a href="tel:${c.phone}" class="btn btn-sm ${c.isPrimary ? 'btn-danger' : 'btn-primary'}" style="font-weight: 800; font-size: 0.82rem; padding: 0.35rem 0.75rem;">📞 Call</a>` : ''}
          </div>
        `).join('');
      }
    }

    modal.style.display = 'flex';
  }

  closeEmergencyTriageModal() {
    const modal = document.getElementById('emergency-triage-modal');
    if (modal) modal.style.display = 'none';
  }
}

// Instantiate PWA client on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  window.healthBridgeApp = new HealthBridgePWA();
});
