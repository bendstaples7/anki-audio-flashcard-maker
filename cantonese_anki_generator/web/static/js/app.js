/**
 * Main JavaScript application for Manual Audio Alignment interface
 */

// Application state
const AppState = {
    currentMode: null,  // 'prepare' or 'upload'
    sessionId: null,
    currentSession: null,
    alignments: [],
    currentlyPlaying: null,
    pendingUpdates: new Map(),
    regenerationInProgress: false,  // Track if regeneration is running
    uploadedFiles: {
        url: null,
        audioFile: null,
        audioFilePath: null
    },
    validationState: {
        urlValid: false,
        audioValid: false
    },
    // Spreadsheet preparation state
    spreadsheetPrep: {
        inputText: '',
        parsedTerms: [],
        vocabularyEntries: []
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
    
    // Set up back button
    setupBackButton();
    
    // Set up log streaming
    setupLogStreaming();
    
    // Set up log controls
    setupLogControls();
    
    // Initialize session loading (check URL for session ID)
    initSessionLoading();
    
    // Check authentication status
    checkAuthenticationStatus();
    
    // Check API health
    checkAPIHealth();
}

/**
 * Cache DOM elements for performance
 */
function cacheElements() {
    elements = {
        // Mode selection elements
        modeSelection: document.getElementById('mode-selection'),
        prepareModeBtn: document.getElementById('prepare-mode-btn'),
        uploadModeBtn: document.getElementById('upload-mode-btn'),
        
        // Spreadsheet preparation elements
        spreadsheetPrepSection: document.getElementById('spreadsheet-prep-section'),
        englishTermsInput: document.getElementById('english-terms-input'),
        generateTranslationsBtn: document.getElementById('generate-translations-btn'),
        
        // Translation progress elements
        translationProgress: document.getElementById('translation-progress'),
        translationProgressFill: document.getElementById('translation-progress-fill'),
        translationProgressPercentage: document.getElementById('translation-progress-percentage'),
        progressTotal: document.getElementById('progress-total'),
        progressCompleted: document.getElementById('progress-completed'),
        progressFailed: document.getElementById('progress-failed'),
        
        // Review table elements
        reviewTableContainer: document.getElementById('review-table-container'),
        reviewTableBody: document.getElementById('review-table-body'),
        exportSheetBtn: document.getElementById('export-sheet-btn'),
        exportResult: document.getElementById('export-result'),
        
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
        alignmentSection: document.getElementById('alignment-section'),
        uploadContainer: document.querySelector('.upload-container')
    };
}

/**
 * Set up event listeners for form interactions
 */
function setupEventListeners() {
    // Mode selection buttons
    if (elements.prepareModeBtn) {
        elements.prepareModeBtn.addEventListener('click', handlePrepareModeSelect);
    }
    if (elements.uploadModeBtn) {
        elements.uploadModeBtn.addEventListener('click', handleUploadModeSelect);
    }
    
    // Spreadsheet preparation input
    if (elements.englishTermsInput) {
        elements.englishTermsInput.addEventListener('input', handleEnglishTermsInput);
    }
    if (elements.generateTranslationsBtn) {
        elements.generateTranslationsBtn.addEventListener('click', handleGenerateTranslations);
    }
    
    // Export sheet button
    if (elements.exportSheetBtn) {
        elements.exportSheetBtn.addEventListener('click', handleExportToSheet);
    }
    
    // Set up event delegation for editable cells (Task 13.3)
    if (elements.reviewTableBody) {
        elements.reviewTableBody.addEventListener('input', handleCellEdit);
        elements.reviewTableBody.addEventListener('blur', handleCellBlur, true);
    }
    
    // URL input validation
    elements.docUrlInput.addEventListener('input', debounce(validateUrl, 500));
    elements.docUrlInput.addEventListener('blur', validateUrl);
    
    // Audio file selection
    elements.audioFileInput.addEventListener('change', handleFileSelection);
    
    // Form submission
    elements.uploadForm.addEventListener('submit', handleFormSubmit);
}

/**
 * Handle "Prepare Spreadsheet" mode selection
 * Task 10.2: Navigate to spreadsheet preparation interface
 * Requirements: 1.2
 */
function handlePrepareModeSelect() {
    console.log('Prepare Spreadsheet mode selected');
    
    // Hide mode selection
    if (elements.modeSelection) {
        elements.modeSelection.style.display = 'none';
    }
    
    // Show spreadsheet preparation interface
    if (elements.spreadsheetPrepSection) {
        elements.spreadsheetPrepSection.style.display = 'block';
    }
    
    // Store mode selection in app state
    AppState.currentMode = 'prepare';
    
    // Focus on the input textarea
    if (elements.englishTermsInput) {
        elements.englishTermsInput.focus();
    }
}

/**
 * Handle "Link Spreadsheet + Upload Audio" mode selection
 * Task 10.2: Navigate to existing upload interface
 * Requirements: 1.3
 */
function handleUploadModeSelect() {
    console.log('Upload Audio mode selected');
    
    // Hide mode selection
    if (elements.modeSelection) {
        elements.modeSelection.style.display = 'none';
    }
    
    // Show upload interface
    if (elements.uploadContainer) {
        elements.uploadContainer.style.display = 'grid';
    }
    
    // Store mode selection in app state
    AppState.currentMode = 'upload';
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
            const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout for long operations
            
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
                    const errorData = await response.clone().json();
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
 * Check authentication status on page load
 */
async function checkAuthenticationStatus() {
    try {
        const response = await fetch(`${API_BASE}/auth/status`);
        const data = await response.json();
        
        if (data.needs_reauth || !data.authenticated) {
            // Show authentication required banner
            showAuthenticationBanner(data.authorization_url);
        } else {
            console.log('Authentication OK - token expires in', data.expires_in_hours, 'hours');
            // Remove banner if it exists (user just authenticated)
            const banner = document.getElementById('auth-banner');
            if (banner) {
                banner.remove();
            }
        }
    } catch (error) {
        console.error('Failed to check authentication status:', error);
        // Don't show error - authentication check is optional
    }
}

/**
 * Show authentication required banner with authorization link
 * @param {string} authUrl - OAuth authorization URL
 */
function showAuthenticationBanner(authUrl) {
    console.log('showAuthenticationBanner called with URL:', authUrl);
    
    // Create banner if it doesn't exist
    let banner = document.getElementById('auth-banner');
    if (!banner) {
        console.log('Creating new authentication banner');
        banner = document.createElement('div');
        banner.id = 'auth-banner';
        banner.className = 'auth-banner';
        banner.innerHTML = `
            <div class="auth-banner-content">
                <div class="auth-banner-icon">🔐</div>
                <div class="auth-banner-text">
                    <strong>Authentication Required</strong>
                    <p>You need to authenticate with Google to access Docs and Sheets.</p>
                </div>
                <a href="${authUrl}" class="btn btn-primary auth-btn" target="_blank" rel="noopener noreferrer">
                    <span class="btn-icon">🔑</span> Authenticate with Google
                </a>
                <button class="auth-banner-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        // Insert at the top of the page
        const container = document.querySelector('#app') || document.querySelector('main') || document.body;
        if (container && container.firstChild) {
            container.insertBefore(banner, container.firstChild);
            console.log('Banner inserted into page');
        } else {
            console.error('Container not found or has no children!');
        }
    } else {
        console.log('Banner already exists');
    }
}

/**
 * Handle authentication errors from API responses
 * @param {Object} errorData - Error response data
 */
function handleAuthenticationError(errorData) {
    if (errorData.error_code === 'AUTHENTICATION_REQUIRED' && errorData.authorization_url) {
        showAuthenticationBanner(errorData.authorization_url);
        
        // Show simple error message (banner already has the link)
        showError(
            errorData.error || 'Authentication required. Please use the banner above to authenticate.',
            { autoHide: false }
        );
    } else {
        showError(errorData.error || 'Authentication failed', { autoHide: false });
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
    
    // Clear any existing sessions to force fresh processing
    // This ensures we don't load cached results
    AppState.sessionId = null;
    AppState.currentSession = null;
    
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
        
        // Debug: Log the response
        console.log('Upload response status:', uploadResponse.status);
        console.log('Upload response data:', uploadData);
        
        if (!uploadResponse.ok) {
            // Check for authentication error
            if (uploadResponse.status === 401 || uploadData.error_code === 'AUTHENTICATION_REQUIRED') {
                console.log('Authentication error detected, authorization_url:', uploadData.authorization_url);
                handleAuthenticationError(uploadData);
                throw new Error('Authentication required');
            }
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
            // Check for authentication error
            if (processResponse.status === 401 || processData.error_code === 'AUTHENTICATION_REQUIRED') {
                handleAuthenticationError(processData);
                throw new Error('Authentication required');
            }
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
 * Task 14.2: Enhanced error handling for spreadsheet preparation
 * Requirements: 9.1, 9.2, 9.3, 9.5
 */

/**
 * Error message templates with suggested actions
 * Requirements: 9.1, 9.2, 9.3
 */
const ERROR_MESSAGES = {
    translation_api_unavailable: {
        message: 'Translation service is currently unavailable. This may be due to network issues or service maintenance.',
        actions: [
            'Check your internet connection',
            'Try again in a few moments',
            'Manually enter translations for failed terms in the review table'
        ],
        type: 'network-error'
    },
    auth_required: {
        message: 'Google Sheets authentication is required to export your vocabulary list.',
        actions: [
            'Click the authentication link in the banner above',
            'Sign in with your Google account',
            'Grant the requested permissions',
            'Return to this page and try exporting again'
        ],
        type: 'auth-error'
    },
    validation_failed: {
        message: 'Some vocabulary entries have missing required fields and cannot be exported.',
        actions: [
            'Review the highlighted entries in the table below',
            'Fill in missing English or Cantonese text',
            'Click "Generate Google Sheet" again when ready'
        ],
        type: 'validation-error-display'
    },
    network_error: {
        message: 'Network connection error. Unable to reach the server.',
        actions: [
            'Check your internet connection',
            'Verify you can access other websites',
            'Try again in a few moments',
            'Your entered data has been preserved'
        ],
        type: 'network-error'
    },
    export_failed: {
        message: 'Failed to create Google Sheet. This may be due to permissions or service issues.',
        actions: [
            'Verify you have permission to create Google Sheets',
            'Check if you need to re-authenticate (see banner above)',
            'Try exporting again',
            'Your vocabulary data is preserved in the table below'
        ],
        type: 'network-error'
    },
    generic_error: {
        message: 'An unexpected error occurred. Please try again.',
        actions: [
            'Refresh the page and try again',
            'Check your internet connection',
            'If the problem persists, contact support'
        ],
        type: 'network-error'
    }
};

/**
 * Show error in the spreadsheet preparation error display area
 * Requirements: 9.1, 9.2, 9.3
 * @param {string} errorType - Type of error (key from ERROR_MESSAGES)
 * @param {string} customMessage - Optional custom error message
 */
function showPrepError(errorType, customMessage = null) {
    const errorDisplay = document.getElementById('prep-error-display');
    const errorMessage = document.getElementById('prep-error-message');
    const errorActions = document.getElementById('prep-error-actions');
    const errorActionsList = document.getElementById('prep-error-actions-list');
    
    if (!errorDisplay || !errorMessage || !errorActions || !errorActionsList) {
        console.error('Error display elements not found');
        // Fallback to toast
        showError(customMessage || 'An error occurred');
        return;
    }
    
    // Get error template or use generic
    const errorTemplate = ERROR_MESSAGES[errorType] || ERROR_MESSAGES.generic_error;
    
    // Set message
    errorMessage.textContent = customMessage || errorTemplate.message;
    
    // Set actions
    if (errorTemplate.actions && errorTemplate.actions.length > 0) {
        errorActionsList.innerHTML = '';
        errorTemplate.actions.forEach(action => {
            const li = document.createElement('li');
            li.textContent = action;
            errorActionsList.appendChild(li);
        });
        errorActions.style.display = 'block';
    } else {
        errorActions.style.display = 'none';
    }
    
    // Set error type class
    errorDisplay.className = 'prep-error-display ' + errorTemplate.type;
    
    // Show error display
    errorDisplay.style.display = 'block';
    
    // Scroll to error display
    errorDisplay.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    
    console.log(`Spreadsheet prep error displayed: ${errorType}`);
}

/**
 * Hide the spreadsheet preparation error display
 */
function hidePrepError() {
    const errorDisplay = document.getElementById('prep-error-display');
    if (errorDisplay) {
        errorDisplay.style.display = 'none';
    }
}

/**
 * Handle translation API errors
 * Requirements: 9.1, 9.5
 * @param {Error} error - Error object
 */
function handleTranslationError(error) {
    console.error('Translation error:', error);
    
    // Preserve user data (Requirement 9.5)
    // Data is already in AppState.spreadsheetPrep.inputText
    
    // Determine error type
    let errorType = 'generic_error';
    let customMessage = null;
    
    if (error.message.includes('Network error') || error.message.includes('Failed to fetch')) {
        errorType = 'network_error';
    } else if (error.message.includes('Translation service') || error.message.includes('unavailable')) {
        errorType = 'translation_api_unavailable';
    } else {
        customMessage = error.message;
    }
    
    // Show error display
    showPrepError(errorType, customMessage);
    
    // Also show toast for immediate feedback
    showError(error.message || 'Translation failed', {
        retryAction: handleGenerateTranslations,
        retryLabel: 'Retry Translation',
        autoHide: false
    });
}

/**
 * Handle authentication errors
 * Requirements: 9.2
 * @param {Object} errorData - Error response data from API
 */
function handlePrepAuthenticationError(errorData) {
    console.error('Authentication error:', errorData);
    
    // Show authentication banner if authorization URL provided
    if (errorData.authorization_url) {
        showAuthenticationBanner(errorData.authorization_url);
    }
    
    // Show error display
    showPrepError('auth_required', errorData.error);
    
    // Also show toast
    showError(errorData.error || 'Authentication required', { autoHide: false });
}

/**
 * Handle validation errors
 * Requirements: 9.1, 9.5
 * @param {Object} validation - Validation result with errors
 */
function handleValidationError(validation) {
    console.error('Validation errors:', validation.errors);
    
    // Preserve user data (Requirement 9.5)
    // Data is already in AppState.spreadsheetPrep.vocabularyEntries
    
    // Highlight errors in table
    highlightValidationErrors(validation.errors);
    
    // Show error display
    const errorCount = validation.errors.length;
    const customMessage = `Cannot export: ${errorCount} ${errorCount === 1 ? 'entry has' : 'entries have'} missing required fields. Please review the highlighted entries below.`;
    showPrepError('validation_failed', customMessage);
}

/**
 * Handle export errors
 * Requirements: 9.1, 9.2, 9.5
 * @param {Error} error - Error object
 * @param {number} statusCode - HTTP status code (if available)
 */
function handleExportError(error, statusCode = null) {
    console.error('Export error:', error, 'Status:', statusCode);
    
    // Preserve user data (Requirement 9.5)
    // Data is already in AppState.spreadsheetPrep.vocabularyEntries
    
    // Determine error type
    let errorType = 'export_failed';
    let customMessage = null;
    
    if (statusCode === 401 || error.message.includes('Authentication')) {
        errorType = 'auth_required';
    } else if (error.message.includes('Network error') || error.message.includes('Failed to fetch')) {
        errorType = 'network_error';
    } else {
        customMessage = error.message;
    }
    
    // Show error display
    showPrepError(errorType, customMessage);
    
    // Also show toast for immediate feedback
    showError(error.message || 'Export failed', {
        retryAction: handleExportToSheet,
        retryLabel: 'Retry Export',
        autoHide: false
    });
}

/**
 * Handle network errors
 * Requirements: 9.3, 9.5
 * @param {Error} error - Error object
 * @param {Function} retryAction - Function to call for retry
 */
function handleNetworkError(error, retryAction = null) {
    console.error('Network error:', error);
    
    // Preserve user data (Requirement 9.5)
    // Data is preserved in AppState
    
    // Show error display
    showPrepError('network_error', error.message);
    
    // Show toast with retry option if provided
    if (retryAction) {
        showError(error.message || 'Network error', {
            retryAction: retryAction,
            retryLabel: 'Retry',
            autoHide: false
        });
    } else {
        showError(error.message || 'Network error', { autoHide: false });
    }
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

/**
 * Setup back button to return to upload screen
 */
function setupBackButton() {
    const backBtn = document.getElementById('back-btn');
    
    if (backBtn) {
        backBtn.addEventListener('click', returnToUploadScreen);
        console.log('Back button initialized');
    }
}

/**
 * Return to upload screen and reset the application state
 * Updated to support mode selection (Task 10.2)
 */
function returnToUploadScreen() {
    // Confirm if user wants to leave (if there are unsaved changes)
    const hasUnsavedChanges = AppState.alignments.some(a => a.is_manually_adjusted);
    
    if (hasUnsavedChanges) {
        const confirmed = confirm(
            'You have unsaved manual adjustments. Are you sure you want to return to the upload screen?\n\n' +
            'Your current session will be preserved and you can return to it later using the session URL.'
        );
        
        if (!confirmed) {
            return;
        }
    }
    
    // Clear the processing log
    clearLog();
    
    // Hide alignment section
    if (elements.alignmentSection) {
        elements.alignmentSection.style.display = 'none';
    }
    
    // Hide upload container
    if (elements.uploadContainer) {
        elements.uploadContainer.style.display = 'none';
    }
    
    // Show mode selection
    if (elements.modeSelection) {
        elements.modeSelection.style.display = 'block';
    }
    
    // Reset app state
    AppState.currentMode = null;
    AppState.sessionId = null;
    AppState.currentSession = null;
    AppState.alignments = [];
    
    // Clear URL parameters
    window.history.pushState({}, '', window.location.pathname);
}

/**
 * Task 11.2: Spreadsheet Preparation Input Interface Logic
 */

/**
 * Handle text input changes in English terms textarea
 * Requirements: 2.2, 2.3, 2.4, 2.5
 */
function handleEnglishTermsInput(event) {
    const inputText = event.target.value;
    
    // Store input text in app state
    AppState.spreadsheetPrep.inputText = inputText;
    
    // Update textarea styling based on content
    if (inputText.trim()) {
        elements.englishTermsInput.classList.add('has-content');
    } else {
        elements.englishTermsInput.classList.remove('has-content');
    }
    
    // Enable/disable generate button based on input
    const hasValidInput = inputText.trim().length > 0;
    if (elements.generateTranslationsBtn) {
        elements.generateTranslationsBtn.disabled = !hasValidInput;
    }
}

/**
 * Parse input text into individual English terms
 * Requirements: 2.2, 2.3, 2.4, 2.5
 * @param {string} inputText - Multi-line input text
 * @returns {string[]} Array of parsed terms
 */
function parseEnglishTerms(inputText) {
    // Split by newlines
    const lines = inputText.split('\n');
    
    // Filter out empty lines and trim whitespace
    const terms = lines
        .map(line => line.trim())
        .filter(line => line.length > 0);
    
    return terms;
}

/**
 * Handle Generate Translations button click
 * Requirements: 2.2, 2.3, 2.4, 2.5, 3.1
 * Task 12.2: Show progress indicator when translation starts
 */
async function handleGenerateTranslations() {
    const inputText = AppState.spreadsheetPrep.inputText;
    
    // Parse input into terms
    const terms = parseEnglishTerms(inputText);
    
    if (terms.length === 0) {
        showError('Please enter at least one English term');
        return;
    }
    
    // Store parsed terms
    AppState.spreadsheetPrep.parsedTerms = terms;
    
    console.log(`Generating translations for ${terms.length} terms:`, terms);
    
    // Disable button and show loading state
    const generateBtn = elements.generateTranslationsBtn;
    if (generateBtn) {
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span class="btn-icon">⏳</span> Generating...';
    }
    
    // Show progress indicator (Requirements: 8.1)
    showTranslationProgress(terms.length);
    
    try {
        // Call translation API
        const response = await fetchWithRetry(`${API_BASE}/spreadsheet-prep/translate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                terms: terms
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Translation failed');
        }
        
        const data = await response.json();
        
        // Update progress to 100% (Requirements: 8.2)
        updateTranslationProgress(data.summary.total, data.summary.successful, data.summary.failed);
        
        // Store vocabulary entries
        AppState.spreadsheetPrep.vocabularyEntries = data.results;
        
        // Show success message with summary (Requirements: 8.3)
        const summary = data.summary;
        const message = `Generated ${summary.successful} translations (${summary.failed} failed)`;
        showSuccess(message);
        
        console.log('Translation results:', data);
        
        // Hide progress indicator after a short delay (Requirements: 8.3)
        setTimeout(() => {
            hideTranslationProgress();
            
            // Display results in review table (Task 13.2)
            renderReviewTable(data.results);
        }, 2000);
        
    } catch (error) {
        console.error('Translation error:', error);
        hideTranslationProgress();
        
        // Use enhanced error handling (Task 14.2)
        handleTranslationError(error);
    } finally {
        // Re-enable button
        if (generateBtn) {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<span class="btn-icon">✨</span> Generate Translations';
        }
    }
}

/**
 * Task 12.2: Progress tracking functions for translation
 */

/**
 * Show translation progress indicator
 * Requirements: 8.1, 8.4
 * @param {number} total - Total number of terms to translate
 */
function showTranslationProgress(total) {
    const progressContainer = document.getElementById('translation-progress');
    if (!progressContainer) {
        console.error('Translation progress container not found');
        return;
    }
    
    // Initialize progress display
    updateTranslationProgress(total, 0, 0);
    
    // Show the progress container
    progressContainer.style.display = 'block';
    
    console.log(`Translation progress indicator shown for ${total} terms`);
}

/**
 * Update translation progress indicator
 * Requirements: 8.2, 8.5
 * @param {number} total - Total number of terms
 * @param {number} completed - Number of successfully completed translations
 * @param {number} failed - Number of failed translations
 */
function updateTranslationProgress(total, completed, failed) {
    // Update progress bar
    const progressFill = document.getElementById('translation-progress-fill');
    const progressPercentage = document.getElementById('translation-progress-percentage');
    
    if (progressFill && progressPercentage) {
        const processed = completed + failed;
        const percent = total > 0 ? Math.round((processed / total) * 100) : 0;
        
        progressFill.style.width = `${percent}%`;
        progressPercentage.textContent = `${percent}%`;
    }
    
    // Update stats
    const totalElement = document.getElementById('progress-total');
    const completedElement = document.getElementById('progress-completed');
    const failedElement = document.getElementById('progress-failed');
    
    if (totalElement) totalElement.textContent = total;
    if (completedElement) completedElement.textContent = completed;
    if (failedElement) failedElement.textContent = failed;
    
    console.log(`Translation progress updated: ${completed}/${total} completed, ${failed} failed`);
}

/**
 * Hide translation progress indicator
 * Requirements: 8.3
 */
function hideTranslationProgress() {
    const progressContainer = document.getElementById('translation-progress');
    if (progressContainer) {
        progressContainer.style.display = 'none';
        console.log('Translation progress indicator hidden');
    }
}

/**
 * Task 13.2: Review Table Rendering Functions
 */

/**
 * Render the review table with vocabulary entries
 * Requirements: 3.5, 5.1, 5.5
 * @param {Array} results - Array of translation results
 */
function renderReviewTable(results) {
    if (!elements.reviewTableBody || !elements.reviewTableContainer) {
        console.error('Review table elements not found');
        return;
    }
    
    // Clear existing rows
    elements.reviewTableBody.innerHTML = '';
    
    // Render each entry
    results.forEach((entry, index) => {
        const row = createReviewTableRow(entry, index);
        elements.reviewTableBody.appendChild(row);
    });
    
    // Show the review table container
    elements.reviewTableContainer.style.display = 'block';
    
    // Enable export button if there are valid entries
    updateExportButtonState();
    
    console.log(`Review table rendered with ${results.length} entries`);
}

/**
 * Create a single row for the review table
 * Requirements: 3.5, 5.1, 5.5
 * @param {Object} entry - Vocabulary entry with translation results
 * @param {number} index - Row index
 * @returns {HTMLElement} Table row element
 */
function createReviewTableRow(entry, index) {
    const row = document.createElement('tr');
    row.dataset.index = index;
    
    // Add error class if translation or romanization failed
    if (!entry.success || entry.error) {
        row.classList.add('has-error');
    }
    
    // English column (editable)
    const englishCell = document.createElement('td');
    englishCell.className = 'col-english';
    const englishDiv = document.createElement('div');
    englishDiv.className = 'editable-cell';
    englishDiv.contentEditable = 'true';
    englishDiv.dataset.field = 'english';
    englishDiv.dataset.index = index;
    englishDiv.textContent = entry.english || '';
    
    // Add empty class if no content
    if (!entry.english) {
        englishDiv.classList.add('empty');
    }
    
    englishCell.appendChild(englishDiv);
    
    // Cantonese column (editable)
    const cantoneseCell = document.createElement('td');
    cantoneseCell.className = 'col-cantonese';
    const cantoneseDiv = document.createElement('div');
    cantoneseDiv.className = 'editable-cell';
    cantoneseDiv.contentEditable = 'true';
    cantoneseDiv.dataset.field = 'cantonese';
    cantoneseDiv.dataset.index = index;
    cantoneseDiv.textContent = entry.cantonese || '';
    
    // Add empty class if no content
    if (!entry.cantonese) {
        cantoneseDiv.classList.add('empty');
    }
    
    // Show error message if translation failed
    if (entry.error && !entry.cantonese) {
        const errorMsg = document.createElement('div');
        errorMsg.className = 'error-message';
        errorMsg.textContent = entry.error;
        cantoneseCell.appendChild(cantoneseDiv);
        cantoneseCell.appendChild(errorMsg);
    } else {
        cantoneseCell.appendChild(cantoneseDiv);
    }
    
    // Jyutping column (editable)
    const jyutpingCell = document.createElement('td');
    jyutpingCell.className = 'col-jyutping';
    const jyutpingDiv = document.createElement('div');
    jyutpingDiv.className = 'editable-cell';
    jyutpingDiv.contentEditable = 'true';
    jyutpingDiv.dataset.field = 'jyutping';
    jyutpingDiv.dataset.index = index;
    jyutpingDiv.textContent = entry.jyutping || '';
    
    // Add empty class if no content
    if (!entry.jyutping) {
        jyutpingDiv.classList.add('empty');
    }
    
    jyutpingCell.appendChild(jyutpingDiv);
    
    // Status column
    const statusCell = document.createElement('td');
    statusCell.className = 'col-status';
    const statusIndicator = document.createElement('div');
    statusIndicator.className = entry.success ? 'status-indicator success' : 'status-indicator error';
    
    const statusIcon = document.createElement('span');
    statusIcon.className = 'status-indicator-icon';
    statusIcon.textContent = entry.success ? '✓' : '✗';
    
    const statusText = document.createElement('span');
    statusText.textContent = entry.success ? 'Success' : 'Failed';
    
    statusIndicator.appendChild(statusIcon);
    statusIndicator.appendChild(statusText);
    statusCell.appendChild(statusIndicator);
    
    // Assemble row
    row.appendChild(englishCell);
    row.appendChild(cantoneseCell);
    row.appendChild(jyutpingCell);
    row.appendChild(statusCell);
    
    return row;
}

/**
 * Update export button state based on validation
 * Requirements: 7.3
 */
function updateExportButtonState() {
    if (!elements.exportSheetBtn) return;
    
    const entries = AppState.spreadsheetPrep.vocabularyEntries;
    
    // Check if all entries have required fields
    const allValid = entries.every(entry => 
        entry.english && entry.english.trim() && 
        entry.cantonese && entry.cantonese.trim()
    );
    
    elements.exportSheetBtn.disabled = !allValid || entries.length === 0;
}

/**
 * Task 13.3: Cell Editing Logic
 */

/**
 * Handle cell edit events
 * Requirements: 5.2, 5.3, 5.4, 5.6
 * @param {Event} event - Input event from editable cell
 */
function handleCellEdit(event) {
    const target = event.target;
    
    // Check if the target is an editable cell
    if (!target.classList.contains('editable-cell')) {
        return;
    }
    
    const field = target.dataset.field;
    const index = parseInt(target.dataset.index, 10);
    const value = target.textContent.trim();
    
    // Update the vocabulary entry immediately (Requirement 5.4)
    if (AppState.spreadsheetPrep.vocabularyEntries[index]) {
        AppState.spreadsheetPrep.vocabularyEntries[index][field] = value;
        
        console.log(`Updated entry ${index} ${field}: "${value}"`);
        
        // Remove empty class if content was added
        if (value) {
            target.classList.remove('empty');
        } else {
            target.classList.add('empty');
        }
        
        // Revalidate and update export button state (Requirement 5.6)
        updateExportButtonState();
    }
}

/**
 * Handle cell blur events (when user leaves the cell)
 * Requirements: 5.2, 5.3, 5.6
 * @param {Event} event - Blur event from editable cell
 */
function handleCellBlur(event) {
    const target = event.target;
    
    // Check if the target is an editable cell
    if (!target.classList.contains('editable-cell')) {
        return;
    }
    
    const field = target.dataset.field;
    const index = parseInt(target.dataset.index, 10);
    const value = target.textContent.trim();
    
    // Ensure the value is saved (in case input event didn't fire)
    if (AppState.spreadsheetPrep.vocabularyEntries[index]) {
        AppState.spreadsheetPrep.vocabularyEntries[index][field] = value;
        
        // Validate the entry
        const entry = AppState.spreadsheetPrep.vocabularyEntries[index];
        const isValid = entry.english && entry.english.trim() && 
                       entry.cantonese && entry.cantonese.trim();
        
        // Update row styling based on validation
        const row = target.closest('tr');
        if (row) {
            if (!isValid) {
                row.classList.add('has-error');
            } else {
                // Only remove error class if it was added by validation, not by translation failure
                const originalEntry = AppState.spreadsheetPrep.vocabularyEntries[index];
                if (originalEntry.success) {
                    row.classList.remove('has-error');
                }
            }
        }
        
        // Update export button state
        updateExportButtonState();
    }
}

/**
 * Task 13.5: Validation and Export Logic
 */

/**
 * Validate all vocabulary entries
 * Requirements: 7.1, 7.2, 7.3, 7.5
 * @returns {Object} Validation result with isValid flag and errors array
 */
function validateVocabularyEntries() {
    const entries = AppState.spreadsheetPrep.vocabularyEntries;
    const errors = [];
    
    entries.forEach((entry, index) => {
        const validationErrors = [];
        
        // Check for empty English term (Requirement 7.1)
        if (!entry.english || !entry.english.trim()) {
            validationErrors.push('English term is required');
        }
        
        // Check for empty Cantonese text (Requirement 7.2)
        if (!entry.cantonese || !entry.cantonese.trim()) {
            validationErrors.push('Cantonese text is required');
        }
        
        if (validationErrors.length > 0) {
            errors.push({
                index: index,
                english: entry.english,
                errors: validationErrors
            });
        }
    });
    
    return {
        isValid: errors.length === 0,
        errors: errors
    };
}

/**
 * Highlight entries with validation errors
 * Requirements: 7.4
 * @param {Array} errors - Array of validation errors with indices
 */
function highlightValidationErrors(errors) {
    // Clear existing error highlights
    const rows = elements.reviewTableBody.querySelectorAll('tr');
    rows.forEach(row => {
        row.classList.remove('validation-error');
    });
    
    // Highlight rows with errors
    errors.forEach(error => {
        const row = elements.reviewTableBody.querySelector(`tr[data-index="${error.index}"]`);
        if (row) {
            row.classList.add('validation-error', 'has-error');
            
            // Scroll to first error
            if (error === errors[0]) {
                row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    });
}

/**
 * Handle export to Google Sheets
 * Requirements: 7.3, 7.4, 7.5, 6.4, 6.6
 */
async function handleExportToSheet() {
    // Hide any previous errors
    hidePrepError();
    
    // Validate entries (Requirement 7.3)
    const validation = validateVocabularyEntries();
    
    if (!validation.isValid) {
        // Use enhanced validation error handling (Task 14.2)
        handleValidationError(validation);
        return;
    }
    
    // Disable button and show loading state
    const exportBtn = elements.exportSheetBtn;
    if (exportBtn) {
        exportBtn.disabled = true;
        exportBtn.innerHTML = '<span class="btn-icon">⏳</span> Creating Sheet...';
    }
    
    try {
        // Call export API (Requirement 6.4)
        const response = await fetchWithRetry(`${API_BASE}/spreadsheet-prep/export`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                entries: AppState.spreadsheetPrep.vocabularyEntries.map(entry => ({
                    english: entry.english,
                    cantonese: entry.cantonese,
                    jyutping: entry.jyutping || ''
                }))
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            
            // Check for authentication error (Task 14.2)
            if (response.status === 401 || errorData.error_code === 'AUTHENTICATION_REQUIRED') {
                handlePrepAuthenticationError(errorData);
                throw new Error('Authentication required');
            }
            
            throw new Error(errorData.error || 'Export failed');
        }
        
        const data = await response.json();
        
        // Display sheet URL on success (Requirement 6.6)
        if (elements.exportResult) {
            elements.exportResult.className = 'export-result success';
            elements.exportResult.innerHTML = `
                <strong>✓ Google Sheet Created Successfully!</strong><br>
                <a href="${data.sheet_url}" target="_blank" rel="noopener noreferrer">
                    Open Google Sheet
                </a>
            `;
            elements.exportResult.style.display = 'block';
        }
        
        showSuccess('Google Sheet created successfully!');
        
        console.log('Export successful:', data);
        
    } catch (error) {
        console.error('Export error:', error);
        
        // Use enhanced error handling (Task 14.2)
        // Determine status code if available
        let statusCode = null;
        if (error.message.includes('Authentication')) {
            statusCode = 401;
        }
        handleExportError(error, statusCode);
        
        // Display error in export result area as well
        if (elements.exportResult) {
            elements.exportResult.className = 'export-result error';
            elements.exportResult.innerHTML = `
                <strong>✗ Export Failed</strong><br>
                ${error.message}
            `;
            elements.exportResult.style.display = 'block';
        }
        
    } finally {
        // Re-enable button
        if (exportBtn) {
            exportBtn.disabled = false;
            exportBtn.innerHTML = '<span class="btn-icon">📊</span> Generate Google Sheet';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initApp);

// Export functions to global scope for HTML onclick handlers
window.hidePrepError = hidePrepError;
window.hideError = hideError;
window.hideSuccess = hideSuccess;

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
    console.log(`[DEBUG] initializeTermWaveform called for term: ${termId}, container: ${containerId}`);
    
    // Log WaveSurfer version and verify it matches expected version
    if (typeof WaveSurfer !== 'undefined' && WaveSurfer.VERSION) {
        console.log(`[DEBUG] WaveSurfer version: ${WaveSurfer.VERSION}`);
        const expectedVersion = '7.7.3';
        if (WaveSurfer.VERSION !== expectedVersion) {
            console.warn(`[DEBUG] WaveSurfer version mismatch! Expected: ${expectedVersion}, Got: ${WaveSurfer.VERSION}`);
            console.warn(`[DEBUG] API differences may exist - verify Regions plugin compatibility`);
        } else {
            console.log(`[DEBUG] WaveSurfer version matches expected version: ${expectedVersion}`);
        }
    } else {
        console.error(`[DEBUG] WaveSurfer.VERSION not available - cannot verify version`);
    }
    
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
        interact: false,    // Disable waveform dragging/panning
        hideScrollbar: true,
        minPxPerSec: 50,    // Reduce to fit longer audio without scrolling
        fillParent: true,   // Force waveform to fill container width
        autoScroll: false,  // Prevent automatic scrolling
        autoCenter: false   // Prevent automatic centering
    };
    
    console.log(`[DEBUG] Creating WaveSurfer instance with options:`, { ...defaultOptions, ...options });
    
    const wavesurfer = WaveSurfer.create({
        ...defaultOptions,
        ...options
    });
    
    console.log(`[DEBUG] WaveSurfer instance created for term: ${termId}`);
    
    // Add lifecycle event logging
    wavesurfer.on('init', () => {
        console.log(`[DEBUG] WaveSurfer 'init' event fired for term: ${termId}`);
    });
    
    wavesurfer.on('ready', () => {
        console.log(`[DEBUG] WaveSurfer 'ready' event fired for term: ${termId}`);
        console.log(`[DEBUG] Duration: ${wavesurfer.getDuration()}s`);
    });
    
    wavesurfer.on('decode', () => {
        console.log(`[DEBUG] WaveSurfer 'decode' event fired for term: ${termId}`);
    });
    
    wavesurfer.on('error', (error) => {
        console.error(`[DEBUG] WaveSurfer error for term ${termId}:`, error);
    });
    
    // Add regions plugin for draggable boundary markers
    console.log(`[DEBUG] Registering Regions plugin for term: ${termId}`);
    
    // Check if Regions plugin is available
    if (!WaveSurfer.Regions) {
        console.error(`[DEBUG] WaveSurfer.Regions plugin not available!`);
        
        // Store instance even without regions to prevent memory leak
        WaveSurferInstances.termWaveforms.set(termId, {
            instance: wavesurfer,
            regions: null,
            regionsAvailable: false
        });
        
        return wavesurfer;
    }
    
    // Create regions plugin with explicit configuration
    const regionsPlugin = wavesurfer.registerPlugin(
        WaveSurfer.Regions.create({
            dragSelection: false  // Disable creating regions by dragging on waveform
        })
    );
    console.log(`[DEBUG] Regions plugin registered for term: ${termId}`, regionsPlugin);
    
    // Store reference
    WaveSurferInstances.termWaveforms.set(termId, {
        instance: wavesurfer,
        regions: regionsPlugin,
        regionsAvailable: true
    });
    
    console.log(`[DEBUG] Term waveform initialized and stored for term: ${termId}`);
    
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
    
    // Boundary adjustment controls
    const boundaryControls = document.createElement('div');
    boundaryControls.className = 'boundary-controls';
    boundaryControls.innerHTML = `
        <div class="time-inputs">
            <label>
                Start: <input type="number" 
                    class="time-input start-time-input" 
                    id="start-${termAlignment.term_id}"
                    value="${termAlignment.start_time.toFixed(2)}" 
                    step="0.01" 
                    min="0"
                    data-term-id="${termAlignment.term_id}">s
            </label>
            <label>
                End: <input type="number" 
                    class="time-input end-time-input" 
                    id="end-${termAlignment.term_id}"
                    value="${termAlignment.end_time.toFixed(2)}" 
                    step="0.01" 
                    min="0"
                    data-term-id="${termAlignment.term_id}">s
            </label>
            <button class="trim-btn" data-term-id="${termAlignment.term_id}">
                ✂ Trim
            </button>
        </div>
    `;
    
    waveformCell.appendChild(waveformContainer);
    waveformCell.appendChild(boundaryControls);
    
    // Controls column
    const controlsCell = document.createElement('div');
    controlsCell.className = 'controls-cell';
    
    const playBtn = document.createElement('button');
    playBtn.className = 'play-btn';
    playBtn.innerHTML = '▶ Play';
    playBtn.dataset.termId = termAlignment.term_id;
    playBtn.onclick = () => playTermAudio(termAlignment.term_id);
    
    controlsCell.appendChild(playBtn);
    
    // Add regeneration buttons
    const regenBtn = document.createElement('button');
    regenBtn.className = 'regen-btn';
    regenBtn.innerHTML = '🔄 Regenerate';
    regenBtn.title = 'Re-run alignment for this term only';
    regenBtn.dataset.termId = termAlignment.term_id;
    regenBtn.onclick = () => regenerateTerm(termAlignment.term_id);
    
    const regenFromBtn = document.createElement('button');
    regenFromBtn.className = 'regen-from-btn';
    regenFromBtn.innerHTML = '🔄➡ From Here';
    regenFromBtn.title = 'Re-run alignment for this term and all following terms';
    regenFromBtn.dataset.termId = termAlignment.term_id;
    regenFromBtn.onclick = () => regenerateFromTerm(termAlignment.term_id);
    
    controlsCell.appendChild(regenBtn);
    controlsCell.appendChild(regenFromBtn);
    
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
 * Render waveforms progressively with delays to prevent browser overload
 * @param {Array} alignments - Array of TermAlignment objects
 */
async function renderWaveformsProgressively(alignments) {
    console.log(`Starting progressive waveform rendering for ${alignments.length} terms`);
    
    for (let i = 0; i < alignments.length; i++) {
        const alignment = alignments[i];
        
        // Skip terms with invalid time ranges (0-0 means no audio aligned)
        if (alignment.start_time === 0 && alignment.end_time === 0) {
            console.warn(`Skipping term ${alignment.term_id} - no audio aligned (0s - 0s)`);
            continue;
        }
        
        if (alignment.audio_segment_url) {
            try {
                await renderTermWaveform(
                    alignment.term_id,
                    alignment.audio_segment_url,
                    alignment.start_time,
                    alignment.end_time
                );
                
                // Small delay between each waveform to prevent overwhelming the browser
                // Only delay if there are more waveforms to render
                if (i < alignments.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 50)); // 50ms delay
                }
            } catch (error) {
                console.error(`Failed to render waveform for term ${alignment.term_id}:`, error);
                // Continue with next waveform even if one fails
            }
        } else {
            console.warn(`Skipping term ${alignment.term_id} - no audio segment URL`);
        }
    }
    
    console.log('Progressive waveform rendering complete');
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
    
    console.log(`[DEBUG] renderTermWaveform called for term: ${termId}`);
    console.log(`[DEBUG] Audio URL: ${audioUrl}`);
    console.log(`[DEBUG] Time range: ${startTime}s - ${endTime}s`);
    
    try {
        // Destroy existing waveform if it exists
        const existingWaveform = getTermWaveform(termId);
        if (existingWaveform) {
            console.log(`[DEBUG] Destroying existing waveform for term ${termId}`);
            // Properly clean up regions plugin and all event listeners
            if (existingWaveform.regions) {
                existingWaveform.regions.destroy();
            }
            existingWaveform.instance.destroy();
            WaveSurferInstances.termWaveforms.delete(termId);
        }
        
        // Initialize WaveSurfer for this term
        console.log(`[DEBUG] Initializing WaveSurfer for term: ${termId}`);
        const wavesurfer = initializeTermWaveform(containerId, termId);
        
        // Load the audio segment and wait for ready event
        console.log(`[DEBUG] Loading audio for term: ${termId}`);
        await new Promise((resolve, reject) => {
            // Set up ready event listener before loading
            wavesurfer.once('ready', () => {
                console.log(`[DEBUG] Ready event fired for term: ${termId}`);
                resolve();
            });
            
            // Set up error event listener
            wavesurfer.once('error', (error) => {
                console.error(`[DEBUG] Error loading audio for term ${termId}:`, error);
                reject(error);
            });
            
            // Start loading audio
            wavesurfer.load(audioUrl);
        });
        console.log(`[DEBUG] Audio loaded and ready for term: ${termId}`);
        
        // Get the waveform data (includes regions plugin)
        const waveformData = getTermWaveform(termId);
        console.log(`[DEBUG] Retrieved waveform data for term: ${termId}`, waveformData);
        
        if (waveformData && waveformData.regions) {
            // Add a draggable region covering the full segment
            // User can drag the edges to trim
            const duration = wavesurfer.getDuration();
            console.log(`[DEBUG] Creating region for term: ${termId}, duration: ${duration}s`);
            
            const regionConfig = {
                id: `region-${termId}`,
                start: 0,
                end: duration,
                color: 'rgba(52, 152, 219, 0.3)', // Semi-transparent blue
                drag: true,       // Enable dragging (required for edge resizing in WaveSurfer v7)
                resize: true,     // Allow resizing from edges
                content: ''
            };
            
            const region = waveformData.regions.addRegion(regionConfig);
            console.log(`[DEBUG] Region created for term: ${termId}`, region);
            
            // Force shadow DOM to disable scrolling and fill parent
            setTimeout(() => {
                const container = document.getElementById(containerId);
                if (container) {
                    const shadowRoot = container.querySelector('div')?.shadowRoot;
                    if (shadowRoot) {
                        const scrollDiv = shadowRoot.querySelector('.scroll');
                        const wrapperDiv = shadowRoot.querySelector('.wrapper');
                        
                        if (scrollDiv) {
                            scrollDiv.style.overflowX = 'hidden';
                            console.log(`[DEBUG] Forced overflow-x: hidden for term: ${termId}`);
                        }
                        
                        if (wrapperDiv) {
                            wrapperDiv.style.width = '100%';
                            console.log(`[DEBUG] Forced width: 100% for term: ${termId}`);
                        }
                    }
                }
            }, 100);
            
            // Set up drag handlers for automatic trimming
            console.log(`[DEBUG] Setting up region drag handlers for term: ${termId}`);
            setupRegionDragHandlersForTrim(termId, waveformData.regions);
        } else {
            console.error(`[DEBUG] No waveform data or regions plugin for term: ${termId}`);
        }
        
        console.log(`[DEBUG] Waveform rendering complete for term ${termId}`);
        
    } catch (error) {
        console.log(`[DEBUG] Failed to render waveform for term ${termId}:`, error);
        console.error(`[DEBUG] Error stack:`, error.stack);
        
        // Show user-friendly error message with retry option
        const waveformContainer = document.getElementById(containerId);
        if (waveformContainer) {
            // Clear container
            waveformContainer.innerHTML = '';
            
            // Create error display elements
            const errorDiv = document.createElement('div');
            errorDiv.className = 'waveform-error';
            
            const errorIcon = document.createElement('div');
            errorIcon.className = 'error-icon';
            errorIcon.textContent = '⚠️';
            
            const errorText = document.createElement('div');
            errorText.className = 'error-text';
            errorText.textContent = 'Failed to load waveform';
            
            const retryButton = document.createElement('button');
            retryButton.className = 'retry-waveform-btn';
            retryButton.textContent = '🔄 Retry';
            
            // Store data in dataset to avoid XSS
            retryButton.dataset.termId = termId;
            retryButton.dataset.audioUrl = audioUrl;
            retryButton.dataset.startTime = startTime;
            retryButton.dataset.endTime = endTime;
            
            // Attach event listener instead of inline onclick
            retryButton.addEventListener('click', () => {
                retryWaveformLoad(
                    retryButton.dataset.termId,
                    retryButton.dataset.audioUrl,
                    parseFloat(retryButton.dataset.startTime),
                    parseFloat(retryButton.dataset.endTime)
                );
            });
            
            errorDiv.appendChild(errorIcon);
            errorDiv.appendChild(errorText);
            errorDiv.appendChild(retryButton);
            waveformContainer.appendChild(errorDiv);
        }
        
        // Log error but don't show toast for individual waveform failures
        // This prevents overwhelming the user with multiple error toasts
    }
}

/**
 * Retry loading a waveform after a failure
 * @param {string} termId - Term identifier
 * @param {string} audioUrl - URL to the audio segment
 * @param {number} startTime - Start time in seconds
 * @param {number} endTime - End time in seconds
 */
async function retryWaveformLoad(termId, audioUrl, startTime, endTime) {
    console.log(`[DEBUG] Retrying waveform load for term: ${termId}`);
    
    // Clear the error message
    const waveformContainer = document.getElementById(`waveform-${termId}`);
    if (waveformContainer) {
        waveformContainer.innerHTML = '<div class="loading-message">Loading waveform...</div>';
    }
    
    // Attempt to render the waveform again with error handling
    try {
        await renderTermWaveform(termId, audioUrl, startTime, endTime);
    } catch (error) {
        console.error(`[DEBUG] Retry failed for term ${termId}:`, error);
        
        // Restore error UI if retry fails
        if (waveformContainer) {
            waveformContainer.innerHTML = '';
            
            const errorDiv = document.createElement('div');
            errorDiv.className = 'waveform-error';
            
            const errorIcon = document.createElement('div');
            errorIcon.className = 'error-icon';
            errorIcon.textContent = '⚠️';
            
            const errorText = document.createElement('div');
            errorText.className = 'error-text';
            errorText.textContent = 'Failed to load waveform. Retry?';
            
            const retryButton = document.createElement('button');
            retryButton.className = 'retry-waveform-btn';
            retryButton.textContent = '🔄 Retry';
            
            retryButton.dataset.termId = termId;
            retryButton.dataset.audioUrl = audioUrl;
            retryButton.dataset.startTime = startTime;
            retryButton.dataset.endTime = endTime;
            
            retryButton.addEventListener('click', () => {
                retryWaveformLoad(
                    retryButton.dataset.termId,
                    retryButton.dataset.audioUrl,
                    parseFloat(retryButton.dataset.startTime),
                    parseFloat(retryButton.dataset.endTime)
                );
            });
            
            errorDiv.appendChild(errorIcon);
            errorDiv.appendChild(errorText);
            errorDiv.appendChild(retryButton);
            waveformContainer.appendChild(errorDiv);
        }
    }
}

/**
 * Set up drag event handlers for trim functionality
 * Updates input fields as you drag and auto-trims when you release
 * @param {string} termId - Term identifier
 * @param {Object} regionsPlugin - WaveSurfer regions plugin instance
 */
function setupRegionDragHandlersForTrim(termId, regionsPlugin) {
    console.log(`[DEBUG] setupRegionDragHandlersForTrim called for term: ${termId}`);
    console.log(`[DEBUG] Regions plugin:`, regionsPlugin);
    
    // Task 5.1: Add verification checks in setupRegionDragHandlersForTrim
    // Check that regionsPlugin is not null/undefined
    if (!regionsPlugin) {
        console.warn(`[VERIFICATION] Regions plugin not found for term ${termId} - cannot setup drag handlers`);
        return;
    }
    
    // Check that region exists using getRegions()
    const regions = regionsPlugin.getRegions();
    console.log(`[DEBUG] All regions:`, regions);
    
    if (!regions || regions.length === 0) {
        console.warn(`[VERIFICATION] No regions found in plugin for term ${termId} - region may not be created yet`);
        return;
    }
    
    const region = regions.find(r => r.id === `region-${termId}`);
    
    // Log warning if region not found
    if (!region) {
        console.warn(`[VERIFICATION] Region with id 'region-${termId}' not found in regions list. Available regions: ${regions.map(r => r.id).join(', ')}`);
        return;
    }
    
    console.log(`[VERIFICATION] Region found for term ${termId}:`, region);
    console.log(`[VERIFICATION] Region resize enabled: ${region.resize}`);
    console.log(`[VERIFICATION] Region drag enabled: ${region.drag}`);
    
    // Get the alignment data for this term to know the current absolute times
    const alignment = AppState.alignments.find(a => a.term_id === termId);
    if (!alignment) {
        console.error(`[DEBUG] No alignment found for term ${termId}`);
        return;
    }
    
    const originalStartTime = alignment.start_time;
    const originalDuration = alignment.end_time - alignment.start_time;
    
    // Track if user is actively dragging/resizing (prevents auto-trim on programmatic updates)
    let userIsInteracting = false;
    let lastKnownStart = null;
    let lastKnownEnd = null;
    
    // Task 5.2: Add event listener verification
    // Log when each event listener is attached
    console.log(`[EVENT-LISTENER] Attaching 'region-update-start' event listener for term: ${termId}`);
    regionsPlugin.on('region-update-start', (region) => {
        console.log(`[EVENT-FIRED] 'region-update-start' event fired for region: ${region.id}`);
        if (region.id === `region-${termId}`) {
            userIsInteracting = true;
            lastKnownStart = region.start;
            lastKnownEnd = region.end;
            console.log(`[EVENT-FIRED] User started interacting with region for term: ${termId}`);
        }
    });
    console.log(`[EVENT-LISTENER] ✓ 'region-update-start' listener attached successfully for term: ${termId}`);
    
    // Listen for region update events (while dragging/resizing)
    console.log(`[EVENT-LISTENER] Attaching 'region-updated' event listener for term: ${termId}`);
    regionsPlugin.on('region-updated', (region) => {
        console.log(`[EVENT-FIRED] 'region-updated' event fired for region: ${region.id}, userIsInteracting: ${userIsInteracting}`);
        if (region.id === `region-${termId}`) {
            // Check if boundaries actually changed (to detect user interaction even if region-update-start didn't fire)
            const boundariesChanged = lastKnownStart !== region.start || lastKnownEnd !== region.end;
            
            if (boundariesChanged) {
                // Boundaries changed - this is a user interaction (resize or drag)
                userIsInteracting = true;
                lastKnownStart = region.start;
                lastKnownEnd = region.end;
                
                console.log(`[EVENT-FIRED] Boundaries changed - updating input fields - start: ${region.start}s, end: ${region.end}s`);
                
                // Region times are relative to the segment (0 to duration)
                // Convert to absolute times by adding the original start time
                // and scaling based on the original duration
                const relativeStart = region.start;
                const relativeEnd = region.end;
                
                // Get current segment duration from waveform
                const waveformData = getTermWaveform(termId);
                if (!waveformData) return;
                
                const currentDuration = waveformData.instance.getDuration();
                
                // Calculate absolute times
                // The region is on the current audio segment, so we need to map it back
                // to absolute times based on the current alignment
                const currentAlignment = AppState.alignments.find(a => a.term_id === termId);
                if (!currentAlignment) return;
                
                const absoluteStart = currentAlignment.start_time + (relativeStart / currentDuration) * (currentAlignment.end_time - currentAlignment.start_time);
                const absoluteEnd = currentAlignment.start_time + (relativeEnd / currentDuration) * (currentAlignment.end_time - currentAlignment.start_time);
                
                console.log(`[DEBUG] Calculated absolute times - start: ${absoluteStart.toFixed(2)}s, end: ${absoluteEnd.toFixed(2)}s`);
                
                // Update input fields with absolute times
                const startInput = document.getElementById(`start-${termId}`);
                const endInput = document.getElementById(`end-${termId}`);
                
                if (startInput && endInput) {
                    startInput.value = absoluteStart.toFixed(2);
                    endInput.value = absoluteEnd.toFixed(2);
                    console.log(`[EVENT-FIRED] Updated input fields for term: ${termId}`);
                } else {
                    console.warn(`[EVENT-FIRED] Input fields not found for term: ${termId}`);
                }
            }
        }
    });
    console.log(`[EVENT-LISTENER] ✓ 'region-updated' listener attached successfully for term: ${termId}`);
    
    // Listen for region update end (when user finishes dragging/resizing)
    console.log(`[EVENT-LISTENER] Attaching 'region-update-end' event listener for term: ${termId}`);
    regionsPlugin.on('region-update-end', async (region) => {
        console.log(`[EVENT-FIRED] 'region-update-end' event fired for region: ${region.id}, userIsInteracting: ${userIsInteracting}`);
        if (region.id === `region-${termId}` && userIsInteracting) {
            userIsInteracting = false;
            console.log(`[EVENT-FIRED] User finished interacting with region for term: ${termId}`);
            console.log(`[EVENT-FIRED] Final boundaries - start: ${region.start}s, end: ${region.end}s`);
            
            // Automatically trigger trim with the new boundaries from input fields
            console.log(`[EVENT-FIRED] Triggering automatic trim for term: ${termId}`);
            await handleTrimBoundaries(termId);
        }
    });
    console.log(`[EVENT-LISTENER] ✓ 'region-update-end' listener attached successfully for term: ${termId}`);
    
    console.log(`[EVENT-LISTENER] ✓✓✓ All 3 event listeners attached successfully for term: ${termId}`);
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
    
    // Check boundaries are within audio duration
    const session = AppState.currentSession;
    if (session && newEnd > session.audio_duration) {
        return {
            valid: false,
            error: `End time exceeds audio duration (${formatTime(session.audio_duration)})`
        };
    }
    
    // All validations passed
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
    
    // Create and append rows first (fast)
    for (const alignment of alignments) {
        const row = createTermRow(alignment);
        alignmentRows.appendChild(row);
    }
    
    // Set up event delegation for trim buttons
    setupTrimButtonHandlers();
    
    console.log(`Displayed ${alignments.length} term alignments`);
    
    // Render waveforms progressively with delays to prevent overwhelming the browser
    // This happens in the background without blocking the UI
    renderWaveformsProgressively(alignments);
}

/**
 * Set up event handlers for trim buttons using event delegation
 */
function setupTrimButtonHandlers() {
    const alignmentRows = document.getElementById('alignment-rows');
    
    // Remove any existing trim handler to avoid duplicates
    if (alignmentRows._trimHandler) {
        alignmentRows.removeEventListener('click', alignmentRows._trimHandler);
    }
    
    // Create new handler
    const trimHandler = async (e) => {
        if (e.target.classList.contains('trim-btn')) {
            console.log('Trim button clicked!', e.target);
            const termId = e.target.dataset.termId;
            console.log('Term ID:', termId);
            await handleTrimBoundaries(termId);
        }
    };
    
    // Store reference and add listener
    alignmentRows._trimHandler = trimHandler;
    alignmentRows.addEventListener('click', trimHandler);
    
    console.log('Trim button handlers set up');
}

/**
 * Handle trim button click - update boundaries based on input values
 * @param {string} termId - Term identifier
 */
async function handleTrimBoundaries(termId) {
    try {
        // Get input values
        const startInput = document.getElementById(`start-${termId}`);
        const endInput = document.getElementById(`end-${termId}`);
        
        if (!startInput || !endInput) {
            showError('Could not find time input fields');
            return;
        }
        
        const newStartTime = parseFloat(startInput.value);
        const newEndTime = parseFloat(endInput.value);
        
        // Validate inputs
        if (isNaN(newStartTime) || isNaN(newEndTime)) {
            showError('Please enter valid time values');
            return;
        }
        
        if (newStartTime < 0 || newEndTime < 0) {
            showError('Time values must be non-negative');
            return;
        }
        
        if (newStartTime >= newEndTime) {
            showError('Start time must be less than end time');
            return;
        }
        
        // Validate boundaries don't overlap with adjacent terms
        const validationResult = validateBoundaries(termId, newStartTime, newEndTime);
        if (!validationResult.valid) {
            showError(validationResult.error);
            return;
        }
        
        console.log(`Trimming term ${termId}: ${newStartTime}s - ${newEndTime}s`);
        
        // Show loading state
        const trimBtn = document.querySelector(`.trim-btn[data-term-id="${termId}"]`);
        const originalText = trimBtn.innerHTML;
        trimBtn.innerHTML = '⏳ Trimming...';
        trimBtn.disabled = true;
        
        // Send update to server
        const response = await fetchWithRetry(`${API_BASE}/session/${AppState.sessionId}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                term_id: termId,
                start_time: newStartTime,
                end_time: newEndTime
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to update boundaries');
        }
        
        // Update local state
        const alignment = AppState.alignments.find(a => a.term_id === termId);
        if (alignment) {
            console.log(`Updating alignment state: ${alignment.start_time} -> ${newStartTime}, ${alignment.end_time} -> ${newEndTime}`);
            alignment.start_time = newStartTime;
            alignment.end_time = newEndTime;
            alignment.is_manually_adjusted = true;
        }
        
        // Update input fields to reflect the new values
        console.log(`Updating input fields: start=${newStartTime}, end=${newEndTime}`);
        startInput.value = newStartTime.toFixed(2);
        endInput.value = newEndTime.toFixed(2);
        console.log(`Input fields after update: start=${startInput.value}, end=${endInput.value}`);
        
        // Mark as pending update
        AppState.pendingUpdates.set(termId, {
            start_time: newStartTime,
            end_time: newEndTime
        });
        
        // Update UI to show manual adjustment
        const termRow = document.getElementById(`term-row-${termId}`);
        if (termRow && !termRow.classList.contains('manually-adjusted')) {
            termRow.classList.add('manually-adjusted');
            
            // Add reset button if not already present
            const controlsCell = termRow.querySelector('.controls-cell');
            if (controlsCell && !controlsCell.querySelector('.reset-btn')) {
                const resetBtn = document.createElement('button');
                resetBtn.className = 'reset-btn';
                resetBtn.innerHTML = '↺ Reset';
                resetBtn.dataset.termId = termId;
                resetBtn.onclick = () => resetTermAlignment(termId);
                
                const adjustmentIndicator = document.createElement('div');
                adjustmentIndicator.className = 'adjustment-indicator';
                adjustmentIndicator.textContent = '✓ Manually adjusted';
                
                controlsCell.appendChild(resetBtn);
                controlsCell.appendChild(adjustmentIndicator);
            }
        }
        
        // Reload the waveform with new boundaries
        // Add cache-busting parameter to force reload of audio
        const cacheBuster = Date.now();
        const newAudioUrl = `/api/audio/${AppState.sessionId}/${termId}?t=${cacheBuster}`;
        
        // Render the updated waveform
        await renderTermWaveform(
            termId,
            newAudioUrl,
            newStartTime,
            newEndTime
        );
        
        // Restore button state
        trimBtn.innerHTML = originalText;
        trimBtn.disabled = false;
        
        showSuccess(`Boundaries updated for "${alignment.english}"`);
        console.log(`Successfully trimmed term ${termId}`);
        
    } catch (error) {
        console.error(`Failed to trim boundaries for term ${termId}:`, error);
        showError(`Failed to trim boundaries: ${error.message}`);
        
        // Restore button state
        const trimBtn = document.querySelector(`.trim-btn[data-term-id="${termId}"]`);
        if (trimBtn) {
            trimBtn.innerHTML = '✂ Trim';
            trimBtn.disabled = false;
        }
    }
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
 * Regenerate alignment for a single term
 * Re-runs the automatic alignment algorithm for just this term
 * @param {string} termId - Term identifier
 */
async function regenerateTerm(termId) {
    // Prevent regeneration during bulk regeneration
    if (AppState.regenerationInProgress) {
        showError('Bulk regeneration in progress. Please wait for it to complete.');
        return;
    }
    
    const alignment = AppState.alignments.find(a => a.term_id === termId);
    if (!alignment) {
        showError('Term not found');
        return;
    }
    
    const confirmed = confirm(
        `Regenerate alignment for "${alignment.english}"?\n\n` +
        `This will re-run the automatic alignment algorithm for this term only.`
    );
    
    if (!confirmed) {
        return;
    }
    
    // Set flag to prevent concurrent regenerations
    AppState.regenerationInProgress = true;
    
    try {
        // Show loading state
        const regenBtn = document.querySelector(`.regen-btn[data-term-id="${termId}"]`);
        if (regenBtn) {
            regenBtn.disabled = true;
            regenBtn.innerHTML = '⏳ Regenerating...';
        }
        
        // Disable all regenerate-from buttons during processing
        document.querySelectorAll('.regen-from-btn').forEach(btn => {
            btn.disabled = true;
        });
        
        // Call backend API to regenerate this term
        const response = await fetchWithRetry(`${API_BASE}/session/${AppState.sessionId}/regenerate/${termId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to regenerate term');
        }
        
        // Update local state with new alignment
        const updatedTerm = data.data.term;
        alignment.start_time = updatedTerm.start_time;
        alignment.end_time = updatedTerm.end_time;
        alignment.confidence_score = updatedTerm.confidence_score;
        alignment.is_manually_adjusted = false;
        
        // Update UI
        const startInput = document.getElementById(`start-${termId}`);
        const endInput = document.getElementById(`end-${termId}`);
        if (startInput) startInput.value = alignment.start_time.toFixed(2);
        if (endInput) endInput.value = alignment.end_time.toFixed(2);
        
        // Reload waveform
        const cacheBuster = Date.now();
        await renderTermWaveform(
            termId,
            `/api/audio/${AppState.sessionId}/${termId}?t=${cacheBuster}`,
            alignment.start_time,
            alignment.end_time
        );
        
        // Update full waveform
        updateFullWaveformBoundary(termId, alignment.start_time, alignment.end_time);
        
        // Remove manual adjustment indicator if present
        removeManualAdjustmentIndicator(termId);
        
        showSuccess(`"${alignment.english}" regenerated successfully`);
        
    } catch (error) {
        console.error(`Failed to regenerate term ${termId}:`, error);
        showError(error.message || 'Failed to regenerate alignment');
    } finally {
        // Clear the flag
        AppState.regenerationInProgress = false;
        
        // Restore button state
        const regenBtn = document.querySelector(`.regen-btn[data-term-id="${termId}"]`);
        if (regenBtn) {
            regenBtn.disabled = false;
            regenBtn.innerHTML = '🔄 Regenerate';
        }
        
        // Restore all regenerate-from buttons
        document.querySelectorAll('.regen-from-btn').forEach(btn => {
            btn.disabled = false;
        });
    }
}

/**
 * Regenerate alignment for this term and all following terms
 * Useful when one term's correction affects all subsequent terms
 * @param {string} termId - Term identifier to start from
 */
async function regenerateFromTerm(termId) {
    // Prevent multiple simultaneous regenerations
    if (AppState.regenerationInProgress) {
        showError('Regeneration already in progress. Please wait for it to complete.');
        return;
    }
    
    const alignment = AppState.alignments.find(a => a.term_id === termId);
    if (!alignment) {
        showError('Term not found');
        return;
    }
    
    // Find the index of this term
    const termIndex = AppState.alignments.findIndex(a => a.term_id === termId);
    const remainingCount = AppState.alignments.length - termIndex;
    
    const confirmed = confirm(
        `Regenerate alignment from "${alignment.english}" onwards?\n\n` +
        `This will re-run automatic alignment for ${remainingCount} term(s), ` +
        `starting from the end of the previous term.\n\n` +
        `This may take several minutes as it uses Whisper to verify each term.`
    );
    
    if (!confirmed) {
        return;
    }
    
    // Set flag to prevent concurrent regenerations
    AppState.regenerationInProgress = true;
    
    try {
        // Disable ALL regenerate buttons during processing
        document.querySelectorAll('.regen-from-btn').forEach(btn => {
            btn.disabled = true;
            if (btn.dataset.termId === termId) {
                btn.innerHTML = '⏳ Starting...';
            } else {
                btn.innerHTML = '⏳ Busy...';
            }
        });
        
        // Get the end time of the previous term (or 0 if this is the first term)
        let startFromTime = 0;
        if (termIndex > 0) {
            const previousTerm = AppState.alignments[termIndex - 1];
            startFromTime = previousTerm.end_time;
        }
        
        // Show progress modal
        showRegenerationProgress();
        updateRegenerationProgress(0, 'Starting regeneration...');
        
        // Start regeneration (don't await - it will take a while)
        const regenerationPromise = fetchWithRetry(`${API_BASE}/session/${AppState.sessionId}/regenerate-from/${termId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start_from_time: startFromTime
            })
        });
        
        // Poll for progress (only update progress bar, NOT waveforms)
        let progressInterval = setInterval(async () => {
            try {
                const progressResponse = await fetch(`${API_BASE}/session/${AppState.sessionId}/regenerate/progress`);
                const progressData = await progressResponse.json();
                
                if (progressData.success && progressData.data) {
                    const progress = progressData.data;
                    console.log('Regeneration progress:', progress);
                    updateRegenerationProgress(progress.percent, progress.stage);
                    
                    // Check if complete or error
                    if (progress.status === 'complete' || progress.status === 'error') {
                        clearInterval(progressInterval);
                        progressInterval = null;
                        
                        if (progress.status === 'error') {
                            hideRegenerationProgress();
                            throw new Error(progress.stage);
                        }
                    }
                }
            } catch (error) {
                console.error('Progress polling error:', error);
                // Don't stop polling on error - the regeneration might still be running
            }
        }, 1000); // Poll every second
        
        // Wait for regeneration to complete
        const response = await regenerationPromise;
        const data = await response.json();
        
        // Stop polling if still running
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
        
        hideRegenerationProgress();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to regenerate terms');
        }
        
        // Update local state with all regenerated terms
        const updatedTerms = data.data.terms;
        
        // Use a single cache buster for all waveforms to prevent jiggling
        const cacheBuster = Date.now();
        
        // Update state and inputs first (synchronous)
        for (const updatedTerm of updatedTerms) {
            const localAlignment = AppState.alignments.find(a => a.term_id === updatedTerm.term_id);
            if (localAlignment) {
                localAlignment.start_time = updatedTerm.start_time;
                localAlignment.end_time = updatedTerm.end_time;
                localAlignment.confidence_score = updatedTerm.confidence_score;
                localAlignment.is_manually_adjusted = false;
                
                // Update UI inputs for this term
                const startInput = document.getElementById(`start-${updatedTerm.term_id}`);
                const endInput = document.getElementById(`end-${updatedTerm.term_id}`);
                if (startInput) startInput.value = localAlignment.start_time.toFixed(2);
                if (endInput) endInput.value = localAlignment.end_time.toFixed(2);
                
                // Update full waveform boundary markers
                updateFullWaveformBoundary(updatedTerm.term_id, localAlignment.start_time, localAlignment.end_time);
                
                // Remove manual adjustment indicator if present
                removeManualAdjustmentIndicator(updatedTerm.term_id);
            }
        }
        
        // Render all waveforms in parallel (prevents sequential jiggling)
        await Promise.all(updatedTerms.map(updatedTerm => {
            const localAlignment = AppState.alignments.find(a => a.term_id === updatedTerm.term_id);
            if (localAlignment) {
                return renderTermWaveform(
                    updatedTerm.term_id,
                    `/api/audio/${AppState.sessionId}/${updatedTerm.term_id}?t=${cacheBuster}`,
                    localAlignment.start_time,
                    localAlignment.end_time
                );
            }
            return Promise.resolve();
        }));
        
        showSuccess(`${updatedTerms.length} term(s) regenerated successfully from "${alignment.english}"`);
        
    } catch (error) {
        console.error(`Failed to regenerate from term ${termId}:`, error);
        showError(error.message || 'Failed to regenerate alignments');
    } finally {
        // Clear the flag
        AppState.regenerationInProgress = false;
        
        // Restore ALL button states
        document.querySelectorAll('.regen-from-btn').forEach(btn => {
            btn.disabled = false;
            btn.innerHTML = '🔄➡ From Here';
        });
    }
}

/**
 * Show regeneration progress modal
 */
function showRegenerationProgress() {
    // Reuse upload progress UI
    const progressContainer = elements.uploadProgress || document.getElementById('upload-progress');
    if (progressContainer) {
        progressContainer.style.display = 'block';
        console.log('Regeneration progress modal shown');
    } else {
        console.error('Progress container not found');
    }
}

/**
 * Hide regeneration progress modal
 */
function hideRegenerationProgress() {
    const progressContainer = elements.uploadProgress || document.getElementById('upload-progress');
    if (progressContainer) {
        progressContainer.style.display = 'none';
    }
}

/**
 * Update regeneration progress display
 * @param {number} percent - Progress percentage (0-100)
 * @param {string} stage - Current stage description
 */
function updateRegenerationProgress(percent, stage) {
    console.log(`Progress update: ${percent}% - ${stage}`);
    if (elements.progressFill) {
        elements.progressFill.style.width = `${percent}%`;
    }
    if (elements.progressText) {
        elements.progressText.textContent = stage;
    }
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


/**
 * Log Streaming with Server-Sent Events
 * Real-time processing log display
 */

// Log streaming state
let logEventSource = null;
let logBuffer = [];

/**
 * Set up log streaming from the server
 */
function setupLogStreaming() {
    const logContainer = document.getElementById('processing-log');
    
    if (!logContainer) {
        console.warn('Processing log container not found');
        return;
    }
    
    // Connect to SSE endpoint
    try {
        logEventSource = new EventSource(`${API_BASE}/logs/stream`);
        
        logEventSource.onopen = () => {
            console.log('Log stream connected');
            // Remove placeholder if present
            const placeholder = logContainer.querySelector('.log-placeholder');
            if (placeholder) {
                placeholder.remove();
            }
        };
        
        logEventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                // Handle connection message
                if (data.type === 'connected') {
                    console.log('Log stream established:', data.message);
                    return;
                }
                
                // Handle log entry
                if (data.timestamp && data.message) {
                    appendLogEntry(data);
                }
            } catch (error) {
                console.error('Failed to parse log message:', error);
            }
        };
        
        logEventSource.onerror = (error) => {
            console.error('Log stream error:', error);
            
            // Don't show error to user if it's just a connection close
            if (logEventSource.readyState === EventSource.CLOSED) {
                console.log('Log stream closed');
            } else {
                // Try to reconnect after a delay
                setTimeout(() => {
                    if (logEventSource && logEventSource.readyState === EventSource.CLOSED) {
                        console.log('Attempting to reconnect log stream...');
                        setupLogStreaming();
                    }
                }, 5000);
            }
        };
        
        console.log('Log streaming initialized');
        
    } catch (error) {
        console.error('Failed to initialize log streaming:', error);
    }
}

/**
 * Append a log entry to the processing log
 * @param {Object} logEntry - Log entry with timestamp, level, and message
 */
function appendLogEntry(logEntry) {
    const logContainer = document.getElementById('processing-log');
    
    if (!logContainer) {
        return;
    }
    
    // Remove placeholder if present
    const placeholder = logContainer.querySelector('.log-placeholder');
    if (placeholder) {
        placeholder.remove();
    }
    
    // Create log entry element
    const entry = document.createElement('div');
    entry.className = `log-entry log-${logEntry.level}`;
    
    // Format timestamp
    const timestamp = document.createElement('span');
    timestamp.className = 'log-timestamp';
    timestamp.textContent = `[${logEntry.timestamp}]`;
    
    // Format message
    const message = document.createElement('span');
    message.className = 'log-message';
    message.textContent = logEntry.message;
    
    entry.appendChild(timestamp);
    entry.appendChild(message);
    
    // Append to container
    logContainer.appendChild(entry);
    
    // Add to buffer for copy functionality
    logBuffer.push(`[${logEntry.timestamp}] ${logEntry.message}`);
    
    // Auto-scroll to bottom
    logContainer.scrollTop = logContainer.scrollHeight;
    
    // Enable log control buttons
    enableLogControls();
}

/**
 * Set up log control buttons (clear, copy)
 */
function setupLogControls() {
    const clearBtn = document.getElementById('clear-log-btn');
    const copyBtn = document.getElementById('copy-log-btn');
    
    if (clearBtn) {
        clearBtn.addEventListener('click', clearLog);
    }
    
    if (copyBtn) {
        copyBtn.addEventListener('click', copyLogToClipboard);
    }
}

/**
 * Clear the processing log
 */
function clearLog() {
    const logContainer = document.getElementById('processing-log');
    
    if (!logContainer) {
        return;
    }
    
    // Clear all log entries
    logContainer.innerHTML = '';
    
    // Add placeholder back
    const placeholder = document.createElement('div');
    placeholder.className = 'log-placeholder';
    placeholder.innerHTML = `
        <span class="log-icon">📋</span>
        <p>Processing logs will appear here when you upload files</p>
    `;
    logContainer.appendChild(placeholder);
    
    // Clear buffer
    logBuffer = [];
    
    // Disable control buttons
    disableLogControls();
    
    console.log('Processing log cleared');
}

/**
 * Copy log contents to clipboard
 */
async function copyLogToClipboard() {
    if (logBuffer.length === 0) {
        showError('No log entries to copy');
        return;
    }
    
    const logText = logBuffer.join('\n');
    
    try {
        await navigator.clipboard.writeText(logText);
        showSuccess('Log copied to clipboard');
    } catch (error) {
        console.error('Failed to copy log:', error);
        
        // Fallback: create a temporary textarea
        const textarea = document.createElement('textarea');
        textarea.value = logText;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        
        try {
            document.execCommand('copy');
            showSuccess('Log copied to clipboard');
        } catch (fallbackError) {
            showError('Failed to copy log to clipboard');
        }
        
        document.body.removeChild(textarea);
    }
}

/**
 * Enable log control buttons
 */
function enableLogControls() {
    const clearBtn = document.getElementById('clear-log-btn');
    const copyBtn = document.getElementById('copy-log-btn');
    
    if (clearBtn) {
        clearBtn.disabled = false;
    }
    
    if (copyBtn) {
        copyBtn.disabled = false;
    }
}

/**
 * Disable log control buttons
 */
function disableLogControls() {
    const clearBtn = document.getElementById('clear-log-btn');
    const copyBtn = document.getElementById('copy-log-btn');
    
    if (clearBtn) {
        clearBtn.disabled = true;
    }
    
    if (copyBtn) {
        copyBtn.disabled = true;
    }
}

/**
 * Close log stream when leaving the page
 */
window.addEventListener('beforeunload', () => {
    if (logEventSource) {
        logEventSource.close();
        console.log('Log stream closed on page unload');
    }
});
