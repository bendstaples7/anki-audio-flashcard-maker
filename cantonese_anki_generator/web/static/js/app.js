/**
 * Main JavaScript application for Manual Audio Alignment interface
 */

// Application state
const AppState = {
    sessionId: null,
    currentSession: null,
    alignments: [],
    currentlyPlaying: null,
    pendingUpdates: new Map(),
    uploadedFiles: {
        url: null,
        audioFile: null,
        audioFilePath: null
    },
    validationState: {
        urlValid: false,
        audioValid: false
    }
};

// API base URL
const API_BASE = '/api';

// DOM elements (cached for performance)
let elements = {};

/**
 * Initialize the application
 */
function initApp() {
    console.log('Manual Audio Alignment interface initialized');
    
    // Cache DOM elements
    cacheElements();
    
    // Set up event listeners
    setupEventListeners();
    
    // Set up save button
    setupSaveButton();
    
    // Set up reset all button
    setupResetAllButton();
    
    // Set up quality controls (sorting and filtering)
    setupQualityControls();
    
    // Set up generate button
    setupGenerateButton();
    
    // Initialize session loading (check URL for session ID)
    initSessionLoading();
    
    // Check API health
    checkAPIHealth();
}

/**
 * Cache DOM elements for performance
 */
function cacheElements() {
    elements = {
        // Form elements
        uploadForm: document.getElementById('upload-form'),
        docUrlInput: document.getElementById('doc-url'),
        audioFileInput: document.getElementById('audio-file'),
        processBtn: document.getElementById('process-btn'),
        
        // Feedback elements
        urlFeedback: document.getElementById('url-feedback'),
        fileFeedback: document.getElementById('file-feedback'),
        fileNameDisplay: document.querySelector('.file-name'),
        
        // Progress elements
        uploadProgress: document.getElementById('upload-progress'),
        progressFill: document.getElementById('progress-fill'),
        progressText: document.getElementById('progress-text'),
        
        // Toast elements
        errorToast: document.getElementById('error-toast'),
        errorMessage: document.getElementById('error-message'),
        successToast: document.getElementById('success-toast'),
        successMessage: document.getElementById('success-message'),
        
        // Section elements
        uploadSection: document.getElementById('upload-section'),
        alignmentSection: document.getElementById('alignment-section')
    };
}

/**
 * Set up event listeners for form interactions
 */
function setupEventListeners() {
    // URL input validation
    elements.docUrlInput.addEventListener('input', debounce(validateUrl, 500));
    elements.docUrlInput.addEventListener('blur', validateUrl);
    
    // Audio file selection
    elements.audioFileInput.addEventListener('change', handleFileSelection);
    
    // Form submission
    elements.uploadForm.addEventListener('submit', handleFormSubmit);
}

/**
 * Task 19.1: Handle network errors gracefully
 * Wrapper for fetch with automatic retry and error handling
 * @param {string} url - URL to fetch
 * @param {Object} options - Fetch options
 * @param {number} maxRetries - Maximum number of retry attempts (default: 2)
 * @returns {Promise<Response>} Fetch response
 */
async function fetchWithRetry(url, options = {}, maxRetries = 2) {
    let lastError = null;
    
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
            // Add timeout to prevent hanging requests
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
            
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            // Check if response is ok
            if (!response.ok) {
                // Try to parse error message from response
                let errorMessage = `Request failed with status ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch (e) {
                    // Response is not JSON, use status text
                    errorMessage = response.statusText || errorMessage;
                }
                
                // Don't retry on client errors (4xx), only on server errors (5xx) or network issues
                if (response.status >= 400 && response.status < 500) {
                    throw new Error(errorMessage);
                }
                
                lastError = new Error(errorMessage);
                
                // Wait before retrying (exponential backoff)
                if (attempt < maxRetries) {
                    const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
                    console.log(`Request failed, retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
                    await new Promise(resolve => setTimeout(resolve, delay));
                    continue;
                }
            }
            
            return response;
            
        } catch (error) {
            lastError = error;
            
            // Handle specific error types
            if (error.name === 'AbortError') {
                lastError = new Error('Request timeout - please check your connection and try again');
            } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
                lastError = new Error('Network error - please check your internet connection');
            }
            
            // Retry on network errors
            if (attempt < maxRetries) {
                const delay = Math.min(1000 * Math.pow(2, attempt), 5000);
                console.log(`Network error, retrying in ${delay}ms... (attempt ${attempt + 1}/${maxRetries})`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }
        }
    }
    
    // All retries exhausted
    throw lastError || new Error('Request failed after multiple attempts');
}

/**
 * Check API health status with error handling
 */
async function checkAPIHealth() {
    try {
        const response = await fetchWithRetry(`${API_BASE}/health`, {}, 1); // Only 1 retry for health check
        const data = await response.json();
        console.log('API Status:', data.message);
    } catch (error) {
        console.error('Failed to connect to API:', error);
        showError('Failed to connect to server. Please check your connection.', {
            retryAction: checkAPIHealth,
            retryLabel: 'Retry Connection',
            autoHide: false
        });
    }
}

/**
 * Validate Google Docs/Sheets URL
 */
async function validateUrl() {
    const url = elements.docUrlInput.value.trim();
    
    // Clear previous feedback
    clearFeedback(elements.urlFeedback);
    
    // Empty URL is not an error (just not valid yet)
    if (!url) {
        AppState.validationState.urlValid = false;
        updateProcessButton();
        return;
    }
    
    // Basic format check
    const docsPattern = /^https:\/\/docs\.google\.com\/(document|spreadsheets)\/d\/[a-zA-Z0-9-_]+/;
    if (!docsPattern.test(url)) {
        showFeedback(
            elements.urlFeedback,
            'Invalid URL format. Please provide a valid Google Docs or Sheets URL.',
            'error'
        );
        AppState.validationState.urlValid = false;
        updateProcessButton();
        return;
    }
    
    // Show validating state
    showFeedback(elements.urlFeedback, 'Validating URL...', 'info');
    
    // Validate accessibility (this will be done on server during upload)
    // For now, just mark as valid if format is correct
    showFeedback(elements.urlFeedback, 'URL format is valid', 'success');
    AppState.validationState.urlValid = true;
    AppState.uploadedFiles.url = url;
    updateProcessButton();
}

/**
 * Handle audio file selection
 */
function handleFileSelection(event) {
    const file = event.target.files[0];
    
    // Clear previous feedback
    clearFeedback(elements.fileFeedback);
    
    if (!file) {
        elements.fileNameDisplay.textContent = 'No file selected';
        AppState.validationState.audioValid = false;
        AppState.uploadedFiles.audioFile = null;
        updateProcessButton();
        return;
    }
    
    // Update file name display
    elements.fileNameDisplay.textContent = file.name;
    
    // Validate file format
    const validFormats = ['.mp3', '.wav', '.m4a'];
    const fileName = file.name.toLowerCase();
    const fileExt = fileName.substring(fileName.lastIndexOf('.'));
    
    if (!validFormats.includes(fileExt)) {
        showFeedback(
            elements.fileFeedback,
            `Unsupported format. Please select an MP3, WAV, or M4A file.`,
            'error'
        );
        AppState.validationState.audioValid = false;
        AppState.uploadedFiles.audioFile = null;
        updateProcessButton();
        return;
    }
    
    // Validate file size (50MB limit)
    const maxSize = 50 * 1024 * 1024; // 50MB in bytes
    if (file.size > maxSize) {
        showFeedback(
            elements.fileFeedback,
            `File too large (${(file.size / (1024 * 1024)).toFixed(2)}MB). Maximum size is 50MB.`,
            'error'
        );
        AppState.validationState.audioValid = false;
        AppState.uploadedFiles.audioFile = null;
        updateProcessButton();
        return;
    }
    
    // File is valid
    const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
    showFeedback(
        elements.fileFeedback,
        `Valid audio file (${fileSizeMB}MB)`,
        'success'
    );
    AppState.validationState.audioValid = true;
    AppState.uploadedFiles.audioFile = file;
    updateProcessButton();
}

/**
 * Update Process button state based on validation
 */
function updateProcessButton() {
    const isValid = AppState.validationState.urlValid && AppState.validationState.audioValid;
    elements.processBtn.disabled = !isValid;
    
    if (isValid) {
        elements.processBtn.classList.add('btn-ready');
    } else {
        elements.processBtn.classList.remove('btn-ready');
    }
}

/**
 * Handle form submission with improved error handling
 * Task 19.1: Provide retry options for failed operations
 */
async function handleFormSubmit(event) {
    event.preventDefault();
    
    // Disable form during upload
    setFormEnabled(false);
    
    // Show progress
    showUploadProgress();
    
    try {
        // Create FormData for file upload
        const formData = new FormData();
        formData.append('url', AppState.uploadedFiles.url);
        formData.append('audio', AppState.uploadedFiles.audioFile);
        
        // Upload files with retry
        updateProgress(10, 'Uploading files...');
        
        const uploadResponse = await fetchWithRetry(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        updateProgress(30, 'Processing upload...');
        
        const uploadData = await uploadResponse.json();
        
        if (!uploadResponse.ok) {
            throw new Error(uploadData.error || 'Upload failed');
        }
        
        // Store uploaded file info
        AppState.uploadedFiles.audioFilePath = uploadData.data.audio_filepath;
        
        // Process files and create session with retry
        updateProgress(50, 'Running automatic alignment...');
        
        const processResponse = await fetchWithRetry(`${API_BASE}/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                doc_url: AppState.uploadedFiles.url,
                audio_filepath: uploadData.data.audio_filepath
            })
        });
        
        updateProgress(80, 'Creating alignment session...');
        
        const processData = await processResponse.json();
        
        if (!processResponse.ok) {
            throw new Error(processData.error || 'Processing failed');
        }
        
        updateProgress(100, 'Complete!');
        
        // Store session ID
        AppState.sessionId = processData.data.session_id;
        
        // Update URL with session ID for sharing/bookmarking (Requirement 8.3)
        updateUrlWithSessionId(AppState.sessionId);
        
        // Show success message
        const lowConfCount = processData.data.low_confidence_count;
        const message = lowConfCount > 0
            ? `Processing complete! ${processData.data.total_terms} terms aligned (${lowConfCount} need review).`
            : `Processing complete! ${processData.data.total_terms} terms aligned successfully.`;
        
        showSuccess(message);
        
        // Hide progress after a short delay
        setTimeout(async () => {
            hideUploadProgress();
            
            // Load and display the session
            await loadSession(AppState.sessionId);
            
        }, 1000);
        
    } catch (error) {
        console.error('Upload error:', error);
        
        // Provide user-friendly error message with retry option
        const errorMessage = error.message || 'Failed to upload files. Please try again.';
        showError(errorMessage, {
            retryAction: () => handleFormSubmit(event),
            retryLabel: 'Retry Upload',
            autoHide: false
        });
        
        hideUploadProgress();
        setFormEnabled(true);
    }
}

/**
 * Load and display a session with improved error handling
 * Task 19.1: Handle network errors gracefully
 * @param {string} sessionId - Session identifier
 */
async function loadSession(sessionId) {
    try {
        // Fetch session data with retry
        const response = await fetchWithRetry(`${API_BASE}/session/${sessionId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load session');
        }
        
        // Store session data
        AppState.currentSession = data.data;
        AppState.alignments = data.data.terms;
        
        // Hide upload section and show alignment section
        elements.uploadSection.style.display = 'none';
        const alignmentSection = document.getElementById('alignment-section');
        if (alignmentSection) {
            alignmentSection.style.display = 'block';
        }
        
        // Display alignments
        await displayAlignments(data.data.terms);
        
        // Render full waveform
        // Note: We need to serve the full audio file, not individual segments
        // For now, we'll use the first term's audio as a placeholder
        // TODO: Add endpoint to serve full audio file
        const audioUrl = `${API_BASE}/audio/${sessionId}/full`;
        await renderFullWaveform(audioUrl, data.data.terms);
        
        console.log('Session loaded and displayed');
        
    } catch (error) {
        console.error('Failed to load session:', error);
        showError(`Failed to load session: ${error.message}`, {
            retryAction: () => loadSession(sessionId),
            retryLabel: 'Retry Load',
            autoHide: false
        });
    }
}

/**
 * Show upload progress
 */
function showUploadProgress() {
    elements.uploadProgress.style.display = 'block';
    elements.processBtn.style.display = 'none';
}

/**
 * Hide upload progress
 */
function hideUploadProgress() {
    elements.uploadProgress.style.display = 'none';
    elements.processBtn.style.display = 'inline-flex';
}

/**
 * Update progress bar and text
 */
function updateProgress(percent, text) {
    elements.progressFill.style.width = `${percent}%`;
    elements.progressText.textContent = text;
}

/**
 * Enable or disable form inputs
 */
function setFormEnabled(enabled) {
    elements.docUrlInput.disabled = !enabled;
    elements.audioFileInput.disabled = !enabled;
    elements.processBtn.disabled = !enabled;
}

/**
 * Show feedback message
 */
function showFeedback(element, message, type) {
    element.textContent = message;
    element.className = `validation-feedback ${type}`;
    element.style.display = 'block';
}

/**
 * Clear feedback message
 */
function clearFeedback(element) {
    element.textContent = '';
    element.className = 'validation-feedback';
    element.style.display = 'none';
}

/**
 * Show error toast with optional retry action
 * Task 19.1: Display user-friendly error messages for API failures
 * @param {string} message - Error message to display
 * @param {Object} options - Optional configuration
 * @param {Function} options.retryAction - Function to call when retry is clicked
 * @param {string} options.retryLabel - Label for retry button (default: "Retry")
 * @param {boolean} options.autoHide - Whether to auto-hide (default: true)
 * @param {number} options.duration - Auto-hide duration in ms (default: 5000)
 */
function showError(message, options = {}) {
    const {
        retryAction = null,
        retryLabel = 'Retry',
        autoHide = true,
        duration = 5000
    } = options;
    
    elements.errorMessage.textContent = message;
    
    // Add retry button if retry action provided
    const existingRetryBtn = elements.errorToast.querySelector('.retry-btn');
    if (existingRetryBtn) {
        existingRetryBtn.remove();
    }
    
    if (retryAction) {
        const retryBtn = document.createElement('button');
        retryBtn.className = 'retry-btn';
        retryBtn.textContent = retryLabel;
        retryBtn.style.marginLeft = '10px';
        retryBtn.style.padding = '5px 10px';
        retryBtn.style.backgroundColor = '#3498db';
        retryBtn.style.color = 'white';
        retryBtn.style.border = 'none';
        retryBtn.style.borderRadius = '4px';
        retryBtn.style.cursor = 'pointer';
        retryBtn.onclick = () => {
            hideError();
            retryAction();
        };
        elements.errorMessage.appendChild(retryBtn);
    }
    
    elements.errorToast.style.display = 'flex';
    
    // Auto-hide after duration if enabled
    if (autoHide) {
        setTimeout(hideError, duration);
    }
}

/**
 * Hide error toast
 */
function hideError() {
    elements.errorToast.style.display = 'none';
    
    // Clean up retry button if present
    const retryBtn = elements.errorToast.querySelector('.retry-btn');
    if (retryBtn) {
        retryBtn.remove();
    }
}

/**
 * Show success toast
 */
function showSuccess(message) {
    elements.successMessage.textContent = message;
    elements.successToast.style.display = 'flex';
    
    // Auto-hide after 3 seconds
    setTimeout(hideSuccess, 3000);
}

/**
 * Hide success toast
 */
function hideSuccess() {
    elements.successToast.style.display = 'none';
}

/**
 * Debounce function to limit API calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Task 18: Implement Anki package generation with adjustments
 */

/**
 * Generate Anki package with manual adjustments
 * Triggers package generation and polls for progress
 * Task 19.1: Provide retry options for failed operations
 */
async function generateAnkiPackage() {
    if (!AppState.sessionId) {
        showError('No active session to generate from');
        return;
    }
    
    const generateBtn = document.getElementById('generate-btn');
    
    try {
        // Disable button and show loading state
        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';
        }
        
        // Show progress
        showGenerationProgress();
        updateGenerationProgress(0, 'Starting generation...');
        
        // Start generation with retry
        const response = await fetchWithRetry(`${API_BASE}/session/${AppState.sessionId}/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                deck_name: null  // Auto-generate deck name
            })
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to start generation');
        }
        
        // Poll for progress
        await pollGenerationProgress();
        
    } catch (error) {
        console.error('Generation error:', error);
        
        // Provide user-friendly error message with retry option
        showError(error.message || 'Failed to generate Anki package', {
            retryAction: generateAnkiPackage,
            retryLabel: 'Retry Generation',
            autoHide: false
        });
        
        hideGenerationProgress();
        
        // Re-enable button
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<span class="btn-icon">📦</span> Generate Anki Deck';
        }
    }
}

/**
 * Poll for generation progress
 */
async function pollGenerationProgress() {
    const maxAttempts = 120;  // 2 minutes max (120 * 1 second)
    let attempts = 0;
    
    return new Promise((resolve, reject) => {
        const pollInterval = setInterval(async () => {
            attempts++;
            
            try {
                const response = await fetch(`${API_BASE}/session/${AppState.sessionId}/generate/progress`);
                
                if (!response.ok) {
                    clearInterval(pollInterval);
                    reject(new Error('Failed to get generation progress'));
                    return;
                }
                
                const data = await response.json();
                const progress = data.data;
                
                // Update progress display
                updateGenerationProgress(progress.percent, progress.stage);
                
                // Check if complete
                if (progress.status === 'complete') {
                    clearInterval(pollInterval);
                    handleGenerationComplete(progress);
                    resolve();
                    return;
                }
                
                // Check if error
                if (progress.status === 'error') {
                    clearInterval(pollInterval);
                    reject(new Error(progress.error || 'Generation failed'));
                    return;
                }
                
                // Check timeout
                if (attempts >= maxAttempts) {
                    clearInterval(pollInterval);
                    reject(new Error('Generation timeout'));
                    return;
                }
                
            } catch (error) {
                clearInterval(pollInterval);
                reject(error);
            }
        }, 1000);  // Poll every second
    });
}

/**
 * Handle generation completion
 * @param {Object} progress - Progress data with download info
 */
function handleGenerationComplete(progress) {
    console.log('Generation complete:', progress);
    
    // Hide progress
    hideGenerationProgress();
    
    // Show success message with download link
    const message = `
        <div class="generation-complete">
            <h3>✅ Anki Package Generated!</h3>
            <div class="package-info">
                <p><strong>File:</strong> ${progress.filename}</p>
                <p><strong>Size:</strong> ${progress.file_size_mb} MB</p>
                <p><strong>Cards:</strong> ${progress.card_count}</p>
                <p><strong>Manually Adjusted:</strong> ${progress.manually_adjusted_count} / ${progress.total_terms}</p>
            </div>
            <a href="${progress.download_url}" class="btn btn-success download-btn" download>
                <span class="btn-icon">⬇️</span> Download Package
            </a>
        </div>
    `;
    
    // Show in a modal or toast
    showGenerationSummary(message);
    
    // Trigger automatic download
    triggerDownload(progress.download_url, progress.filename);
    
    // Re-enable generate button
    const generateBtn = document.getElementById('generate-btn');
    if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<span class="btn-icon">📦</span> Generate Anki Deck';
    }
}

/**
 * Trigger automatic download of the package
 * @param {string} url - Download URL
 * @param {string} filename - Filename for download
 */
function triggerDownload(url, filename) {
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Show generation progress UI
 */
function showGenerationProgress() {
    // Reuse upload progress UI or create new one
    const progressContainer = elements.uploadProgress || document.getElementById('generation-progress');
    if (progressContainer) {
        progressContainer.style.display = 'block';
    }
}

/**
 * Hide generation progress UI
 */
function hideGenerationProgress() {
    const progressContainer = elements.uploadProgress || document.getElementById('generation-progress');
    if (progressContainer) {
        progressContainer.style.display = 'none';
    }
}

/**
 * Update generation progress display
 * @param {number} percent - Progress percentage (0-100)
 * @param {string} stage - Current stage description
 */
function updateGenerationProgress(percent, stage) {
    if (elements.progressFill) {
        elements.progressFill.style.width = `${percent}%`;
    }
    if (elements.progressText) {
        elements.progressText.textContent = stage;
    }
}

/**
 * Show generation summary in a modal or prominent display
 * @param {string} html - HTML content to display
 */
function showGenerationSummary(html) {
    // Create a modal or use existing toast system
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'generation-summary-modal';
    summaryDiv.innerHTML = `
        <div class="modal-overlay"></div>
        <div class="modal-content">
            ${html}
            <button class="btn btn-secondary close-modal" onclick="this.closest('.generation-summary-modal').remove()">
                Close
            </button>
        </div>
    `;
    document.body.appendChild(summaryDiv);
    
    // Auto-remove after 30 seconds
    setTimeout(() => {
        if (summaryDiv.parentNode) {
            summaryDiv.remove();
        }
    }, 30000);
}

/**
 * Setup generate button
 */
function setupGenerateButton() {
    const generateBtn = document.getElementById('generate-btn');
    
    if (generateBtn) {
        generateBtn.addEventListener('click', generateAnkiPackage);
        console.log('Generate button initialized');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initApp);

// Additional functionality will be implemented in subsequent tasks:
// - Waveform rendering
// - Audio playback controls
// - Boundary adjustment
// - Session management

/**
 * WaveSurfer.js Integration
 * Task 8.1: Set up WaveSurfer.js library
 */

// WaveSurfer instances storage
const WaveSurferInstances = {
    fullWaveform: null,
    termWaveforms: new Map() // Map of term_id -> WaveSurfer instance
};

/**
 * Initialize WaveSurfer instance for full waveform overview
 * @param {string} containerId - DOM element ID for the waveform container
 * @param {Object} options - Additional WaveSurfer options
 * @returns {Object} WaveSurfer instance
 */
function initializeFullWaveform(containerId, options = {}) {
    const defaultOptions = {
        container: `#${containerId}`,
        waveColor: '#3498db',
        progressColor: '#2980b9',
        cursorColor: '#e74c3c',
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 120,
        normalize: true,
        backend: 'WebAudio',
        interact: true,
        hideScrollbar: false,
        minPxPerSec: 50
    };
    
    const wavesurfer = WaveSurfer.create({
        ...defaultOptions,
        ...options
    });
    
    // Add regions plugin for boundary markers
    const regionsPlugin = wavesurfer.registerPlugin(WaveSurfer.Regions.create());
    
    // Store reference
    WaveSurferInstances.fullWaveform = {
        instance: wavesurfer,
        regions: regionsPlugin
    };
    
    console.log('Full waveform WaveSurfer instance initialized');
    
    return wavesurfer;
}

/**
 * Initialize WaveSurfer instance for individual term waveform
 * @param {string} containerId - DOM element ID for the waveform container
 * @param {string} termId - Unique identifier for the term
 * @param {Object} options - Additional WaveSurfer options
 * @returns {Object} WaveSurfer instance
 */
function initializeTermWaveform(containerId, termId, options = {}) {
    const defaultOptions = {
        container: `#${containerId}`,
        waveColor: '#95a5a6',
        progressColor: '#3498db',
        cursorColor: '#e74c3c',
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 80,
        normalize: true,
        backend: 'WebAudio',
        interact: true,
        hideScrollbar: true,
        minPxPerSec: 100
    };
    
    const wavesurfer = WaveSurfer.create({
        ...defaultOptions,
        ...options
    });
    
    // Add regions plugin for draggable boundary markers
    const regionsPlugin = wavesurfer.registerPlugin(WaveSurfer.Regions.create());
    
    // Store reference
    WaveSurferInstances.termWaveforms.set(termId, {
        instance: wavesurfer,
        regions: regionsPlugin
    });
    
    console.log(`Term waveform initialized for term: ${termId}`);
    
    return wavesurfer;
}

/**
 * Get WaveSurfer instance for a specific term
 * @param {string} termId - Term identifier
 * @returns {Object|null} WaveSurfer instance or null if not found
 */
function getTermWaveform(termId) {
    return WaveSurferInstances.termWaveforms.get(termId);
}

/**
 * Get full waveform WaveSurfer instance
 * @returns {Object|null} WaveSurfer instance or null if not initialized
 */
function getFullWaveform() {
    return WaveSurferInstances.fullWaveform;
}

/**
 * Destroy all WaveSurfer instances (cleanup)
 */
function destroyAllWaveforms() {
    // Destroy full waveform
    if (WaveSurferInstances.fullWaveform) {
        WaveSurferInstances.fullWaveform.instance.destroy();
        WaveSurferInstances.fullWaveform = null;
    }
    
    // Destroy all term waveforms
    WaveSurferInstances.termWaveforms.forEach((waveform) => {
        waveform.instance.destroy();
    });
    WaveSurferInstances.termWaveforms.clear();
    
    console.log('All WaveSurfer instances destroyed');
}

/**
 * Configure waveform rendering options
 * @param {Object} wavesurfer - WaveSurfer instance
 * @param {Object} options - Rendering options to update
 */
function configureWaveformOptions(wavesurfer, options) {
    // WaveSurfer v7 doesn't support runtime option changes for most properties
    // Options must be set during initialization
    // This function is a placeholder for any dynamic configuration needs
    console.log('Waveform options configured:', options);
}

/**
 * Task 8.2: Implement term waveform rendering
 */

/**
 * Create a term row in the alignment table
 * @param {Object} termAlignment - TermAlignment data
 * @returns {HTMLElement} The created term row element
 */
function createTermRow(termAlignment) {
    const row = document.createElement('div');
    row.className = 'term-row';
    row.id = `term-row-${termAlignment.term_id}`;
    row.dataset.termId = termAlignment.term_id;
    
    // Add classes based on state
    if (termAlignment.is_manually_adjusted) {
        row.classList.add('manually-adjusted');
    }
    if (termAlignment.confidence_score < 0.6) {
        row.classList.add('low-confidence');
    }
    
    // Term info column
    const termInfo = document.createElement('div');
    termInfo.className = 'term-info';
    termInfo.innerHTML = `
        <div class="term-english">${escapeHtml(termAlignment.english)}</div>
        <div class="term-cantonese">${escapeHtml(termAlignment.cantonese)}</div>
        <div class="term-id">#${termAlignment.term_id}</div>
    `;
    
    // Waveform column
    const waveformCell = document.createElement('div');
    waveformCell.className = 'waveform-cell';
    
    const waveformContainer = document.createElement('div');
    waveformContainer.className = 'term-waveform';
    waveformContainer.id = `waveform-${termAlignment.term_id}`;
    
    const boundaryTimes = document.createElement('div');
    boundaryTimes.className = 'boundary-times';
    boundaryTimes.innerHTML = `
        <span class="start-time">${formatTime(termAlignment.start_time)}</span>
        <span class="end-time">${formatTime(termAlignment.end_time)}</span>
    `;
    
    waveformCell.appendChild(waveformContainer);
    waveformCell.appendChild(boundaryTimes);
    
    // Controls column
    const controlsCell = document.createElement('div');
    controlsCell.className = 'controls-cell';
    
    const playBtn = document.createElement('button');
    playBtn.className = 'play-btn';
    playBtn.innerHTML = '▶ Play';
    playBtn.dataset.termId = termAlignment.term_id;
    playBtn.onclick = () => playTermAudio(termAlignment.term_id);
    
    controlsCell.appendChild(playBtn);
    
    // Add reset button if manually adjusted
    if (termAlignment.is_manually_adjusted) {
        const resetBtn = document.createElement('button');
        resetBtn.className = 'reset-btn';
        resetBtn.innerHTML = '↺ Reset';
        resetBtn.dataset.termId = termAlignment.term_id;
        resetBtn.onclick = () => resetTermAlignment(termAlignment.term_id);
        
        const adjustmentIndicator = document.createElement('div');
        adjustmentIndicator.className = 'adjustment-indicator';
        adjustmentIndicator.textContent = '✓ Manually adjusted';
        
        controlsCell.appendChild(resetBtn);
        controlsCell.appendChild(adjustmentIndicator);
    }
    
    // Quality column
    const qualityCell = document.createElement('div');
    qualityCell.className = 'quality-cell';
    
    const confidenceScore = termAlignment.confidence_score;
    const qualityLevel = confidenceScore >= 0.8 ? 'high' : confidenceScore >= 0.6 ? 'medium' : 'low';
    const qualityIcon = confidenceScore >= 0.8 ? '✓' : confidenceScore >= 0.6 ? '⚠' : '✗';
    
    // Tooltip text explaining quality levels (Requirement 10.5)
    const tooltipText = confidenceScore >= 0.8 
        ? 'High confidence: Automatic alignment is likely accurate'
        : confidenceScore >= 0.6
        ? 'Medium confidence: Review recommended'
        : 'Low confidence: Manual adjustment recommended';
    
    qualityCell.innerHTML = `
        <div class="quality-indicator ${qualityLevel}" title="${tooltipText}">${qualityIcon}</div>
        <div class="confidence-score ${qualityLevel}" title="${tooltipText}">${Math.round(confidenceScore * 100)}%</div>
        <div class="confidence-label">Confidence</div>
    `;
    
    // Assemble row
    row.appendChild(termInfo);
    row.appendChild(waveformCell);
    row.appendChild(controlsCell);
    row.appendChild(qualityCell);
    
    return row;
}

/**
 * Render waveform for a specific term
 * @param {string} termId - Term identifier
 * @param {string} audioUrl - URL to the audio segment
 * @param {number} startTime - Start time in seconds
 * @param {number} endTime - End time in seconds
 */
async function renderTermWaveform(termId, audioUrl, startTime, endTime) {
    const containerId = `waveform-${termId}`;
    
    try {
        // Initialize WaveSurfer for this term
        const wavesurfer = initializeTermWaveform(containerId, termId);
        
        // Load audio segment
        await wavesurfer.load(audioUrl);
        
        // Add boundary markers as regions
        const waveformData = getTermWaveform(termId);
        if (waveformData && waveformData.regions) {
            const duration = wavesurfer.getDuration();
            
            // Add a draggable region covering the entire segment
            const region = waveformData.regions.addRegion({
                id: `region-${termId}`,
                start: 0,
                end: duration,
                color: 'rgba(52, 152, 219, 0.2)',
                drag: true,  // Enable dragging
                resize: true, // Enable resizing (boundary adjustment)
                data: {
                    termId: termId,
                    startTime: startTime,
                    endTime: endTime
                }
            });
            
            // Set up drag event handlers for this region
            setupRegionDragHandlers(termId, waveformData.regions);
        }
        
        console.log(`Waveform rendered for term ${termId}`);
        
    } catch (error) {
        console.error(`Failed to render waveform for term ${termId}:`, error);
        showError(`Failed to load waveform for term ${termId}`);
    }
}

/**
 * Set up drag event handlers for a term's region
 * Task 10.1: Create draggable boundary markers
 * @param {string} termId - Term identifier
 * @param {Object} regionsPlugin - WaveSurfer regions plugin instance
 */
function setupRegionDragHandlers(termId, regionsPlugin) {
    // Listen for region update events (drag and resize)
    regionsPlugin.on('region-updated', (region) => {
        if (region.id === `region-${termId}`) {
            handleRegionUpdate(termId, region);
        }
    });
    
    // Listen for region update end (when user finishes dragging)
    regionsPlugin.on('region-update-end', (region) => {
        if (region.id === `region-${termId}`) {
            handleRegionUpdateEnd(termId, region);
        }
    });
    
    console.log(`Drag handlers set up for term ${termId}`);
}

/**
 * Handle region update during drag (real-time feedback)
 * Task 12.3: Ensure boundary adjustments work at all zoom levels
 * @param {string} termId - Term identifier
 * @param {Object} region - WaveSurfer region object
 */
function handleRegionUpdate(termId, region) {
    // Get the alignment data for this term
    const alignment = AppState.alignments.find(a => a.term_id === termId);
    if (!alignment) {
        return;
    }
    
    // Calculate new absolute times based on region position
    // Region times are relative to the audio segment, need to convert to absolute
    const segmentDuration = alignment.end_time - alignment.start_time;
    const newStart = alignment.start_time + (region.start * segmentDuration);
    const newEnd = alignment.start_time + (region.end * segmentDuration);
    
    // Validate boundaries don't overlap with adjacent terms
    const validationResult = validateBoundaries(termId, newStart, newEnd);
    
    if (!validationResult.valid) {
        // Show visual feedback for invalid boundaries
        region.element.style.borderColor = '#e74c3c'; // Red border
        console.warn(`Invalid boundaries for term ${termId}: ${validationResult.error}`);
        return;
    }
    
    // Valid boundaries - update visual feedback
    region.element.style.borderColor = '#2ecc71'; // Green border
    
    // Update boundary times display in real-time
    // Provide fine-grained time precision when zoomed (Requirement 6.4)
    updateBoundaryTimesDisplay(termId, newStart, newEnd);
}

/**
 * Handle region update end (finalize boundary adjustment)
 * Task 10.2: Implement boundary update synchronization
 * @param {string} termId - Term identifier
 * @param {Object} region - WaveSurfer region object
 */
async function handleRegionUpdateEnd(termId, region) {
    // Get the alignment data for this term
    const alignment = AppState.alignments.find(a => a.term_id === termId);
    if (!alignment) {
        return;
    }
    
    // Calculate new absolute times
    const segmentDuration = alignment.end_time - alignment.start_time;
    const newStart = alignment.start_time + (region.start * segmentDuration);
    const newEnd = alignment.start_time + (region.end * segmentDuration);
    
    // Validate boundaries
    const validationResult = validateBoundaries(termId, newStart, newEnd);
    
    if (!validationResult.valid) {
        // Revert to previous boundaries
        showError(validationResult.error);
        region.setOptions({
            start: 0,
            end: 1
        });
        region.element.style.borderColor = '';
        return;
    }
    
    // Reset border color
    region.element.style.borderColor = '';
    
    console.log(`Boundary adjustment completed for term ${termId}: ${newStart.toFixed(2)}s - ${newEnd.toFixed(2)}s`);
    
    // Send boundary update to backend API
    try {
        await sendBoundaryUpdate(termId, newStart, newEnd);
        
        // Update local state
        alignment.start_time = newStart;
        alignment.end_time = newEnd;
        alignment.is_manually_adjusted = true;
        
        // Update waveform display (already done by region)
        // Update playback to use new boundaries immediately (Requirement 4.4)
        await reloadTermAudio(termId, newStart, newEnd);
        
        // Mark term as manually adjusted (Requirement 4.5)
        markTermAsAdjusted(termId);
        
        // Update full waveform boundary markers (Task 10.3)
        updateFullWaveformBoundary(termId, newStart, newEnd);
        
        showSuccess(`Boundaries updated for "${alignment.english}"`);
        
    } catch (error) {
        console.error(`Failed to update boundaries for term ${termId}:`, error);
        showError(`Failed to save boundary update: ${error.message}`);
        
        // Revert to previous boundaries
        region.setOptions({
            start: 0,
            end: 1
        });
    }
}

/**
 * Send boundary update to backend API with improved error handling
 * Task 10.2: Send boundary updates to backend API
 * Task 19.1: Handle network errors gracefully
 * @param {string} termId - Term identifier
 * @param {number} startTime - New start time in seconds
 * @param {number} endTime - New end time in seconds
 * @returns {Promise} Promise that resolves when update is complete
 */
async function sendBoundaryUpdate(termId, startTime, endTime) {
    if (!AppState.sessionId) {
        throw new Error('No active session');
    }
    
    const response = await fetchWithRetry(`${API_BASE}/session/${AppState.sessionId}/update`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            term_id: termId,
            start_time: startTime,
            end_time: endTime
        })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.error || 'Failed to update boundaries');
    }
    
    console.log(`Boundary update sent to backend for term ${termId}`);
    
    return data;
}

/**
 * Reload audio for a term with new boundaries
 * Task 10.2: Update playback to use new boundaries immediately
 * @param {string} termId - Term identifier
 * @param {number} startTime - New start time in seconds
 * @param {number} endTime - New end time in seconds
 */
async function reloadTermAudio(termId, startTime, endTime) {
    const waveformData = getTermWaveform(termId);
    
    if (!waveformData) {
        return;
    }
    
    const wavesurfer = waveformData.instance;
    
    // Stop current playback if playing
    if (wavesurfer.isPlaying()) {
        wavesurfer.pause();
    }
    
    // Reload audio segment with new boundaries
    // The audio segment URL will be updated by the backend
    const audioUrl = `${API_BASE}/audio/${AppState.sessionId}/${termId}`;
    
    try {
        await wavesurfer.load(audioUrl);
        console.log(`Audio reloaded for term ${termId} with new boundaries`);
    } catch (error) {
        console.error(`Failed to reload audio for term ${termId}:`, error);
        // Non-fatal error - user can still continue
    }
}

/**
 * Mark a term as manually adjusted in the UI
 * Task 10.2: Mark term as manually adjusted
 * @param {string} termId - Term identifier
 */
function markTermAsAdjusted(termId) {
    const termRow = document.getElementById(`term-row-${termId}`);
    
    if (!termRow) {
        return;
    }
    
    // Add manually-adjusted class
    termRow.classList.add('manually-adjusted');
    
    // Check if reset button already exists
    const controlsCell = termRow.querySelector('.controls-cell');
    const existingResetBtn = controlsCell.querySelector('.reset-btn');
    
    if (!existingResetBtn) {
        // Add reset button
        const resetBtn = document.createElement('button');
        resetBtn.className = 'reset-btn';
        resetBtn.innerHTML = '↺ Reset';
        resetBtn.dataset.termId = termId;
        resetBtn.onclick = () => resetTermAlignment(termId);
        
        // Add adjustment indicator
        const adjustmentIndicator = document.createElement('div');
        adjustmentIndicator.className = 'adjustment-indicator';
        adjustmentIndicator.textContent = '✓ Manually adjusted';
        
        controlsCell.appendChild(resetBtn);
        controlsCell.appendChild(adjustmentIndicator);
    }
    
    console.log(`Term ${termId} marked as manually adjusted`);
}

/**
 * Validate that new boundaries don't overlap with adjacent terms
 * Task 10.1: Validate boundaries don't overlap adjacent terms
 * @param {string} termId - Term identifier
 * @param {number} newStart - New start time in seconds
 * @param {number} newEnd - New end time in seconds
 * @returns {Object} Validation result with 'valid' boolean and 'error' message
 */
function validateBoundaries(termId, newStart, newEnd) {
    // Basic validation
    if (newStart >= newEnd) {
        return {
            valid: false,
            error: 'Start time must be less than end time'
        };
    }
    
    if (newStart < 0) {
        return {
            valid: false,
            error: 'Start time cannot be negative'
        };
    }
    
    // Find the term index
    const termIndex = AppState.alignments.findIndex(a => a.term_id === termId);
    if (termIndex === -1) {
        return {
            valid: false,
            error: 'Term not found'
        };
    }
    
    // Check overlap with previous term
    if (termIndex > 0) {
        const prevTerm = AppState.alignments[termIndex - 1];
        if (newStart < prevTerm.end_time) {
            return {
                valid: false,
                error: `Start time overlaps with previous term "${prevTerm.english}" (ends at ${formatTime(prevTerm.end_time)})`
            };
        }
    }
    
    // Check overlap with next term
    if (termIndex < AppState.alignments.length - 1) {
        const nextTerm = AppState.alignments[termIndex + 1];
        if (newEnd > nextTerm.start_time) {
            return {
                valid: false,
                error: `End time overlaps with next term "${nextTerm.english}" (starts at ${formatTime(nextTerm.start_time)})`
            };
        }
    }
    
    // Check boundaries are within audio duration
    const session = AppState.currentSession;
    if (session && newEnd > session.audio_duration) {
        return {
            valid: false,
            error: `End time exceeds audio duration (${formatTime(session.audio_duration)})`
        };
    }
    
    return {
        valid: true,
        error: null
    };
}

/**
 * Update boundary times display for a term
 * @param {string} termId - Term identifier
 * @param {number} startTime - Start time in seconds
 * @param {number} endTime - End time in seconds
 */
function updateBoundaryTimesDisplay(termId, startTime, endTime) {
    const termRow = document.getElementById(`term-row-${termId}`);
    if (!termRow) {
        return;
    }
    
    const boundaryTimes = termRow.querySelector('.boundary-times');
    if (boundaryTimes) {
        boundaryTimes.innerHTML = `
            <span class="start-time">${formatTime(startTime)}</span>
            <span class="end-time">${formatTime(endTime)}</span>
        `;
    }
}

/**
 * Load and display all term alignments
 * @param {Array} alignments - Array of TermAlignment objects
 */
async function displayAlignments(alignments) {
    const alignmentRows = document.getElementById('alignment-rows');
    
    // Clear existing rows
    alignmentRows.innerHTML = '';
    
    // Store alignments in app state
    AppState.alignments = alignments;
    
    // Create and append rows
    for (const alignment of alignments) {
        const row = createTermRow(alignment);
        alignmentRows.appendChild(row);
        
        // Render waveform for this term
        // Audio URL will come from the session data
        if (alignment.audio_segment_url) {
            await renderTermWaveform(
                alignment.term_id,
                alignment.audio_segment_url,
                alignment.start_time,
                alignment.end_time
            );
        }
    }
    
    console.log(`Displayed ${alignments.length} term alignments`);
}

/**
 * Play audio for a specific term
 * Task 9.1: Create playback management system
 * @param {string} termId - Term identifier
 */
function playTermAudio(termId) {
    const waveformData = getTermWaveform(termId);
    
    if (!waveformData) {
        console.error(`No waveform found for term ${termId}`);
        showError(`Audio not loaded for this term`);
        return;
    }
    
    const wavesurfer = waveformData.instance;
    const playBtn = document.querySelector(`.play-btn[data-term-id="${termId}"]`);
    const termRow = document.getElementById(`term-row-${termId}`);
    
    if (!playBtn || !termRow) {
        console.error(`UI elements not found for term ${termId}`);
        return;
    }
    
    // Stop any currently playing audio when new audio starts (Requirement 3.5)
    if (AppState.currentlyPlaying && AppState.currentlyPlaying !== termId) {
        stopTermAudio(AppState.currentlyPlaying);
    }
    
    // Toggle play/pause
    if (wavesurfer.isPlaying()) {
        // Pause current playback
        wavesurfer.pause();
        updatePlaybackState(termId, 'ready');
    } else {
        // Start playback
        wavesurfer.play();
        updatePlaybackState(termId, 'playing');
        
        // Set up event listeners for playback state changes
        
        // When playback completes, return to ready state (Requirement 3.4)
        wavesurfer.once('finish', () => {
            updatePlaybackState(termId, 'ready');
            AppState.currentlyPlaying = null;
            console.log(`Playback completed for term ${termId}`);
        });
        
        // Handle playback errors
        wavesurfer.once('error', (error) => {
            console.error(`Playback error for term ${termId}:`, error);
            updatePlaybackState(termId, 'ready');
            AppState.currentlyPlaying = null;
            showError(`Failed to play audio for term ${termId}`);
        });
    }
}

/**
 * Update playback state for a term
 * Task 9.2: Implement playback state visualization
 * @param {string} termId - Term identifier
 * @param {string} state - Playback state: 'ready', 'playing', 'paused'
 */
function updatePlaybackState(termId, state) {
    const playBtn = document.querySelector(`.play-btn[data-term-id="${termId}"]`);
    const termRow = document.getElementById(`term-row-${termId}`);
    
    if (!playBtn || !termRow) {
        return;
    }
    
    // Remove all state classes
    playBtn.classList.remove('playing', 'paused', 'ready');
    termRow.classList.remove('playing-audio');
    
    // Update button and row based on state
    switch (state) {
        case 'playing':
            // Show active playback indicator (Requirement 3.3)
            playBtn.innerHTML = '⏸ Pause';
            playBtn.classList.add('playing');
            termRow.classList.add('playing-audio');
            AppState.currentlyPlaying = termId;
            console.log(`Playback started for term ${termId}`);
            break;
            
        case 'paused':
            playBtn.innerHTML = '▶ Play';
            playBtn.classList.add('paused');
            // Keep currentlyPlaying set for resume
            break;
            
        case 'ready':
        default:
            // Return to ready state (Requirement 3.4)
            playBtn.innerHTML = '▶ Play';
            playBtn.classList.add('ready');
            if (AppState.currentlyPlaying === termId) {
                AppState.currentlyPlaying = null;
            }
            break;
    }
}

/**
 * Stop audio playback for a specific term
 * Task 9.1: Create playback management system
 * @param {string} termId - Term identifier
 */
function stopTermAudio(termId) {
    const waveformData = getTermWaveform(termId);
    
    if (!waveformData) {
        return;
    }
    
    const wavesurfer = waveformData.instance;
    
    // Stop playback if playing
    if (wavesurfer.isPlaying()) {
        wavesurfer.pause();
        wavesurfer.seekTo(0); // Reset to beginning
    }
    
    // Update UI to ready state
    updatePlaybackState(termId, 'ready');
    
    console.log(`Playback stopped for term ${termId}`);
}

/**
 * Stop all audio playback
 * Task 9.1: Create playback management system
 */
function stopAllAudio() {
    if (AppState.currentlyPlaying) {
        stopTermAudio(AppState.currentlyPlaying);
    }
    
    // Also stop full waveform if playing
    const fullWaveform = getFullWaveform();
    if (fullWaveform && fullWaveform.instance.isPlaying()) {
        fullWaveform.instance.pause();
    }
    
    console.log('All audio playback stopped');
}

/**
 * Reset term alignment to original automatic boundaries
 * Task 15.1: Add individual term reset
 * @param {string} termId - Term identifier
 */
async function resetTermAlignment(termId) {
    // Get the alignment data for this term
    const alignment = AppState.alignments.find(a => a.term_id === termId);
    if (!alignment) {
        showError('Term not found');
        return;
    }
    
    // Request confirmation before resetting (Requirement 9.5)
    const confirmed = confirm(
        `Reset "${alignment.english}" to its original automatic alignment?\n\n` +
        `This will restore the boundaries to:\n` +
        `Start: ${formatTime(alignment.original_start)}\n` +
        `End: ${formatTime(alignment.original_end)}`
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        // Send reset request to backend
        const response = await fetch(`${API_BASE}/session/${AppState.sessionId}/reset/${termId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to reset term');
        }
        
        // Update local state with original boundaries (Requirement 9.2)
        alignment.start_time = alignment.original_start;
        alignment.end_time = alignment.original_end;
        alignment.is_manually_adjusted = false;
        
        // Update UI to remove manual adjustment indicator (Requirement 9.3)
        removeManualAdjustmentIndicator(termId);
        
        // Update waveform display with original boundaries
        await reloadTermWaveform(termId, alignment.start_time, alignment.end_time);
        
        // Update full waveform boundary markers
        updateFullWaveformBoundary(termId, alignment.start_time, alignment.end_time);
        
        // Update boundary times display
        updateBoundaryTimesDisplay(termId, alignment.start_time, alignment.end_time);
        
        showSuccess(`"${alignment.english}" reset to original alignment`);
        
        console.log(`Term ${termId} reset to original boundaries: ${alignment.start_time}s - ${alignment.end_time}s`);
        
    } catch (error) {
        console.error(`Failed to reset term ${termId}:`, error);
        showError(error.message || 'Failed to reset alignment');
    }
}

/**
 * Remove manual adjustment indicator from a term row
 * Task 15.1: Remove manual adjustment indicator
 * @param {string} termId - Term identifier
 */
function removeManualAdjustmentIndicator(termId) {
    const termRow = document.getElementById(`term-row-${termId}`);
    
    if (!termRow) {
        return;
    }
    
    // Remove manually-adjusted class
    termRow.classList.remove('manually-adjusted');
    
    // Remove reset button and adjustment indicator
    const controlsCell = termRow.querySelector('.controls-cell');
    if (controlsCell) {
        const resetBtn = controlsCell.querySelector('.reset-btn');
        const adjustmentIndicator = controlsCell.querySelector('.adjustment-indicator');
        
        if (resetBtn) {
            resetBtn.remove();
        }
        
        if (adjustmentIndicator) {
            adjustmentIndicator.remove();
        }
    }
    
    console.log(`Manual adjustment indicator removed for term ${termId}`);
}

/**
 * Reload term waveform with new boundaries
 * @param {string} termId - Term identifier
 * @param {number} startTime - Start time in seconds
 * @param {number} endTime - End time in seconds
 */
async function reloadTermWaveform(termId, startTime, endTime) {
    const waveformData = getTermWaveform(termId);
    
    if (!waveformData) {
        return;
    }
    
    const wavesurfer = waveformData.instance;
    
    // Stop current playback if playing
    if (wavesurfer.isPlaying()) {
        wavesurfer.pause();
    }
    
    // Reload audio segment with new boundaries
    const audioUrl = `${API_BASE}/audio/${AppState.sessionId}/${termId}`;
    
    try {
        await wavesurfer.load(audioUrl);
        
        // Update region to cover full segment
        if (waveformData.regions) {
            const regions = waveformData.regions.getRegions();
            const region = regions.find(r => r.id === `region-${termId}`);
            
            if (region) {
                const duration = wavesurfer.getDuration();
                region.setOptions({
                    start: 0,
                    end: duration
                });
            }
        }
        
        console.log(`Waveform reloaded for term ${termId} with boundaries: ${startTime}s - ${endTime}s`);
    } catch (error) {
        console.error(`Failed to reload waveform for term ${termId}:`, error);
        // Non-fatal error - user can still continue
    }
}

/**
 * Reset all terms to original automatic alignments
 * Task 15.2: Add reset all functionality
 */
async function resetAllTerms() {
    // Count manually adjusted terms
    const adjustedTerms = AppState.alignments.filter(a => a.is_manually_adjusted);
    
    if (adjustedTerms.length === 0) {
        showError('No manually adjusted terms to reset');
        return;
    }
    
    // Request confirmation before resetting all (Requirement 9.5)
    const confirmed = confirm(
        `Reset all ${adjustedTerms.length} manually adjusted terms to their original automatic alignments?\n\n` +
        `This action will restore all terms to their original boundaries.`
    );
    
    if (!confirmed) {
        return;
    }
    
    // Disable reset all button during operation
    const resetAllBtn = document.getElementById('reset-all-btn');
    if (resetAllBtn) {
        resetAllBtn.disabled = true;
        resetAllBtn.innerHTML = '<span class="btn-icon">⏳</span> Resetting...';
    }
    
    try {
        // Send reset all request to backend
        const response = await fetch(`${API_BASE}/session/${AppState.sessionId}/reset-all`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to reset all terms');
        }
        
        // Update local state for all terms (Requirement 9.4)
        for (const alignment of AppState.alignments) {
            if (alignment.is_manually_adjusted) {
                alignment.start_time = alignment.original_start;
                alignment.end_time = alignment.original_end;
                alignment.is_manually_adjusted = false;
                
                // Update UI for each term
                removeManualAdjustmentIndicator(alignment.term_id);
                updateBoundaryTimesDisplay(alignment.term_id, alignment.start_time, alignment.end_time);
                
                // Reload waveform
                await reloadTermWaveform(alignment.term_id, alignment.start_time, alignment.end_time);
            }
        }
        
        // Refresh full waveform with all updated boundaries
        refreshFullWaveform(AppState.alignments);
        
        const resetCount = data.data.reset_count;
        showSuccess(`All ${resetCount} manually adjusted terms reset to original alignment`);
        
        console.log(`Reset all: ${resetCount} terms restored to original boundaries`);
        
    } catch (error) {
        console.error('Failed to reset all terms:', error);
        showError(error.message || 'Failed to reset all terms');
    } finally {
        // Re-enable reset all button
        if (resetAllBtn) {
            resetAllBtn.disabled = false;
            resetAllBtn.innerHTML = '<span class="btn-icon">↺</span> Reset All';
        }
    }
}

/**
 * Set up reset all button event listener
 * Task 15.2: Implement "Reset All" button
 */
function setupResetAllButton() {
    const resetAllBtn = document.getElementById('reset-all-btn');
    
    if (resetAllBtn) {
        resetAllBtn.addEventListener('click', resetAllTerms);
        console.log('Reset All button initialized');
    }
}

/**
 * Format time in seconds to MM:SS or MM:SS.mmm format
 * Task 12.3: Provide fine-grained time precision when zoomed
 * @param {number} seconds - Time in seconds
 * @param {boolean} showMilliseconds - Whether to show milliseconds (default: auto based on zoom)
 * @returns {string} Formatted time string
 */
function formatTime(seconds, showMilliseconds = null) {
    // Auto-determine if we should show milliseconds based on zoom level
    // Show milliseconds when zoomed in beyond 10x for fine-grained precision
    const shouldShowMs = showMilliseconds !== null 
        ? showMilliseconds 
        : ZoomState.level >= 10;
    
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    
    if (shouldShowMs) {
        const ms = Math.floor((seconds % 1) * 1000);
        return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
    }
    
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Task 8.3: Implement full waveform overview
 */

// Zoom state management
const ZoomState = {
    level: 1,
    minZoom: 1,
    maxZoom: 100,
    currentRange: { start: 0, end: 0 },
    isPanning: false,
    panStartX: 0,
    panStartScrollLeft: 0
};

/**
 * Initialize and render the full waveform overview
 * @param {string} audioUrl - URL to the full audio file
 * @param {Array} alignments - Array of TermAlignment objects
 */
async function renderFullWaveform(audioUrl, alignments) {
    const containerId = 'full-waveform';
    
    try {
        // Initialize full waveform WaveSurfer
        const wavesurfer = initializeFullWaveform(containerId);
        
        // Load full audio file
        await wavesurfer.load(audioUrl);
        
        const duration = wavesurfer.getDuration();
        ZoomState.currentRange = { start: 0, end: duration };
        
        // Update time range display
        updateTimeRangeDisplay(0, duration);
        
        // Add boundary markers for all terms
        addTermBoundaryMarkers(alignments);
        
        // Set up zoom and pan controls
        setupZoomControls(wavesurfer);
        
        // Set up waveform click navigation
        setupWaveformNavigation(wavesurfer);
        
        console.log('Full waveform rendered successfully');
        
    } catch (error) {
        console.error('Failed to render full waveform:', error);
        showError('Failed to load full audio waveform');
    }
}

/**
 * Add boundary markers for all terms to the full waveform
 * @param {Array} alignments - Array of TermAlignment objects
 */
function addTermBoundaryMarkers(alignments) {
    const waveformData = getFullWaveform();
    
    if (!waveformData || !waveformData.regions) {
        console.error('Full waveform not initialized');
        return;
    }
    
    const regions = waveformData.regions;
    
    // Clear existing regions
    regions.clearRegions();
    
    // Add a region for each term
    alignments.forEach((alignment, index) => {
        const color = alignment.is_manually_adjusted 
            ? 'rgba(243, 156, 18, 0.3)' // Orange for manually adjusted
            : alignment.confidence_score < 0.6
            ? 'rgba(231, 76, 60, 0.3)' // Red for low confidence
            : 'rgba(52, 152, 219, 0.3)'; // Blue for normal
        
        regions.addRegion({
            id: `region-${alignment.term_id}`,
            start: alignment.start_time,
            end: alignment.end_time,
            color: color,
            drag: false,
            resize: false,
            content: `${alignment.english}`,
            data: {
                termId: alignment.term_id,
                english: alignment.english,
                cantonese: alignment.cantonese
            }
        });
    });
    
    console.log(`Added ${alignments.length} boundary markers to full waveform`);
}

/**
 * Set up zoom and pan controls for the full waveform
 * Task 12.1: Add zoom controls to full waveform
 * Task 12.2: Implement pan navigation
 * @param {Object} wavesurfer - WaveSurfer instance
 */
function setupZoomControls(wavesurfer) {
    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');
    const zoomSlider = document.getElementById('zoom-slider');
    const waveformContainer = document.getElementById('full-waveform');
    
    // Zoom in button - increase zoom by 10 levels
    zoomInBtn.addEventListener('click', () => {
        const newZoom = Math.min(ZoomState.level + 10, ZoomState.maxZoom);
        setZoomLevel(wavesurfer, newZoom);
    });
    
    // Zoom out button - decrease zoom by 10 levels
    zoomOutBtn.addEventListener('click', () => {
        const newZoom = Math.max(ZoomState.level - 10, ZoomState.minZoom);
        setZoomLevel(wavesurfer, newZoom);
    });
    
    // Zoom slider - precise zoom control
    zoomSlider.addEventListener('input', (e) => {
        const newZoom = parseInt(e.target.value);
        setZoomLevel(wavesurfer, newZoom);
    });
    
    // Enable scrolling for panning when zoomed (Requirement 6.3)
    waveformContainer.addEventListener('scroll', () => {
        updateVisibleTimeRange(wavesurfer);
    });
    
    // Implement click-and-drag panning (Requirement 6.3)
    setupDragPanning(waveformContainer);
    
    // Keyboard shortcuts for zoom
    document.addEventListener('keydown', (e) => {
        // Only handle if waveform is focused or no input is focused
        if (document.activeElement.tagName === 'INPUT' || 
            document.activeElement.tagName === 'TEXTAREA') {
            return;
        }
        
        // Ctrl/Cmd + Plus/Equals for zoom in
        if ((e.ctrlKey || e.metaKey) && (e.key === '+' || e.key === '=')) {
            e.preventDefault();
            const newZoom = Math.min(ZoomState.level + 5, ZoomState.maxZoom);
            setZoomLevel(wavesurfer, newZoom);
        }
        
        // Ctrl/Cmd + Minus for zoom out
        if ((e.ctrlKey || e.metaKey) && e.key === '-') {
            e.preventDefault();
            const newZoom = Math.max(ZoomState.level - 5, ZoomState.minZoom);
            setZoomLevel(wavesurfer, newZoom);
        }
        
        // Ctrl/Cmd + 0 to reset zoom
        if ((e.ctrlKey || e.metaKey) && e.key === '0') {
            e.preventDefault();
            setZoomLevel(wavesurfer, 1);
        }
    });
    
    console.log('Zoom and pan controls initialized');
}

/**
 * Set up click-and-drag panning for the waveform container
 * Task 12.2: Implement click-and-drag panning
 * @param {HTMLElement} container - Waveform container element
 */
function setupDragPanning(container) {
    let isDragging = false;
    let startX = 0;
    let scrollLeft = 0;
    
    // Mouse down - start dragging
    container.addEventListener('mousedown', (e) => {
        // Only enable drag panning when zoomed in
        if (ZoomState.level <= 1) {
            return;
        }
        
        // Don't interfere with region dragging
        if (e.target.closest('.wavesurfer-region')) {
            return;
        }
        
        isDragging = true;
        startX = e.pageX - container.offsetLeft;
        scrollLeft = container.scrollLeft;
        container.style.cursor = 'grabbing';
        container.style.userSelect = 'none';
        
        ZoomState.isPanning = true;
        ZoomState.panStartX = startX;
        ZoomState.panStartScrollLeft = scrollLeft;
    });
    
    // Mouse leave - stop dragging
    container.addEventListener('mouseleave', () => {
        if (isDragging) {
            isDragging = false;
            container.style.cursor = 'default';
            container.style.userSelect = 'auto';
            ZoomState.isPanning = false;
        }
    });
    
    // Mouse up - stop dragging
    container.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            container.style.cursor = 'default';
            container.style.userSelect = 'auto';
            ZoomState.isPanning = false;
        }
    });
    
    // Mouse move - perform panning
    container.addEventListener('mousemove', (e) => {
        if (!isDragging) {
            // Show grab cursor when zoomed and hovering
            if (ZoomState.level > 1 && !e.target.closest('.wavesurfer-region')) {
                container.style.cursor = 'grab';
            } else {
                container.style.cursor = 'default';
            }
            return;
        }
        
        e.preventDefault();
        const x = e.pageX - container.offsetLeft;
        const walk = (x - startX) * 2; // Multiply for faster panning
        container.scrollLeft = scrollLeft - walk;
    });
    
    console.log('Drag panning initialized');
}

/**
 * Set zoom level for the waveform
 * Task 12.1: Update waveform display at different zoom levels
 * Task 12.3: Maintain adjustment precision while zoomed
 * @param {Object} wavesurfer - WaveSurfer instance
 * @param {number} zoomLevel - Zoom level (1-100)
 */
function setZoomLevel(wavesurfer, zoomLevel) {
    // Clamp zoom level to valid range
    zoomLevel = Math.max(ZoomState.minZoom, Math.min(zoomLevel, ZoomState.maxZoom));
    
    ZoomState.level = zoomLevel;
    
    // Update zoom slider
    const zoomSlider = document.getElementById('zoom-slider');
    if (zoomSlider) {
        zoomSlider.value = zoomLevel;
    }
    
    // Update zoom level display (Requirement 6.5)
    const zoomLevelDisplay = document.getElementById('zoom-level');
    if (zoomLevelDisplay) {
        zoomLevelDisplay.textContent = `Zoom: ${zoomLevel}x`;
    }
    
    // Apply zoom to WaveSurfer
    // minPxPerSec controls zoom level - higher values = more zoomed in
    // Base value of 50 pixels per second at 1x zoom
    const minPxPerSec = 50 * zoomLevel;
    wavesurfer.zoom(minPxPerSec);
    
    // Update visible time range display (Requirement 6.5)
    updateVisibleTimeRange(wavesurfer);
    
    // Enable/disable zoom buttons based on limits
    updateZoomButtonStates();
    
    console.log(`Zoom level set to ${zoomLevel}x (${minPxPerSec} px/sec)`);
}

/**
 * Update zoom button states based on current zoom level
 */
function updateZoomButtonStates() {
    const zoomInBtn = document.getElementById('zoom-in-btn');
    const zoomOutBtn = document.getElementById('zoom-out-btn');
    
    if (zoomInBtn) {
        zoomInBtn.disabled = ZoomState.level >= ZoomState.maxZoom;
    }
    
    if (zoomOutBtn) {
        zoomOutBtn.disabled = ZoomState.level <= ZoomState.minZoom;
    }
}

/**
 * Update the visible time range display
 * Task 12.2: Update visible time range display
 * @param {Object} wavesurfer - WaveSurfer instance
 */
function updateVisibleTimeRange(wavesurfer) {
    const duration = wavesurfer.getDuration();
    const container = document.getElementById('full-waveform');
    
    if (!container || !duration) {
        return;
    }
    
    const scrollLeft = container.scrollLeft;
    const containerWidth = container.clientWidth;
    const totalWidth = container.scrollWidth;
    
    // Calculate visible time range based on scroll position
    // When not zoomed, totalWidth equals containerWidth
    const startTime = totalWidth > containerWidth 
        ? (scrollLeft / totalWidth) * duration 
        : 0;
    const endTime = totalWidth > containerWidth
        ? ((scrollLeft + containerWidth) / totalWidth) * duration
        : duration;
    
    ZoomState.currentRange = { start: startTime, end: endTime };
    
    // Update time range display (Requirement 6.5)
    updateTimeRangeDisplay(startTime, endTime);
}

/**
 * Update time range display text
 * Task 12.2: Update visible time range display
 * @param {number} startTime - Start time in seconds
 * @param {number} endTime - End time in seconds
 */
function updateTimeRangeDisplay(startTime, endTime) {
    const timeRangeDisplay = document.getElementById('time-range');
    if (timeRangeDisplay) {
        timeRangeDisplay.textContent = `${formatTime(startTime)} - ${formatTime(endTime)}`;
    }
}

/**
 * Set up click navigation on the full waveform
 * @param {Object} wavesurfer - WaveSurfer instance
 */
function setupWaveformNavigation(wavesurfer) {
    const waveformData = getFullWaveform();
    
    if (!waveformData || !waveformData.regions) {
        return;
    }
    
    // Listen for region clicks
    waveformData.regions.on('region-clicked', (region, e) => {
        e.stopPropagation();
        
        const termId = region.data?.termId;
        
        if (termId) {
            // Scroll to and highlight the corresponding term row
            scrollToTermRow(termId);
            highlightTermRow(termId);
        }
    });
    
    console.log('Waveform navigation initialized');
}

/**
 * Scroll to a specific term row in the alignment table
 * @param {string} termId - Term identifier
 */
function scrollToTermRow(termId) {
    const termRow = document.getElementById(`term-row-${termId}`);
    
    if (termRow) {
        termRow.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }
}

/**
 * Highlight a specific term row
 * @param {string} termId - Term identifier
 * @param {number} duration - Highlight duration in milliseconds
 */
function highlightTermRow(termId, duration = 2000) {
    // Remove existing highlights
    document.querySelectorAll('.term-row.highlighted').forEach(row => {
        row.classList.remove('highlighted');
    });
    
    // Add highlight to target row
    const termRow = document.getElementById(`term-row-${termId}`);
    
    if (termRow) {
        termRow.classList.add('highlighted');
        
        // Remove highlight after duration
        setTimeout(() => {
            termRow.classList.remove('highlighted');
        }, duration);
    }
}

/**
 * Update full waveform boundary markers when term boundaries change
 * @param {string} termId - Term identifier
 * @param {number} newStart - New start time
 * @param {number} newEnd - New end time
 */
function updateFullWaveformBoundary(termId, newStart, newEnd) {
    const waveformData = getFullWaveform();
    
    if (!waveformData || !waveformData.regions) {
        return;
    }
    
    const regions = waveformData.regions;
    const regionId = `region-${termId}`;
    
    // Find and update the region
    const allRegions = regions.getRegions();
    const region = allRegions.find(r => r.id === regionId);
    
    if (region) {
        // Update region boundaries
        region.setOptions({
            start: newStart,
            end: newEnd
        });
        
        console.log(`Updated full waveform boundary for term ${termId}`);
    }
}

/**
 * Refresh full waveform with updated alignments
 * @param {Array} alignments - Updated array of TermAlignment objects
 */
function refreshFullWaveform(alignments) {
    const waveformData = getFullWaveform();
    
    if (!waveformData) {
        console.error('Full waveform not initialized');
        return;
    }
    
    // Re-add all boundary markers with updated data
    addTermBoundaryMarkers(alignments);
    
    console.log('Full waveform refreshed with updated alignments');
}

/**
 * Task 14.1: Create save progress functionality
 */

/**
 * Save current session progress
 * Sends current session state to backend and displays confirmation
 */
async function saveSessionProgress() {
    if (!AppState.sessionId) {
        showError('No active session to save');
        return;
    }
    
    const saveBtn = document.getElementById('save-btn');
    
    // Disable button during save
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="btn-icon">⏳</span> Saving...';
    }
    
    try {
        const response = await fetch(`${API_BASE}/session/${AppState.sessionId}/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to save session');
        }
        
        // Display save confirmation with details
        const adjustedCount = data.data.manually_adjusted_count;
        const totalCount = data.data.total_terms;
        const message = adjustedCount > 0 
            ? `Session saved! ${adjustedCount} of ${totalCount} terms manually adjusted.`
            : `Session saved! ${totalCount} terms ready.`;
        
        showSuccess(message);
        
        console.log('Session saved successfully:', data.data);
        
    } catch (error) {
        console.error('Failed to save session:', error);
        showError(error.message || 'Failed to save session. Please try again.');
    } finally {
        // Re-enable button
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<span class="btn-icon">💾</span> Save Progress';
        }
    }
}

/**
 * Set up save button event listener
 */
function setupSaveButton() {
    const saveBtn = document.getElementById('save-btn');
    
    if (saveBtn) {
        saveBtn.addEventListener('click', saveSessionProgress);
        console.log('Save button initialized');
    }
}

/**
 * Task 14.2: Implement session loading
 */

/**
 * Get session ID from URL parameters
 * @returns {string|null} Session ID if present in URL, null otherwise
 */
function getSessionIdFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('session');
}

/**
 * Update URL with session ID for sharing/bookmarking
 * @param {string} sessionId - Session identifier
 */
function updateUrlWithSessionId(sessionId) {
    const url = new URL(window.location);
    url.searchParams.set('session', sessionId);
    window.history.pushState({}, '', url);
    console.log(`URL updated with session ID: ${sessionId}`);
}

/**
 * Load saved session on page load if session ID is present in URL
 */
async function loadSessionFromUrl() {
    const sessionId = getSessionIdFromUrl();
    
    if (!sessionId) {
        console.log('No session ID in URL, starting fresh');
        return;
    }
    
    console.log(`Loading session from URL: ${sessionId}`);
    
    try {
        // Show loading state
        showSuccess('Loading saved session...');
        
        // Fetch session data
        const response = await fetch(`${API_BASE}/session/${sessionId}`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to load session');
        }
        
        // Validate original files are still accessible (Requirement 8.5)
        const validationResult = await validateSessionFiles(data.data);
        
        if (!validationResult.valid) {
            showError(validationResult.error);
            // Clear session ID from URL
            const url = new URL(window.location);
            url.searchParams.delete('session');
            window.history.pushState({}, '', url);
            return;
        }
        
        // Store session data in app state
        AppState.sessionId = sessionId;
        AppState.currentSession = data.data;
        AppState.alignments = data.data.terms;
        
        // Hide upload section and show alignment section
        elements.uploadSection.style.display = 'none';
        const alignmentSection = document.getElementById('alignment-section');
        if (alignmentSection) {
            alignmentSection.style.display = 'block';
        }
        
        // Restore all boundary positions and adjustment flags (Requirement 8.3)
        await displayAlignments(data.data.terms);
        
        // Render full waveform with all boundaries
        const audioUrl = `${API_BASE}/audio/${sessionId}/full`;
        await renderFullWaveform(audioUrl, data.data.terms);
        
        // Show success message
        const adjustedCount = data.data.manually_adjusted_count;
        const message = adjustedCount > 0
            ? `Session loaded! ${adjustedCount} terms have manual adjustments.`
            : `Session loaded! ${data.data.total_terms} terms ready for review.`;
        
        showSuccess(message);
        
        console.log('Session loaded successfully:', data.data);
        
    } catch (error) {
        console.error('Failed to load session:', error);
        showError(`Failed to load session: ${error.message}`);
        
        // Clear session ID from URL on error
        const url = new URL(window.location);
        url.searchParams.delete('session');
        window.history.pushState({}, '', url);
    }
}

/**
 * Validate that original files for a session are still accessible
 * @param {Object} sessionData - Session data object
 * @returns {Object} Validation result with 'valid' boolean and 'error' message
 */
async function validateSessionFiles(sessionData) {
    // Check if audio file path exists
    if (!sessionData.audio_file_path) {
        return {
            valid: false,
            error: 'Session audio file path is missing. The original files may have been moved or deleted.'
        };
    }
    
    // Check if document URL is accessible
    if (!sessionData.doc_url) {
        return {
            valid: false,
            error: 'Session document URL is missing. The original files may have been moved or deleted.'
        };
    }
    
    // Try to access the first audio segment to verify files are accessible
    try {
        if (sessionData.terms && sessionData.terms.length > 0) {
            const firstTerm = sessionData.terms[0];
            const audioUrl = `${API_BASE}/audio/${sessionData.session_id}/${firstTerm.term_id}`;
            
            const response = await fetch(audioUrl, { method: 'HEAD' });
            
            if (!response.ok) {
                return {
                    valid: false,
                    error: 'Original audio file is no longer accessible. The file may have been moved or deleted.'
                };
            }
        }
    } catch (error) {
        return {
            valid: false,
            error: `Failed to verify audio file accessibility: ${error.message}`
        };
    }
    
    return {
        valid: true,
        error: null
    };
}

/**
 * Initialize session loading on page load
 */
function initSessionLoading() {
    // Check for session ID in URL and load if present
    loadSessionFromUrl();
}

/**
 * Task 16.2: Add sorting and filtering by quality
 */

/**
 * Set up sorting and filtering controls for the alignment table
 */
function setupQualityControls() {
    const showLowConfidenceCheckbox = document.getElementById('show-low-confidence');
    const sortBySelect = document.getElementById('sort-by');
    const qualityHelpBtn = document.getElementById('quality-help-btn');
    const closeHelpBtn = document.getElementById('close-help-btn');
    const helpPanel = document.getElementById('quality-help-panel');
    
    if (showLowConfidenceCheckbox) {
        showLowConfidenceCheckbox.addEventListener('change', applyFiltersAndSort);
        console.log('Low confidence filter initialized');
    }
    
    if (sortBySelect) {
        sortBySelect.addEventListener('change', applyFiltersAndSort);
        console.log('Sort control initialized');
    }
    
    // Set up help panel toggle (Requirement 10.5)
    if (qualityHelpBtn && helpPanel) {
        qualityHelpBtn.addEventListener('click', () => {
            const isVisible = helpPanel.style.display !== 'none';
            helpPanel.style.display = isVisible ? 'none' : 'block';
            console.log(`Quality help panel ${isVisible ? 'hidden' : 'shown'}`);
        });
        console.log('Quality help button initialized');
    }
    
    if (closeHelpBtn && helpPanel) {
        closeHelpBtn.addEventListener('click', () => {
            helpPanel.style.display = 'none';
            console.log('Quality help panel closed');
        });
        console.log('Close help button initialized');
    }
}

/**
 * Apply current filters and sorting to the alignment table
 * Requirement 10.3: Provide sorting or filtering options to show low-confidence alignments first
 */
function applyFiltersAndSort() {
    if (!AppState.alignments || AppState.alignments.length === 0) {
        return;
    }
    
    // Get current filter and sort settings
    const showLowConfidenceCheckbox = document.getElementById('show-low-confidence');
    const sortBySelect = document.getElementById('sort-by');
    
    const showOnlyLowConfidence = showLowConfidenceCheckbox?.checked || false;
    const sortBy = sortBySelect?.value || 'order';
    
    // Start with all alignments
    let filteredAlignments = [...AppState.alignments];
    
    // Apply filter: show only low-confidence terms (Requirement 10.3)
    if (showOnlyLowConfidence) {
        filteredAlignments = filteredAlignments.filter(alignment => alignment.confidence_score < 0.6);
        console.log(`Filtered to ${filteredAlignments.length} low-confidence terms`);
    }
    
    // Apply sorting (Requirement 10.3)
    switch (sortBy) {
        case 'confidence':
            // Sort by confidence score (low first)
            filteredAlignments.sort((a, b) => a.confidence_score - b.confidence_score);
            console.log('Sorted by confidence (low first)');
            break;
            
        case 'adjusted':
            // Sort by manually adjusted (adjusted first)
            filteredAlignments.sort((a, b) => {
                if (a.is_manually_adjusted === b.is_manually_adjusted) {
                    return 0;
                }
                return a.is_manually_adjusted ? -1 : 1;
            });
            console.log('Sorted by manual adjustment');
            break;
            
        case 'order':
        default:
            // Keep original order (already in order from AppState.alignments)
            console.log('Using original order');
            break;
    }
    
    // Update the table display with filtered and sorted alignments
    updateAlignmentTableDisplay(filteredAlignments);
}

/**
 * Update the alignment table display with a specific set of alignments
 * @param {Array} alignments - Array of TermAlignment objects to display
 */
async function updateAlignmentTableDisplay(alignments) {
    const alignmentRows = document.getElementById('alignment-rows');
    
    if (!alignmentRows) {
        return;
    }
    
    // Clear existing rows
    alignmentRows.innerHTML = '';
    
    // If no alignments match the filter, show a message
    if (alignments.length === 0) {
        const emptyMessage = document.createElement('div');
        emptyMessage.className = 'empty-message';
        emptyMessage.style.padding = '40px';
        emptyMessage.style.textAlign = 'center';
        emptyMessage.style.color = '#7f8c8d';
        emptyMessage.innerHTML = `
            <p style="font-size: 1.2em; margin-bottom: 10px;">No terms match the current filter</p>
            <p style="font-size: 0.9em;">Try adjusting your filter settings</p>
        `;
        alignmentRows.appendChild(emptyMessage);
        return;
    }
    
    // Create and append rows for filtered/sorted alignments
    for (const alignment of alignments) {
        const row = createTermRow(alignment);
        alignmentRows.appendChild(row);
        
        // Render waveform for this term (only if not already rendered)
        if (alignment.audio_segment_url) {
            // Check if waveform already exists
            const existingWaveform = getTermWaveform(alignment.term_id);
            if (!existingWaveform) {
                await renderTermWaveform(
                    alignment.term_id,
                    alignment.audio_segment_url,
                    alignment.start_time,
                    alignment.end_time
                );
            }
        }
    }
    
    console.log(`Updated table display with ${alignments.length} terms`);
}

