/**
 * Aadhaar Health Bridge - Client-Side PWA Single Page Application (app.js)
 * Interacts asynchronously with RESTful /api/v1/ endpoints.
 */

const API_BASE = '/api/v1';

class HealthBridgePWA {
  constructor() {
    this.token = localStorage.getItem('hb_token') || sessionStorage.getItem('hb_token') || null;
    this.currentUser = null;
    this.vaults = [];
    this.activeVaultId = null;
    this.deferredInstallPrompt = null;

    this.init();
  }

  async init() {
    this.bindEvents();
    this.registerServiceWorker();
    this.handleInstallPrompt();

    if (this.token) {
      await this.loadUserProfile();
    } else {
      this.showView('auth');
    }
  }

  // 1. Service Worker Registration
  registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
          .then((reg) => console.log('[PWA] Service Worker registered with scope:', reg.scope))
          .catch((err) => console.warn('[PWA] Service Worker registration failed:', err));
      });
    }
  }

  // 2. PWA Install Prompt Listener
  handleInstallPrompt() {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      this.deferredInstallPrompt = e;
      const installBtn = document.getElementById('pwa-install-btn');
      if (installBtn) installBtn.style.display = 'flex';
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

  // 3. Event Listeners
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

    // Logout
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) logoutBtn.addEventListener('click', () => this.handleLogout());

    // Export FHIR Bundle
    const exportFhirBtn = document.getElementById('export-fhir-btn');
    if (exportFhirBtn) exportFhirBtn.addEventListener('click', () => this.exportFHIRBundle());
  }

  // 4. API Request Helper with JWT Auth
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

  // 5. Auth Handlers
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
      await this.loadUserProfile();
    } catch (err) {
      if (errorEl) errorEl.textContent = err.message || 'Invalid username or password.';
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
    }
  }

  handleLogout() {
    this.token = null;
    this.currentUser = null;
    this.vaults = [];
    this.activeVaultId = null;
    localStorage.removeItem('hb_token');
    sessionStorage.removeItem('hb_token');

    // Secure Service Worker Cache Purge
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({ action: 'PURGE_SECURE_CACHE' });
    }

    this.showView('auth');
  }

  // 6. Profile & Vault Loading
  async loadUserProfile() {
    try {
      this.currentUser = await this.apiRequest('/auth/me');
      this.vaults = await this.apiRequest('/vaults');

      if (this.vaults.length > 0) {
        this.activeVaultId = this.vaults[0].id;
      }

      this.populateVaultSelector();
      this.showView('app');
      this.loadActiveVaultData();
    } catch (err) {
      console.warn('Failed to load profile:', err);
      this.handleLogout();
    }
  }

  populateVaultSelector() {
    const selector = document.getElementById('vault-select');
    if (!selector) return;
    selector.innerHTML = '';
    this.vaults.forEach((v) => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = `${v.full_name || 'Patient'} (${v.relation || 'Self'})`;
      selector.appendChild(opt);
    });
    if (this.activeVaultId) selector.value = this.activeVaultId;
  }

  async loadActiveVaultData() {
    if (!this.activeVaultId) return;

    try {
      const vault = await this.apiRequest(`/vaults/${this.activeVaultId}`);
      this.renderVaultOverview(vault);
      this.cacheEmergencyData(vault);

      // Load tabs in parallel
      this.loadMetrics();
      this.loadDocuments();
      this.loadAuditTrail();
    } catch (err) {
      console.error('Failed to load vault data:', err);
    }
  }

  // 7. Render Views
  renderVaultOverview(vault) {
    const nameEl = document.getElementById('patient-name');
    const relationEl = document.getElementById('patient-relation');
    const bloodEl = document.getElementById('patient-blood-group');
    const emergencyEl = document.getElementById('patient-emergency-contact');

    if (nameEl) nameEl.textContent = vault.full_name || 'N/A';
    if (relationEl) relationEl.textContent = vault.relation || 'Self';
    if (bloodEl) bloodEl.textContent = vault.blood_group || 'O+';
    if (emergencyEl) emergencyEl.textContent = vault.emergency_contact || 'N/A';

    // Render QR Code for Emergency Access
    const qrContainer = document.getElementById('emergency-qr-code');
    if (qrContainer && window.QRCode) {
      qrContainer.innerHTML = '';
      const emergencyUrl = `${window.location.origin}/static/offline_emergency.html?v=${vault.id}`;
      new QRCode(qrContainer, {
        text: emergencyUrl,
        width: 160,
        height: 160,
        colorDark: '#0f766e',
        colorLight: '#ffffff'
      });
    }
  }

  // 8. Offline Emergency Caching
  cacheEmergencyData(vault) {
    try {
      localStorage.setItem(`emergency_vault_${vault.id}`, JSON.stringify({
        id: vault.id,
        name: vault.full_name,
        blood_group: vault.blood_group,
        emergency_contact: vault.emergency_contact,
        allergies: vault.allergies,
        conditions: vault.conditions,
        cached_at: new Date().toISOString()
      }));
    } catch (e) {
      console.warn('Emergency caching error:', e);
    }
  }

  // 9. Metrics Tab
  async loadMetrics() {
    if (!this.activeVaultId) return;
    const container = document.getElementById('metrics-list');
    if (!container) return;

    try {
      const metrics = await this.apiRequest(`/vaults/${this.activeVaultId}/metrics`);
      if (!metrics || metrics.length === 0) {
        container.innerHTML = '<p class="text-muted">No health metrics extracted yet. Upload a lab report PDF.</p>';
        return;
      }

      container.innerHTML = metrics.map((m) => `
        <div class="metric-card">
          <div class="metric-header">
            <span class="metric-name">${m.metric_name}</span>
            <span class="metric-date">${m.observed_date ? new Date(m.observed_date).toLocaleDateString() : 'Recent'}</span>
          </div>
          <div class="metric-body">
            <span class="metric-value">${m.metric_value}</span>
            <span class="metric-unit">${m.metric_unit || ''}</span>
          </div>
        </div>
      `).join('');
    } catch (err) {
      container.innerHTML = '<p class="text-danger">Failed to load health metrics.</p>';
    }
  }

  // 10. Documents Tab
  async loadDocuments() {
    if (!this.activeVaultId) return;
    const container = document.getElementById('documents-list');
    if (!container) return;

    try {
      const docs = await this.apiRequest(`/vaults/${this.activeVaultId}/documents`);
      if (!docs || docs.length === 0) {
        container.innerHTML = '<p class="text-muted">No medical documents uploaded yet.</p>';
        return;
      }

      container.innerHTML = docs.map((d) => `
        <div class="doc-card">
          <div class="doc-icon">📄</div>
          <div class="doc-info">
            <h4>${d.file_name || 'Medical Report'}</h4>
            <span class="badge">${d.category || 'General'}</span>
            <small class="text-muted">${d.upload_date ? new Date(d.upload_date).toLocaleDateString() : ''}</small>
          </div>
        </div>
      `).join('');
    } catch (err) {
      container.innerHTML = '<p class="text-danger">Failed to load documents.</p>';
    }
  }

  // 11. Document Upload
  async handleDocUpload(e) {
    e.preventDefault();
    if (!this.activeVaultId) return;

    const fileInput = document.getElementById('doc-file-input');
    const categorySelect = document.getElementById('doc-category-select');
    const statusEl = document.getElementById('upload-status');

    if (!fileInput || !fileInput.files[0]) return;
    const file = fileInput.files[0];

    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', categorySelect ? categorySelect.value : 'Diagnostic Lab Report');
    formData.append('file_name', file.name);

    if (statusEl) {
      statusEl.textContent = 'Processing PDF with Local Python Engine...';
      statusEl.className = 'status-msg loading';
    }

    try {
      await this.apiRequest(`/vaults/${this.activeVaultId}/documents`, {
        method: 'POST',
        body: formData
      });

      if (statusEl) {
        statusEl.textContent = 'Document successfully processed and indexed!';
        statusEl.className = 'status-msg success';
      }
      fileInput.value = '';
      this.loadDocuments();
      this.loadMetrics();
    } catch (err) {
      if (statusEl) {
        statusEl.textContent = `Upload failed: ${err.message}`;
        statusEl.className = 'status-msg error';
      }
    }
  }

  // 12. Local RAG Chat Assistant
  async handleChatSubmit(e) {
    e.preventDefault();
    if (!this.activeVaultId) return;

    const input = document.getElementById('chat-input');
    const messageContainer = document.getElementById('chat-messages');
    const query = input.value.trim();
    if (!query) return;

    // Append User Message
    this.appendChatMessage('user', query);
    input.value = '';

    // Append Loading Assistant Placeholder
    const loadingId = this.appendChatMessage('assistant', 'Analyzing medical records with Local RAG...', true);

    try {
      const res = await this.apiRequest(`/vaults/${this.activeVaultId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ query })
      });

      this.updateChatMessage(loadingId, res.answer, res.ai_source, res.source_attributions);
    } catch (err) {
      this.updateChatMessage(loadingId, `Error: ${err.message}`, 'Error');
    }
  }

  appendChatMessage(role, text, isLoading = false) {
    const container = document.getElementById('chat-messages');
    if (!container) return null;

    const id = `msg-${Date.now()}`;
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
          <small>Verified Sources:</small>
          ${attributions.filter(a => a.grounded).map(a => `
            <span class="attr-tag">📑 ${a.file_name} (Chunk #${a.chunk_index})</span>
          `).join('')}
        </div>
      `;
    }

    el.innerHTML = `
      <div class="msg-content">${text}</div>
      ${aiSource ? `<div class="msg-footer"><small class="ai-source-badge">${aiSource}</small></div>` : ''}
      ${attrHtml}
    `;
    const container = document.getElementById('chat-messages');
    if (container) container.scrollTop = container.scrollHeight;
  }

  // 13. Audit Trail
  async loadAuditTrail() {
    if (!this.activeVaultId) return;
    const container = document.getElementById('audit-list');
    if (!container) return;

    try {
      const logs = await this.apiRequest(`/vaults/${this.activeVaultId}/audit-trail`);
      if (!logs || logs.length === 0) {
        container.innerHTML = '<p class="text-muted">No audit logs recorded yet.</p>';
        return;
      }

      container.innerHTML = logs.map((l) => `
        <div class="audit-row">
          <span class="audit-action badge">${l.action}</span>
          <span class="audit-details">${l.details || l.event_type}</span>
          <small class="text-muted">${l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : ''}</small>
        </div>
      `).join('');
    } catch (err) {
      container.innerHTML = '<p class="text-muted">Audit logs ready.</p>';
    }
  }

  // 14. Export FHIR Bundle
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
    } catch (err) {
      alert(`FHIR Export error: ${err.message}`);
    }
  }

  // 15. View / Tab Management
  showView(viewName) {
    const authView = document.getElementById('auth-view');
    const appView = document.getElementById('app-view');

    if (viewName === 'auth') {
      if (authView) authView.style.display = 'flex';
      if (appView) appView.style.display = 'none';
    } else {
      if (authView) authView.style.display = 'none';
      if (appView) appView.style.display = 'grid';
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
