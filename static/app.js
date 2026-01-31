/**
 * Multi-Agent Research Assistant - Frontend Application
 * Handles UI interactions, A2A message visualization, and research workflow execution
 */

// State
let isResearching = false;
let currentWorkflowId = null;
let eventSource = null;
let currentResult = null;  // Store current result for export

// DOM Elements
const queryInput = document.getElementById('query-input');
const searchBtn = document.getElementById('search-btn');
const depthSelect = document.getElementById('depth-select');
const formatSelect = document.getElementById('format-select');
const streamCheck = document.getElementById('stream-check');
const progressSection = document.getElementById('progress-section');
const progressBar = document.getElementById('progress-bar');
const progressText = document.getElementById('progress-text');
const logContainer = document.getElementById('log-container');
const resultsSection = document.getElementById('results-section');
const resultsMeta = document.getElementById('results-meta');
const resultsContent = document.getElementById('results-content');

// Agent status elements
const agentStatuses = {
    perplexity: document.getElementById('status-perplexity'),
    claude: document.getElementById('status-claude'),
    openai: document.getElementById('status-openai')
};

/**
 * Execute research workflow
 */
async function executeResearch() {
    const query = queryInput.value.trim();
    if (!query) {
        alert('Please enter a research query');
        return;
    }

    if (isResearching) {
        return;
    }

    // Reset UI
    resetUI();
    setResearchingState(true);

    const depth = depthSelect.value;
    const outputFormat = formatSelect.value;
    const useStreaming = streamCheck.checked;

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

/**
 * Execute research with streaming progress
 */
async function executeStreamingResearch(query, depth, outputFormat) {
    logMessage('Orchestrator', 'Starting research workflow...', 'orchestrator');
    updateProgress(5, 'Initializing research workflow...');

    // Use Server-Sent Events for streaming
    const params = new URLSearchParams({
        query: query,
        depth: depth,
        output_format: outputFormat,
        stream: 'true'
    });

    const response = await fetch('/research', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            query: query,
            depth: depth,
            output_format: outputFormat,
            stream: true
        })
    });

    if (!response.ok) {
        throw new Error(`Research request failed: ${response.status}`);
    }

    // For SSE, we need to handle the stream
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
            if (line.startsWith('data:')) {
                const data = line.slice(5).trim();
                if (data) {
                    try {
                        handleStreamEvent(JSON.parse(data));
                    } catch (e) {
                        // Try to parse as Python dict string
                        handleStreamMessage(data);
                    }
                }
            }
        }
    }
}

/**
 * Handle streaming event
 */
function handleStreamEvent(event) {
    const { id, status, progress, message, error } = event;

    if (error) {
        showError(error);
        return;
    }

    // Update progress
    if (progress !== undefined) {
        updateProgress(progress * 100, message || `Progress: ${Math.round(progress * 100)}%`);
    }

    // Parse message for agent activity
    if (message) {
        parseMessageForAgentActivity(message);

        // If completed, show results
        if (status === 'completed') {
            showResults({
                query: queryInput.value,
                report: message,
                success: true
            });
        }
    }
}

/**
 * Handle stream message (fallback parser)
 */
function handleStreamMessage(data) {
    // Try to extract useful info from string representation
    if (data.includes('progress')) {
        const progressMatch = data.match(/progress['":\s]+(\d+\.?\d*)/);
        if (progressMatch) {
            const progress = parseFloat(progressMatch[1]);
            updateProgress(progress * 100);
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

/**
 * Parse message to update agent status
 */
function parseMessageForAgentActivity(message) {
    const lowerMsg = message.toLowerCase();

    if (lowerMsg.includes('perplexity') || lowerMsg.includes('search')) {
        setAgentStatus('perplexity', 'working', 'Searching...');
        logMessage('Perplexity', message, 'perplexity');
    }

    if (lowerMsg.includes('claude') || lowerMsg.includes('analyz')) {
        setAgentStatus('claude', 'working', 'Analyzing...');
        logMessage('Claude', message, 'claude');
    }

    if (lowerMsg.includes('openai') || lowerMsg.includes('gpt') || lowerMsg.includes('validat')) {
        setAgentStatus('openai', 'working', 'Validating...');
        logMessage('OpenAI', message, 'openai');
    }

    if (lowerMsg.includes('orchestrator') || lowerMsg.includes('synthesi')) {
        logMessage('Orchestrator', message, 'orchestrator');
    }
}

/**
 * Execute research without streaming
 */
async function executeDirectResearch(query, depth, outputFormat) {
    logMessage('Orchestrator', 'Starting research workflow...', 'orchestrator');
    updateProgress(10, 'Initializing...');

    // Simulate agent activity for non-streaming
    setTimeout(() => setAgentStatus('perplexity', 'working', 'Searching...'), 500);
    setTimeout(() => updateProgress(30, 'Searching web sources...'), 1000);
    setTimeout(() => setAgentStatus('claude', 'working', 'Analyzing...'), 3000);
    setTimeout(() => updateProgress(50, 'Analyzing findings...'), 3500);
    setTimeout(() => setAgentStatus('gemini', 'working', 'Validating...'), 5000);
    setTimeout(() => updateProgress(70, 'Validating results...'), 5500);

    const response = await fetch('/research', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            query: query,
            depth: depth,
            output_format: outputFormat,
            stream: false
        })
    });

    if (!response.ok) {
        throw new Error(`Research request failed: ${response.status}`);
    }

    const result = await response.json();

    updateProgress(100, 'Complete!');

    // Reset agent statuses
    Object.keys(agentStatuses).forEach(agent => {
        setAgentStatus(agent, 'active', 'Complete');
    });

    if (result.success) {
        showResults(result);
    } else {
        showError(result.error || 'Research failed');
    }
}

/**
 * Update progress bar and text
 */
function updateProgress(percent, text) {
    progressSection.style.display = 'block';

    if (percent !== null) {
        progressBar.style.width = `${percent}%`;
    }

    if (text) {
        progressText.textContent = text;
    }
}

/**
 * Set agent status
 */
function setAgentStatus(agent, status, text) {
    const statusEl = agentStatuses[agent];
    if (!statusEl) return;

    const dot = statusEl.querySelector('.status-dot');
    const textEl = statusEl.querySelector('.status-text');
    const card = document.getElementById(`agent-${agent}`);

    // Reset classes
    dot.classList.remove('active', 'working', 'error');
    card.classList.remove('active');

    // Set new status
    if (status === 'active' || status === 'working') {
        dot.classList.add(status);
        card.classList.add('active');
    } else if (status === 'error') {
        dot.classList.add('error');
    }

    textEl.textContent = text || status;
}

/**
 * Log a message to the A2A log
 */
function logMessage(sender, message, senderClass) {
    const placeholder = logContainer.querySelector('.log-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const entry = document.createElement('div');
    entry.className = 'log-entry';

    const timestamp = new Date().toLocaleTimeString();

    entry.innerHTML = `
        <span class="log-timestamp">[${timestamp}]</span>
        <span class="log-sender ${senderClass}">${sender}:</span>
        <span class="log-method">${truncateMessage(message, 100)}</span>
    `;

    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

/**
 * Truncate message for log display
 */
function truncateMessage(message, maxLength) {
    if (message.length <= maxLength) return message;
    return message.substring(0, maxLength) + '...';
}

/**
 * Show research results
 */
function showResults(result) {
    resultsSection.style.display = 'block';

    // Store result for export
    currentResult = result;

    // Show download buttons
    const downloadButtons = document.getElementById('download-buttons');
    if (downloadButtons) {
        downloadButtons.style.display = 'flex';
    }

    // Meta information
    resultsMeta.innerHTML = `
        <div class="meta-item">
            <span>Query:</span>
            <span class="meta-value">${result.query}</span>
        </div>
        <div class="meta-item">
            <span>Sources:</span>
            <span class="meta-value">${result.sources_count || 'N/A'}</span>
        </div>
        <div class="meta-item">
            <span>Duration:</span>
            <span class="meta-value">${result.duration_seconds ? result.duration_seconds.toFixed(1) + 's' : 'N/A'}</span>
        </div>
    `;

    // Render markdown content
    if (typeof marked !== 'undefined') {
        resultsContent.innerHTML = marked.parse(result.report || 'No content available');
    } else {
        resultsContent.innerHTML = `<pre>${result.report || 'No content available'}</pre>`;
    }

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

/**
 * Download results as PDF
 */
async function downloadPDF() {
    if (!currentResult) {
        alert('No results to download');
        return;
    }

    try {
        const response = await fetch('/export/pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: currentResult.query,
                report: currentResult.report,
                sources_count: currentResult.sources_count,
                duration_seconds: currentResult.duration_seconds
            })
        });

        if (!response.ok) {
            throw new Error('PDF export failed');
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `research_report_${new Date().toISOString().slice(0,10)}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (error) {
        console.error('PDF download failed:', error);
        alert('Failed to download PDF: ' + error.message);
    }
}

/**
 * Download results as DOCX
 */
async function downloadDOCX() {
    if (!currentResult) {
        alert('No results to download');
        return;
    }

    try {
        const response = await fetch('/export/docx', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: currentResult.query,
                report: currentResult.report,
                sources_count: currentResult.sources_count,
                duration_seconds: currentResult.duration_seconds
            })
        });

        if (!response.ok) {
            throw new Error('DOCX export failed');
        }

        // Download the file
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `research_report_${new Date().toISOString().slice(0,10)}.docx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (error) {
        console.error('DOCX download failed:', error);
        alert('Failed to download DOCX: ' + error.message);
    }
}

/**
 * Show error message
 */
function showError(message) {
    resultsSection.style.display = 'block';
    resultsMeta.innerHTML = `
        <div class="meta-item" style="color: var(--accent-red);">
            <span>Error</span>
        </div>
    `;
    resultsContent.innerHTML = `
        <div style="color: var(--accent-red); padding: 1rem;">
            <strong>Research Failed</strong>
            <p>${message}</p>
        </div>
    `;
}

/**
 * Set UI state for researching
 */
function setResearchingState(researching) {
    isResearching = researching;
    searchBtn.disabled = researching;

    const btnText = searchBtn.querySelector('.btn-text');
    const btnLoading = searchBtn.querySelector('.btn-loading');

    if (researching) {
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline-block';
    } else {
        btnText.style.display = 'inline-block';
        btnLoading.style.display = 'none';
    }
}

/**
 * Reset UI state
 */
function resetUI() {
    progressBar.style.width = '0%';
    progressText.textContent = 'Initializing...';
    progressSection.style.display = 'none';
    resultsSection.style.display = 'none';

    // Clear log
    logContainer.innerHTML = '<div class="log-placeholder">Messages will appear here during research...</div>';

    // Reset agent statuses
    Object.keys(agentStatuses).forEach(agent => {
        setAgentStatus(agent, 'idle', 'Idle');
    });
}

/**
 * Initialize on page load
 */
async function init() {
    // Check health and update agent statuses
    try {
        const response = await fetch('/health');
        const health = await response.json();

        Object.entries(health.agents || {}).forEach(([agentId, status]) => {
            if (agentId in agentStatuses) {
                const isHealthy = status.status === 'healthy' || status.initialized;
                setAgentStatus(agentId, isHealthy ? 'active' : 'error',
                    isHealthy ? 'Ready' : 'Unavailable');
            }
        });
    } catch (error) {
        console.error('Health check failed:', error);
    }

    // Setup enter key handler
    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            executeResearch();
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
