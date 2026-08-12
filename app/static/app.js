/**
 * Aadhaar Health Bridge - Client-Side PWA Single Page Application (app.js)
 * Interacts asynchronously with RESTful /api/v1/ endpoints.
 * Provides offline caching, biometric/emergency pass generation, local RAG AI chat,
 * drag-and-drop report processing, and multilingual translation support.
 */

const API_BASE = '/api/v1';

class HealthBridgePWA {
  constructor() {
    this.token = localStorage.getItem('hb_token') || sessionStorage.getItem('hb_token') || null;
    this.currentUser = null;
    this.vaults = [];
    this.activeVaultId = null;
    this.activeVault = null;
    this.allMetrics = [];
    this.deferredInstallPrompt = null;

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
        this.renderDocuments(this.documents);
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

      this.vaults = await this.apiRequest('/vaults');

      if (this.vaults.length > 0) {
        this.activeVaultId = this.vaults[0].id;
      }

      this.populateVaultSelector();
      this.showView('app');
      await this.loadActiveVaultData();
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
  }

  async loadActiveVaultData() {
    if (!this.activeVaultId) return;

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
    const qrContainer = document.getElementById('emergency-qr-code');
    if (qrContainer && window.QRCode) {
      qrContainer.innerHTML = '';
      const token = vault.qr_token || vault.id;
      const emergencyUrl = `${window.location.origin}/static/offline_emergency.html?token=${token}`;
      new QRCode(qrContainer, {
        text: emergencyUrl,
        width: 170,
        height: 170,
        colorDark: '#0f766e',
        colorLight: '#ffffff'
      });

      const offlineCardLink = document.getElementById('offline-card-link');
      if (offlineCardLink) {
        offlineCardLink.href = emergencyUrl;
      }
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

      this.renderBiomarkers(this.allMetrics);
    } catch (err) {
      container.innerHTML = '<p style="color: #fb7185;">Failed to load health metrics.</p>';
    }
  }

  renderBiomarkers(metrics) {
    const container = document.getElementById('metrics-list');
    if (!container) return;

    if (!metrics || metrics.length === 0) {
      container.innerHTML = '<div class="glass-card" style="grid-column: 1/-1; text-align: center;"><p class="text-muted">No health metrics extracted yet. Upload a diagnostic lab report PDF to extract clinical observations.</p></div>';
      return;
    }

    container.innerHTML = metrics.map((m) => {
      let statusClass = 'normal';
      let statusText = 'Normal Range';

      const numVal = parseFloat(m.metric_value);
      if (!isNaN(numVal)) {
        if (m.metric_name.toLowerCase().includes('glucose') && numVal > 140) {
          statusClass = 'elevated';
          statusText = 'Elevated';
        } else if (m.metric_name.toLowerCase().includes('cholesterol') && numVal > 200) {
          statusClass = 'high';
          statusText = 'High';
        }
      }

      return `
        <div class="biomarker-card">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
              <h4 style="font-size: 0.95rem; font-weight: 700;">${m.metric_name}</h4>
              <small class="text-muted">${m.observed_date ? new Date(m.observed_date).toLocaleDateString() : 'Recent Observation'}</small>
            </div>
            <span class="biomarker-badge ${statusClass}">${statusText}</span>
          </div>
          <div style="display: flex; align-items: baseline; gap: 0.35rem; margin-top: 0.25rem;">
            <span style="font-size: 1.8rem; font-weight: 800; color: var(--primary-light);">${m.metric_value}</span>
            <span style="font-size: 0.85rem; color: var(--text-muted); font-weight: 600;">${m.metric_unit || ''}</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted); border-top: 1px solid var(--border-glow); padding-top: 0.4rem; display: flex; justify-content: space-between;">
            <span>HL7 Observation</span>
            <span>Ref: Standard</span>
          </div>
        </div>
      `;
    }).join('');
  }

  filterBiomarkers(query) {
    const q = (query || '').toLowerCase().trim();
    if (!q) {
      this.renderBiomarkers(this.allMetrics);
      return;
    }
    const filtered = this.allMetrics.filter((m) =>
      m.metric_name.toLowerCase().includes(q) ||
      (m.metric_unit && m.metric_unit.toLowerCase().includes(q))
    );
    this.renderBiomarkers(filtered);
  }

  // 14. Documents & Files Tabs
  async loadDocuments() {
    if (!this.activeVaultId) return;
    const container = document.getElementById('documents-list');
    const badge = document.getElementById('doc-count-badge');
    const filesBadge = document.getElementById('file-count-badge');

    try {
      const docs = await this.apiRequest(`/vaults/${this.activeVaultId}/documents`);
      this.documents = docs || [];
      this.allFiles = this.documents;

      if (badge) badge.textContent = this.documents.length;
      if (filesBadge) filesBadge.textContent = this.documents.length;

      this.renderDocuments(this.documents);
      this.renderFiles(this.documents);
    } catch (err) {
      if (container) container.innerHTML = '<p style="color: #fb7185;">Failed to load documents.</p>';
    }
  }

  renderDocuments(docs) {
    const container = document.getElementById('documents-list');
    if (!container) return;
    const t = (key) => (window.AHB_I18N ? window.AHB_I18N.t(key) : key);

    if (!docs || docs.length === 0) {
      container.innerHTML = '<div class="glass-card" style="grid-column: 1/-1; text-align: center;"><p class="text-muted">No medical documents uploaded yet. Upload your first PDF above.</p></div>';
      return;
    }

    container.innerHTML = docs.map((d) => {
      const cleanName = d.file_name || 'Medical Document';
      const cat = d.category || 'Clinical Report';
      return `
        <div class="glass-card" style="display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
              <span style="font-size: 1.6rem;">📄</span>
              <span class="badge" style="background: rgba(20, 184, 166, 0.15); color: #2dd4bf; border-radius: 6px; font-size: 0.72rem;">${cat}</span>
            </div>
            <h4 style="font-size: 0.95rem; font-weight: 700; word-break: break-word;">${cleanName}</h4>
            <small class="text-muted" style="display: block; margin-top: 0.35rem;">Uploaded: ${d.upload_date ? new Date(d.upload_date).toLocaleDateString() : 'Today'}</small>
          </div>
          <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid var(--border-glow); display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; gap: 0.35rem;">
              <button class="btn btn-sm btn-primary" style="padding: 0.2rem 0.5rem; font-size: 0.72rem;" onclick="window.healthBridgeApp.openPdfViewer(${d.id}, '${cleanName.replace(/'/g, "\\'")}', '${cat.replace(/'/g, "\\'")}')">👁️ Open</button>
              <button class="btn btn-sm" style="background: #25D366; color: white; border: none; font-size: 0.72rem; padding: 0.2rem 0.45rem;" onclick="window.healthBridgeApp.sharePdfWhatsApp(${d.id}, '${cleanName.replace(/'/g, "\\'")}', '${cat.replace(/'/g, "\\'")}', '${d.upload_date || ''}')">💬</button>
            </div>
            <button class="btn btn-sm btn-danger" style="padding: 0.2rem 0.5rem; font-size: 0.72rem;" onclick="window.healthBridgeApp.deleteDocument(${d.id})">Delete</button>
          </div>
        </div>
      `;
    }).join('');
  }

  renderFiles(docs) {
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
          <p class="text-muted" style="font-size: 0.85rem; max-width: 420px; margin: 0 auto 1.25rem;">Upload blood tests, imaging PDFs, discharge summaries, or prescriptions to view and share.</p>
          <button class="btn btn-primary btn-sm" onclick="window.healthBridgeApp.switchTab('documents')">+ ${t('documents.upload_btn')}</button>
        </div>
      `;
      return;
    }

    container.innerHTML = docs.map((d) => {
      const docUrl = `/api/v1/vaults/${this.activeVaultId}/documents/${d.id}/serve`;
      const dateStr = d.upload_date ? new Date(d.upload_date).toLocaleDateString() : 'Today';
      const cleanName = d.file_name || 'Medical Report';
      const cat = d.category || 'Clinical Report';

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
              <span style="font-size: 0.75rem; color: #34d399; font-weight: 700;">● Ready</span>
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
              <a href="${docUrl}" download class="btn btn-sm" style="flex: 1; text-align: center; font-size: 0.75rem; padding: 0.3rem 0.5rem;">
                📥 <span>${t('files.download')}</span>
              </a>
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

  openPdfViewer(docId, docName, docCategory) {
    if (!this.activeVaultId) return;
    const docUrl = `/api/v1/vaults/${this.activeVaultId}/documents/${docId}/serve`;

    const modal = document.getElementById('pdf-viewer-modal');
    const iframe = document.getElementById('pdf-viewer-iframe');
    const titleEl = document.getElementById('pdf-viewer-title');
    const catEl = document.getElementById('pdf-viewer-category');
    const newtabBtn = document.getElementById('pdf-viewer-newtab');
    const downloadBtn = document.getElementById('pdf-viewer-download');
    const whatsappBtn = document.getElementById('pdf-viewer-whatsapp');

    if (titleEl) titleEl.textContent = docName || 'Medical Report PDF';
    if (catEl) catEl.textContent = docCategory || 'Diagnostic Report';
    if (newtabBtn) newtabBtn.href = docUrl;
    if (downloadBtn) downloadBtn.href = docUrl;
    if (whatsappBtn) {
      whatsappBtn.onclick = () => this.sharePdfWhatsApp(docId, docName, docCategory, new Date().toISOString());
    }
    if (iframe) iframe.src = docUrl;

    if (modal) modal.style.display = 'flex';
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

  // 15. Document Upload
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
      await this.apiRequest(`/vaults/${this.activeVaultId}/documents`, {
        method: 'POST',
        body: formData
      });

      this.showToast(`Document "${file.name}" indexed successfully!`, 'success');
      if (statusEl) {
        statusEl.textContent = '✅ Document processed and vector indexed into local RAG!';
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
      this.showToast('Document and associated biomarkers deleted.', 'info');
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
    const relation = document.getElementById('member-relation').value;
    const bloodGroup = document.getElementById('member-blood-group').value;
    const phone = document.getElementById('member-phone').value.trim();

    try {
      await this.apiRequest('/vaults/family', {
        method: 'POST',
        body: JSON.stringify({
          full_name: name,
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

    if (viewName === 'auth') {
      if (authView) authView.style.display = 'flex';
      if (appView) appView.style.display = 'none';
      if (userControls) userControls.style.display = 'none';
    } else {
      if (authView) authView.style.display = 'none';
      if (appView) appView.style.display = 'grid';
      if (userControls) userControls.style.display = 'flex';
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
}

// Instantiate PWA client on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  window.healthBridgeApp = new HealthBridgePWA();
});
