/**
 * ResearchAgent - Frontend Application
 * Handles UI interactions, theme switching, downloads, and research workflow execution
 */

// =============================================================================
// State Management
// =============================================================================

const state = {
    isResearching: false,
    currentWorkflowId: null,
    currentResults: null,
    theme: 'dark'
};

// =============================================================================
// DOM Elements
// =============================================================================

const elements = {
    // Theme
    themeToggle: null,

    // Query
    queryInput: null,
    searchBtn: null,
    depthSelect: null,
    formatSelect: null,
    streamCheck: null,

    // Progress
    progressSection: null,
    progressBar: null,
    progressPercent: null,
    progressText: null,

    // Log
    logContainer: null,

    // Results
    resultsSection: null,
    resultsMeta: null,
    resultsContent: null,

    // Toast
    toast: null,
    toastMessage: null,

    // Agents
    agents: {}
};

// =============================================================================
// Initialization
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initElements();
    initTheme();
    initEventListeners();
    checkHealth();
});

function initElements() {
    elements.themeToggle = document.getElementById('theme-toggle');
    elements.queryInput = document.getElementById('query-input');
    elements.searchBtn = document.getElementById('search-btn');
    elements.depthSelect = document.getElementById('depth-select');
    elements.formatSelect = document.getElementById('format-select');
    elements.streamCheck = document.getElementById('stream-check');
    elements.progressSection = document.getElementById('progress-section');
    elements.progressBar = document.getElementById('progress-bar');
    elements.progressPercent = document.getElementById('progress-percent');
    elements.progressText = document.getElementById('progress-text');
    elements.logContainer = document.getElementById('log-container');
    elements.resultsSection = document.getElementById('results-section');
    elements.resultsMeta = document.getElementById('results-meta');
    elements.resultsContent = document.getElementById('results-content');
    elements.toast = document.getElementById('toast');
    elements.toastMessage = document.getElementById('toast-message');

    // Agent elements
    elements.agents = {
        perplexity: document.getElementById('agent-perplexity'),
        claude: document.getElementById('agent-claude'),
        openai: document.getElementById('agent-openai')
    };
}

function initEventListeners() {
    // Theme toggle
    elements.themeToggle?.addEventListener('click', toggleTheme);

    // Query input - Enter key
    elements.queryInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            executeResearch();
        }
    });

    // Auto-resize textarea
    elements.queryInput?.addEventListener('input', () => {
        elements.queryInput.style.height = 'auto';
        elements.queryInput.style.height = Math.min(elements.queryInput.scrollHeight, 200) + 'px';
    });
}

// =============================================================================
// Theme Management
// =============================================================================

function initTheme() {
    // Check for saved theme preference or system preference
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    state.theme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
    applyTheme(state.theme);

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            state.theme = e.matches ? 'dark' : 'light';
            applyTheme(state.theme);
        }
    });
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(state.theme);
    localStorage.setItem('theme', state.theme);
    showToast(`Switched to ${state.theme} mode`);
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
}

// =============================================================================
// Research Execution
// =============================================================================

async function executeResearch() {
    const query = elements.queryInput?.value.trim();

    if (!query) {
        showToast('Please enter a research query', 'error');
        elements.queryInput?.focus();
        return;
    }

    if (state.isResearching) {
        return;
    }

    // Reset UI and start
    resetUI();
    setResearchingState(true);

    const depth = elements.depthSelect?.value || 'standard';
    const outputFormat = elements.formatSelect?.value || 'report';
    const useStreaming = elements.streamCheck?.checked ?? true;

    try {
        if (useStreaming) {
            await executeStreamingResearch(query, depth, outputFormat);
        } else {
            await executeDirectResearch(query, depth, outputFormat);
        }
    } catch (error) {
        console.error('Research failed:', error);
        showError(error.message);
    } finally {
        setResearchingState(false);
    }
}

async function executeStreamingResearch(query, depth, outputFormat) {
    logMessage('Orchestrator', 'Initializing research workflow...', 'orchestrator');
    updateProgress(5, 'Initializing agents...');

    const response = await fetch('/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query,
            depth,
            output_format: outputFormat,
            stream: true
        })
    });

    if (!response.ok) {
        throw new Error(`Research request failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('data:')) {
                const data = line.slice(5).trim();
                if (data) {
                    try {
                        handleStreamEvent(JSON.parse(data));
                    } catch (e) {
                        handleStreamMessage(data);
                    }
                }
            }
        }
    }
}

function handleStreamEvent(event) {
    const { status, progress, message, error } = event;

    if (error) {
        showError(error);
        return;
    }

    if (progress !== undefined) {
        const percent = Math.round(progress * 100);
        updateProgress(percent, message || `Processing... ${percent}%`);
    }

    if (message) {
        parseMessageForAgentActivity(message);

        if (status === 'completed') {
            showResults({
                query: elements.queryInput?.value || '',
                report: message,
                success: true
            });
        }
    }
}

function handleStreamMessage(data) {
    if (data.includes('progress')) {
        const progressMatch = data.match(/progress['":\s]+(\d+\.?\d*)/);
        if (progressMatch) {
            const progress = parseFloat(progressMatch[1]);
            updateProgress(Math.round(progress * 100));
        }
    }

    if (data.includes('message')) {
        const messageMatch = data.match(/message['":\s]+'([^']+)'/);
        if (messageMatch) {
            updateProgress(null, messageMatch[1]);
            parseMessageForAgentActivity(messageMatch[1]);
        }
    }
}

function parseMessageForAgentActivity(message) {
    const lowerMsg = message.toLowerCase();

    if (lowerMsg.includes('perplexity') || lowerMsg.includes('search')) {
        setAgentStatus('perplexity', 'working');
        logMessage('Perplexity', message, 'perplexity');
    }

    if (lowerMsg.includes('claude') || lowerMsg.includes('analyz')) {
        setAgentStatus('claude', 'working');
        logMessage('Claude', message, 'claude');
    }

    if (lowerMsg.includes('openai') || lowerMsg.includes('gpt') || lowerMsg.includes('validat')) {
        setAgentStatus('openai', 'working');
        logMessage('OpenAI', message, 'openai');
    }

    if (lowerMsg.includes('orchestrator') || lowerMsg.includes('synthesi')) {
        logMessage('Orchestrator', message, 'orchestrator');
    }
}

async function executeDirectResearch(query, depth, outputFormat) {
    logMessage('Orchestrator', 'Starting research workflow...', 'orchestrator');
    updateProgress(10, 'Initializing...');

    // Simulate agent activity for non-streaming mode
    const animations = [
        { delay: 500, action: () => setAgentStatus('perplexity', 'working') },
        { delay: 1000, action: () => updateProgress(25, 'Searching web sources...') },
        { delay: 2000, action: () => logMessage('Perplexity', 'Gathering information from multiple sources...', 'perplexity') },
        { delay: 3000, action: () => setAgentStatus('claude', 'working') },
        { delay: 3500, action: () => updateProgress(50, 'Analyzing findings...') },
        { delay: 4500, action: () => logMessage('Claude', 'Processing and analyzing research data...', 'claude') },
        { delay: 5500, action: () => setAgentStatus('openai', 'working') },
        { delay: 6000, action: () => updateProgress(75, 'Validating results...') },
        { delay: 7000, action: () => logMessage('OpenAI', 'Cross-referencing and validating findings...', 'openai') }
    ];

    animations.forEach(({ delay, action }) => setTimeout(action, delay));

    const response = await fetch('/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query,
            depth,
            output_format: outputFormat,
            stream: false
        })
    });

    if (!response.ok) {
        throw new Error(`Research request failed: ${response.status}`);
    }

    const result = await response.json();

    updateProgress(100, 'Research complete!');

    // Reset all agents to active/complete state
    Object.keys(elements.agents).forEach(agent => {
        setAgentStatus(agent, 'active');
    });

    if (result.success) {
        showResults(result);
    } else {
        showError(result.error || 'Research failed');
    }
}

// =============================================================================
// UI Updates
// =============================================================================

function updateProgress(percent, text) {
    elements.progressSection?.classList.add('visible');

    if (percent !== null && elements.progressBar) {
        elements.progressBar.style.width = `${percent}%`;
        if (elements.progressPercent) {
            elements.progressPercent.textContent = `${percent}%`;
        }
    }

    if (text && elements.progressText) {
        elements.progressText.textContent = text;
    }
}

function setAgentStatus(agentId, status) {
    const agentEl = elements.agents[agentId];
    if (!agentEl) return;

    // Remove all status classes
    agentEl.classList.remove('active', 'working', 'error');

    // Add new status class
    if (status) {
        agentEl.classList.add(status);
    }
}

function logMessage(sender, message, senderClass) {
    if (!elements.logContainer) return;

    // Remove empty state if present
    const emptyState = elements.logContainer.querySelector('.log-empty');
    if (emptyState) {
        emptyState.remove();
    }

    const entry = document.createElement('div');
    entry.className = 'log-entry';

    const timestamp = new Date().toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    entry.innerHTML = `
        <span class="log-timestamp">[${timestamp}]</span>
        <span class="log-sender ${senderClass}">${sender}:</span>
        <span class="log-message">${truncateMessage(message, 120)}</span>
    `;

    elements.logContainer.appendChild(entry);
    elements.logContainer.scrollTop = elements.logContainer.scrollHeight;
}

function truncateMessage(message, maxLength) {
    if (!message || message.length <= maxLength) return message;
    return message.substring(0, maxLength) + '...';
}

function showResults(result) {
    state.currentResults = result;

    elements.resultsSection?.classList.add('visible');

    // Update meta information
    if (elements.resultsMeta) {
        const metaItems = [
            result.query ? `<span class="meta-tag"><strong>Query:</strong> ${truncateMessage(result.query, 50)}</span>` : '',
            result.sources_count ? `<span class="meta-tag"><strong>Sources:</strong> ${result.sources_count}</span>` : '',
            result.duration_seconds ? `<span class="meta-tag"><strong>Duration:</strong> ${result.duration_seconds.toFixed(1)}s</span>` : ''
        ].filter(Boolean);

        elements.resultsMeta.innerHTML = metaItems.join('');
    }

    // Render markdown content
    if (elements.resultsContent) {
        const content = result.report || 'No content available';

        if (typeof marked !== 'undefined') {
            elements.resultsContent.innerHTML = marked.parse(content);
        } else {
            elements.resultsContent.innerHTML = `<pre>${content}</pre>`;
        }
    }

    // Scroll to results
    elements.resultsSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });

    showToast('Research completed successfully!');
}

function showError(message) {
    state.currentResults = { error: message };

    elements.resultsSection?.classList.add('visible');

    if (elements.resultsMeta) {
        elements.resultsMeta.innerHTML = '<span class="meta-tag" style="color: var(--accent-error);"><strong>Error</strong></span>';
    }

    if (elements.resultsContent) {
        elements.resultsContent.innerHTML = `
            <div class="results-error">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                </svg>
                <h3>Research Failed</h3>
                <p>${message}</p>
            </div>
        `;
    }

    showToast('Research failed', 'error');
}

function setResearchingState(researching) {
    state.isResearching = researching;

    if (elements.searchBtn) {
        elements.searchBtn.disabled = researching;
    }
}

function resetUI() {
    // Reset progress
    if (elements.progressBar) {
        elements.progressBar.style.width = '0%';
    }
    if (elements.progressPercent) {
        elements.progressPercent.textContent = '0%';
    }
    if (elements.progressText) {
        elements.progressText.textContent = 'Initializing...';
    }
    elements.progressSection?.classList.remove('visible');

    // Hide results
    elements.resultsSection?.classList.remove('visible');

    // Clear log
    if (elements.logContainer) {
        elements.logContainer.innerHTML = `
            <div class="log-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <p>Agent messages will appear here during research</p>
            </div>
        `;
    }

    // Reset agent statuses
    Object.keys(elements.agents).forEach(agent => {
        setAgentStatus(agent, null);
    });

    // Clear current results
    state.currentResults = null;
}

// =============================================================================
// Download Functionality
// =============================================================================

function downloadResults(format) {
    if (!state.currentResults || !state.currentResults.report) {
        showToast('No results to download', 'error');
        return;
    }

    const query = state.currentResults.query || 'research';
    const timestamp = new Date().toISOString().split('T')[0];
    const baseFilename = `research-${sanitizeFilename(query)}-${timestamp}`;

    let content, filename, mimeType;

    switch (format) {
        case 'markdown':
            content = generateMarkdownContent();
            filename = `${baseFilename}.md`;
            mimeType = 'text/markdown';
            break;

        case 'text':
            content = generateTextContent();
            filename = `${baseFilename}.txt`;
            mimeType = 'text/plain';
            break;

        case 'html':
            content = generateHTMLContent();
            filename = `${baseFilename}.html`;
            mimeType = 'text/html';
            break;

        case 'json':
            content = generateJSONContent();
            filename = `${baseFilename}.json`;
            mimeType = 'application/json';
            break;

        default:
            showToast('Invalid download format', 'error');
            return;
    }

    downloadFile(content, filename, mimeType);
    showToast(`Downloaded as ${format.toUpperCase()}`);
}

function generateMarkdownContent() {
    const result = state.currentResults;
    let content = '';

    // Add header
    content += `# Research Report\n\n`;
    content += `**Query:** ${result.query || 'N/A'}\n`;
    content += `**Date:** ${new Date().toLocaleDateString()}\n`;
    if (result.sources_count) {
        content += `**Sources:** ${result.sources_count}\n`;
    }
    if (result.duration_seconds) {
        content += `**Duration:** ${result.duration_seconds.toFixed(1)}s\n`;
    }
    content += `\n---\n\n`;

    // Add report content
    content += result.report || 'No content available';

    // Add footer
    content += `\n\n---\n\n*Generated by ResearchAgent - Powered by A2A Protocol*\n`;

    return content;
}

function generateTextContent() {
    const result = state.currentResults;
    let content = '';

    content += `RESEARCH REPORT\n`;
    content += `${'='.repeat(50)}\n\n`;
    content += `Query: ${result.query || 'N/A'}\n`;
    content += `Date: ${new Date().toLocaleDateString()}\n`;
    if (result.sources_count) {
        content += `Sources: ${result.sources_count}\n`;
    }
    if (result.duration_seconds) {
        content += `Duration: ${result.duration_seconds.toFixed(1)}s\n`;
    }
    content += `\n${'='.repeat(50)}\n\n`;

    // Strip markdown formatting for plain text
    const plainText = (result.report || 'No content available')
        .replace(/#{1,6}\s/g, '')
        .replace(/\*\*([^*]+)\*\*/g, '$1')
        .replace(/\*([^*]+)\*/g, '$1')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/^\s*[-*+]\s/gm, '  - ');

    content += plainText;
    content += `\n\n${'='.repeat(50)}\n`;
    content += `Generated by ResearchAgent - Powered by A2A Protocol\n`;

    return content;
}

function generateHTMLContent() {
    const result = state.currentResults;
    const reportHTML = typeof marked !== 'undefined'
        ? marked.parse(result.report || 'No content available')
        : `<pre>${result.report || 'No content available'}</pre>`;

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Report - ${result.query || 'Research'}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            color: #1a1a1a;
        }
        header {
            border-bottom: 2px solid #6366f1;
            padding-bottom: 1rem;
            margin-bottom: 2rem;
        }
        h1 { color: #6366f1; margin-bottom: 1rem; }
        .meta { color: #666; font-size: 0.9rem; }
        .meta span { margin-right: 1.5rem; }
        .content { margin-top: 2rem; }
        .content h1, .content h2, .content h3 { margin-top: 1.5rem; margin-bottom: 0.75rem; color: #333; }
        .content p { margin-bottom: 1rem; }
        .content ul, .content ol { margin-bottom: 1rem; padding-left: 1.5rem; }
        .content li { margin-bottom: 0.5rem; }
        .content code { background: #f4f4f5; padding: 0.2rem 0.4rem; border-radius: 4px; }
        .content pre { background: #f4f4f5; padding: 1rem; border-radius: 8px; overflow-x: auto; }
        .content blockquote { border-left: 3px solid #6366f1; padding-left: 1rem; margin: 1rem 0; color: #666; }
        footer {
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid #e5e5e5;
            text-align: center;
            color: #666;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <header>
        <h1>Research Report</h1>
        <div class="meta">
            <span><strong>Query:</strong> ${result.query || 'N/A'}</span>
            <span><strong>Date:</strong> ${new Date().toLocaleDateString()}</span>
            ${result.sources_count ? `<span><strong>Sources:</strong> ${result.sources_count}</span>` : ''}
            ${result.duration_seconds ? `<span><strong>Duration:</strong> ${result.duration_seconds.toFixed(1)}s</span>` : ''}
        </div>
    </header>
    <main class="content">
        ${reportHTML}
    </main>
    <footer>
        <p>Generated by ResearchAgent - Powered by A2A Protocol</p>
    </footer>
</body>
</html>`;
}

function generateJSONContent() {
    const result = state.currentResults;

    return JSON.stringify({
        metadata: {
            query: result.query || null,
            generated_at: new Date().toISOString(),
            sources_count: result.sources_count || null,
            duration_seconds: result.duration_seconds || null,
            generator: 'ResearchAgent',
            protocol: 'A2A'
        },
        report: result.report || null,
        success: result.success ?? true
    }, null, 2);
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
}

function sanitizeFilename(str) {
    return str
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .substring(0, 50);
}

// =============================================================================
// PDF/DOCX Export (Server-side generation)
// =============================================================================

async function downloadPDF() {
    if (!state.currentResults || !state.currentResults.report) {
        showToast('No results to download', 'error');
        return;
    }

    try {
        const response = await fetch('/export/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: state.currentResults.query,
                report: state.currentResults.report,
                sources_count: state.currentResults.sources_count,
                duration_seconds: state.currentResults.duration_seconds
            })
        });

        if (!response.ok) {
            throw new Error('PDF export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `research_report_${new Date().toISOString().slice(0,10)}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        showToast('Downloaded as PDF');
    } catch (error) {
        console.error('PDF download failed:', error);
        showToast('Failed to download PDF', 'error');
    }
}

async function downloadDOCX() {
    if (!state.currentResults || !state.currentResults.report) {
        showToast('No results to download', 'error');
        return;
    }

    try {
        const response = await fetch('/export/docx', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: state.currentResults.query,
                report: state.currentResults.report,
                sources_count: state.currentResults.sources_count,
                duration_seconds: state.currentResults.duration_seconds
            })
        });

        if (!response.ok) {
            throw new Error('DOCX export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `research_report_${new Date().toISOString().slice(0,10)}.docx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        showToast('Downloaded as DOCX');
    } catch (error) {
        console.error('DOCX download failed:', error);
        showToast('Failed to download DOCX', 'error');
    }
}

// =============================================================================
// Clipboard
// =============================================================================

async function copyToClipboard() {
    if (!state.currentResults || !state.currentResults.report) {
        showToast('No results to copy', 'error');
        return;
    }

    try {
        await navigator.clipboard.writeText(state.currentResults.report);
        showToast('Copied to clipboard!');
    } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = state.currentResults.report;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();

        try {
            document.execCommand('copy');
            showToast('Copied to clipboard!');
        } catch (e) {
            showToast('Failed to copy to clipboard', 'error');
        }

        document.body.removeChild(textArea);
    }
}

// =============================================================================
// Toast Notifications
// =============================================================================

function showToast(message, type = 'success') {
    if (!elements.toast || !elements.toastMessage) return;

    elements.toastMessage.textContent = message;

    // Update icon based on type
    const icon = elements.toast.querySelector('.toast-icon');
    if (icon) {
        if (type === 'error') {
            icon.innerHTML = `
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
            `;
            icon.style.color = 'var(--accent-error)';
        } else {
            icon.innerHTML = `
                <path d="M9 12l2 2 4-4"/>
                <circle cx="12" cy="12" r="10"/>
            `;
            icon.style.color = 'var(--accent-success)';
        }
    }

    elements.toast.classList.add('visible');

    // Auto-hide after 3 seconds
    setTimeout(() => {
        elements.toast.classList.remove('visible');
    }, 3000);
}

// =============================================================================
// Utility Functions
// =============================================================================

function clearLog() {
    if (elements.logContainer) {
        elements.logContainer.innerHTML = `
            <div class="log-empty">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <p>Agent messages will appear here during research</p>
            </div>
        `;
    }
    showToast('Log cleared');
}

function newResearch() {
    resetUI();
    elements.queryInput?.focus();

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function checkHealth() {
    try {
        const response = await fetch('/health');
        const health = await response.json();

        // Update agent indicators based on health status
        Object.entries(health.agents || {}).forEach(([agentId, status]) => {
            const normalizedId = agentId.toLowerCase();
            if (elements.agents[normalizedId]) {
                const isHealthy = status.status === 'healthy' || status.initialized;
                setAgentStatus(normalizedId, isHealthy ? 'active' : 'error');
            }
        });
    } catch (error) {
        console.warn('Health check failed:', error);
    }
}

// =============================================================================
// Global Exports (for inline event handlers)
// =============================================================================

window.executeResearch = executeResearch;
window.downloadResults = downloadResults;
window.downloadPDF = downloadPDF;
window.downloadDOCX = downloadDOCX;
window.copyToClipboard = copyToClipboard;
window.clearLog = clearLog;
window.newResearch = newResearch;
window.toggleTheme = toggleTheme;
