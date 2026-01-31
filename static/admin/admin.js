/**
 * Research Agent Admin Panel JavaScript
 */

// State
let authToken = null;
let currentSettings = null;

// Available agents for priority selection
const AVAILABLE_AGENTS = ['claude', 'gemini', 'perplexity', 'ollama'];

// Skill descriptions
const SKILL_DESCRIPTIONS = {
    'synthesis': 'Research Synthesis',
    'document-analysis': 'Document Analysis',
    'web-search': 'Web Search',
    'cross-validate': 'Cross Validation',
    'general-query': 'General Query'
};

// =============================================================================
// API Functions
// =============================================================================

async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    const response = await fetch(`/admin/api${endpoint}`, {
        ...options,
        headers
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || 'Request failed');
    }

    return data;
}

// =============================================================================
// Authentication
// =============================================================================

async function login(password) {
    try {
        const data = await apiRequest('/login', {
            method: 'POST',
            body: JSON.stringify({ password })
        });

        if (data.success) {
            authToken = data.token;
            localStorage.setItem('adminToken', authToken);

            showDashboard();

            if (data.requires_password_change) {
                document.getElementById('password-warning').classList.remove('hidden');
            }

            await loadAllData();
            showToast('Login successful', 'success');
        } else {
            showToast(data.message || 'Login failed', 'error');
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function logout() {
    try {
        await apiRequest('/logout', { method: 'POST' });
    } catch (error) {
        console.error('Logout error:', error);
    }

    authToken = null;
    localStorage.removeItem('adminToken');
    showLogin();
}

async function checkSession() {
    const token = localStorage.getItem('adminToken');
    if (!token) {
        showLogin();
        return;
    }

    authToken = token;

    try {
        const data = await apiRequest('/session');
        if (data.valid) {
            showDashboard();
            if (data.requires_password_change) {
                document.getElementById('password-warning').classList.remove('hidden');
            }
            await loadAllData();
        } else {
            showLogin();
        }
    } catch (error) {
        authToken = null;
        localStorage.removeItem('adminToken');
        showLogin();
    }
}

// =============================================================================
// View Management
// =============================================================================

function showLogin() {
    document.getElementById('login-view').classList.remove('hidden');
    document.getElementById('dashboard-view').classList.add('hidden');
}

function showDashboard() {
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('dashboard-view').classList.remove('hidden');
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update tab panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.toggle('hidden', panel.id !== `tab-${tabName}`);
        panel.classList.toggle('active', panel.id === `tab-${tabName}`);
    });
}

// =============================================================================
// Data Loading
// =============================================================================

async function loadAllData() {
    await Promise.all([
        loadStatus(),
        loadSettings()
    ]);
}

async function loadStatus() {
    try {
        const status = await apiRequest('/status');
        renderStatus(status);
    } catch (error) {
        showToast('Failed to load status: ' + error.message, 'error');
    }
}

async function loadSettings() {
    try {
        currentSettings = await apiRequest('/settings');
        renderPriorities(currentSettings.priorities);
        renderOllamaSettings(currentSettings.ollama);
        document.getElementById('session-timeout').value = currentSettings.session_timeout_hours || 24;
    } catch (error) {
        showToast('Failed to load settings: ' + error.message, 'error');
    }
}

// =============================================================================
// Rendering Functions
// =============================================================================

function renderStatus(status) {
    // Admin status
    const adminHtml = `
        <div class="status-item">
            <span>Active Sessions</span>
            <span>${status.admin?.active_sessions || 0}</span>
        </div>
        <div class="status-item">
            <span>Default Password</span>
            <span class="status-badge ${status.admin?.default_password_in_use ? 'warning' : 'healthy'}">
                ${status.admin?.default_password_in_use ? 'In Use' : 'Changed'}
            </span>
        </div>
    `;
    document.getElementById('admin-status').innerHTML = adminHtml;

    // Agent status
    let agentsHtml = '';
    for (const [agentId, agentStatus] of Object.entries(status.agents || {})) {
        const statusClass = agentStatus.status === 'healthy' ? 'healthy' :
                           agentStatus.status === 'error' ? 'error' : 'warning';
        agentsHtml += `
            <div class="status-item">
                <span>${agentId}</span>
                <span class="status-badge ${statusClass}">${agentStatus.status || 'unknown'}</span>
            </div>
        `;
    }
    document.getElementById('agents-status').innerHTML = agentsHtml || '<p>No agents registered</p>';
}

function renderPriorities(priorities) {
    const container = document.getElementById('priorities-form');
    let html = '';

    for (const [skillId, config] of Object.entries(priorities)) {
        const skillName = SKILL_DESCRIPTIONS[skillId] || skillId;

        html += `
            <div class="priority-item" data-skill="${skillId}">
                <h4>${skillName}</h4>
                <div class="priority-row">
                    <label>Primary:</label>
                    <select class="primary-select" data-skill="${skillId}">
                        ${AVAILABLE_AGENTS.map(agent =>
                            `<option value="${agent}" ${config.primary === agent ? 'selected' : ''}>${agent}</option>`
                        ).join('')}
                    </select>
                </div>
                <div class="priority-row">
                    <label>Fallbacks:</label>
                    <div class="fallback-list" data-skill="${skillId}">
                        ${(config.fallbacks || []).map(agent =>
                            `<span class="fallback-tag">${agent}<button onclick="removeFallback('${skillId}', '${agent}')">&times;</button></span>`
                        ).join('')}
                    </div>
                </div>
                <div class="priority-row">
                    <label>Add:</label>
                    <select class="add-fallback-select" data-skill="${skillId}" onchange="addFallback('${skillId}', this.value); this.value='';">
                        <option value="">Select fallback...</option>
                        ${AVAILABLE_AGENTS.filter(a => a !== config.primary && !config.fallbacks?.includes(a)).map(agent =>
                            `<option value="${agent}">${agent}</option>`
                        ).join('')}
                    </select>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

function renderOllamaSettings(ollama) {
    document.getElementById('ollama-enabled').checked = ollama.enabled;
    document.getElementById('ollama-url').value = ollama.base_url || 'http://localhost:11434/v1';
    document.getElementById('ollama-model').value = ollama.model || 'llama3.1';

    // Update connection status
    updateOllamaStatus();
}

async function updateOllamaStatus() {
    try {
        const status = await apiRequest('/status/ollama');
        const statusEl = document.getElementById('ollama-connection-status');
        const boxEl = document.getElementById('ollama-status-box');

        if (status.enabled) {
            if (status.connected) {
                statusEl.textContent = 'Connected to Ollama';
                boxEl.style.borderColor = 'var(--success-color)';
                boxEl.style.background = '#d1fae5';
            } else {
                statusEl.textContent = 'Ollama enabled but not connected';
                boxEl.style.borderColor = 'var(--warning-color)';
                boxEl.style.background = '#fef3c7';
            }
        } else {
            statusEl.textContent = 'Ollama is disabled';
            boxEl.style.borderColor = 'var(--border-color)';
            boxEl.style.background = 'var(--surface)';
        }
    } catch (error) {
        document.getElementById('ollama-connection-status').textContent = 'Error checking status';
    }
}

// =============================================================================
// Priority Management
// =============================================================================

function addFallback(skillId, agent) {
    if (!agent) return;

    const priorities = getCurrentPriorities();
    if (!priorities[skillId].fallbacks) {
        priorities[skillId].fallbacks = [];
    }

    if (!priorities[skillId].fallbacks.includes(agent)) {
        priorities[skillId].fallbacks.push(agent);
        renderPriorities(priorities);
    }
}

function removeFallback(skillId, agent) {
    const priorities = getCurrentPriorities();
    priorities[skillId].fallbacks = (priorities[skillId].fallbacks || []).filter(a => a !== agent);
    renderPriorities(priorities);
}

function getCurrentPriorities() {
    const priorities = {};

    document.querySelectorAll('.priority-item').forEach(item => {
        const skillId = item.dataset.skill;
        const primary = item.querySelector('.primary-select').value;
        const fallbacks = [];

        item.querySelectorAll('.fallback-tag').forEach(tag => {
            const agent = tag.textContent.replace('×', '').trim();
            fallbacks.push(agent);
        });

        priorities[skillId] = { primary, fallbacks };
    });

    return priorities;
}

async function savePriorities() {
    try {
        const priorities = getCurrentPriorities();
        await apiRequest('/settings/priorities', {
            method: 'PUT',
            body: JSON.stringify({ priorities })
        });
        showToast('Priorities saved successfully', 'success');
    } catch (error) {
        showToast('Failed to save priorities: ' + error.message, 'error');
    }
}

async function resetPriorities() {
    if (!confirm('Reset all priorities to defaults?')) return;

    const defaults = {
        'synthesis': { primary: 'claude', fallbacks: ['ollama'] },
        'document-analysis': { primary: 'claude', fallbacks: ['ollama', 'gemini'] },
        'web-search': { primary: 'perplexity', fallbacks: [] },
        'cross-validate': { primary: 'gemini', fallbacks: ['claude', 'ollama'] },
        'general-query': { primary: 'claude', fallbacks: ['ollama'] }
    };

    try {
        await apiRequest('/settings/priorities', {
            method: 'PUT',
            body: JSON.stringify({ priorities: defaults })
        });
        renderPriorities(defaults);
        showToast('Priorities reset to defaults', 'success');
    } catch (error) {
        showToast('Failed to reset priorities: ' + error.message, 'error');
    }
}

// =============================================================================
// Ollama Settings
// =============================================================================

async function saveOllamaSettings(event) {
    event.preventDefault();

    const config = {
        enabled: document.getElementById('ollama-enabled').checked,
        baseUrl: document.getElementById('ollama-url').value,
        model: document.getElementById('ollama-model').value
    };

    try {
        const result = await apiRequest('/settings/ollama', {
            method: 'PUT',
            body: JSON.stringify(config)
        });
        showToast(result.message + (result.note ? ' ' + result.note : ''), 'success');
        updateOllamaStatus();
    } catch (error) {
        showToast('Failed to save Ollama settings: ' + error.message, 'error');
    }
}

async function testOllamaConnection() {
    showToast('Testing Ollama connection...', 'info');

    try {
        const status = await apiRequest('/status/ollama');
        if (status.connected) {
            showToast('Ollama connection successful!', 'success');
        } else {
            showToast('Ollama is not responding. Make sure Ollama is running.', 'error');
        }
    } catch (error) {
        showToast('Connection test failed: ' + error.message, 'error');
    }
}

// =============================================================================
// Security Settings
// =============================================================================

async function changePassword(event) {
    event.preventDefault();

    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (newPassword !== confirmPassword) {
        showToast('Passwords do not match', 'error');
        return;
    }

    if (newPassword.length < 8) {
        showToast('Password must be at least 8 characters', 'error');
        return;
    }

    try {
        await apiRequest('/settings/password', {
            method: 'PUT',
            body: JSON.stringify({
                currentPassword,
                newPassword
            })
        });

        showToast('Password changed successfully', 'success');
        document.getElementById('password-warning').classList.add('hidden');
        document.getElementById('password-form').reset();
    } catch (error) {
        showToast('Failed to change password: ' + error.message, 'error');
    }
}

async function updateSessionTimeout(event) {
    event.preventDefault();

    const timeoutHours = parseInt(document.getElementById('session-timeout').value);

    try {
        await apiRequest('/settings/session-timeout', {
            method: 'PUT',
            body: JSON.stringify({ timeoutHours })
        });
        showToast(`Session timeout updated to ${timeoutHours} hours`, 'success');
    } catch (error) {
        showToast('Failed to update session timeout: ' + error.message, 'error');
    }
}

// =============================================================================
// Toast Notifications
// =============================================================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// =============================================================================
// Event Listeners
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Login form
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = document.getElementById('password').value;
        await login(password);
    });

    // Logout button
    document.getElementById('logout-btn').addEventListener('click', logout);

    // Tab navigation
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Refresh status button
    document.getElementById('refresh-status').addEventListener('click', loadStatus);

    // Priority buttons
    document.getElementById('save-priorities').addEventListener('click', savePriorities);
    document.getElementById('reset-priorities').addEventListener('click', resetPriorities);

    // Ollama form
    document.getElementById('ollama-form').addEventListener('submit', saveOllamaSettings);
    document.getElementById('test-ollama').addEventListener('click', testOllamaConnection);

    // Security forms
    document.getElementById('password-form').addEventListener('submit', changePassword);
    document.getElementById('session-form').addEventListener('submit', updateSessionTimeout);

    // Check session on load
    checkSession();
});
