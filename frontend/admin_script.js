document.addEventListener('DOMContentLoaded', () => {
    // --- API Configuration ---
    const API_BASE_URL = 'http://127.0.0.1:8000'; // Make sure this matches your FastAPI server's address.
    const API_UPLOAD_URL = `${API_BASE_URL}/upload_and_ingest`;
    const API_INGESTION_STATUS_URL = `${API_BASE_URL}/ingestion_status`;
    const API_DELETE_FILE_URL = `${API_BASE_URL}/delete_document`;
    const API_LIST_FILES_URL = `${API_BASE_URL}/list_documents`; // Endpoint to list existing files

    // --- DOM Elements ---
    const fileUpload = document.getElementById('file-upload');
    const uploadButton = document.getElementById('upload-button');
    const fileListTbody = document.getElementById('file-list-tbody');
    const uploadStatus = document.getElementById('upload-status');
    const ingestionStatus = document.getElementById('ingestion-status');
    const noFilesRow = document.getElementById('no-files-row');
    const uploadArea = document.querySelector('.upload-area');
    const logoutButton = document.getElementById('logout-button'); // Assuming you add a logout button to admin.html

    let pollingIntervalId = null;
    let adminAccessToken = localStorage.getItem('adminAccessToken'); // Retrieve token

    // --- Helper Functions ---

    /**
     * Sets a status message in a given HTML element, with optional styling for type.
     * @param {HTMLElement} element - The DOM element to update (e.g., uploadStatus, ingestionStatus).
     * @param {string} message - The text message to display.
     * @param {'info'|'success'|'error'|'clear'} type - Type of message for styling or clearing.
     */
    function setStatus(element, message, type = 'info') {
        element.textContent = message;
        element.style.display = 'block'; // Ensure it's visible
        element.classList.remove('status-message-info', 'status-message-success', 'status-message-error');

        if (type === 'clear') {
            element.textContent = '';
            element.style.display = 'none'; // Hide if cleared
        } else if (type === 'error') {
            element.classList.add('status-message-error');
        } else if (type === 'success') {
            element.classList.add('status-message-success');
        } else { // 'info' or default
            element.classList.add('status-message-info');
        }
    }

    /**
     * Creates the authorization header for API requests.
     * @returns {object} An object with the Authorization header.
     */
    function createAuthHeader() {
        return {
            'Authorization': `Bearer ${adminAccessToken}`
        };
    }

    /**
     * Handles unauthorized responses by redirecting to the login page.
     */
    function handleUnauthorized() {
        console.log('Unauthorized access. Redirecting to login.');
        localStorage.removeItem('adminAccessToken'); // Clear invalid token
        alert('Your session has expired or is invalid. Please log in again.');
        window.location.href = 'login.html';
    }

    /**
     * Checks if the user is authenticated. If not, redirects to the login page.
     * Also fetches the initial list of documents if authenticated.
     */
    async function checkAuthentication() {
        if (!adminAccessToken) {
            handleUnauthorized();
            return false;
        }

        try {
            // Test if the token is valid by trying to list documents
            const response = await fetch(API_LIST_FILES_URL, {
                method: 'GET',
                headers: createAuthHeader(),
            });

            if (response.ok) {
                console.log('Access token is valid.');
                await listFiles(); // Load documents if authenticated
                return true;
            } else if (response.status === 401) {
                handleUnauthorized();
                return false;
            } else {
                console.error('Authentication check failed with status:', response.status);
                handleUnauthorized();
                return false;
            }
        } catch (error) {
            console.error('Error during authentication check:', error);
            // This might be a network error or CORS issue before a 401 response.
            // Treat as unauthorized for now to prevent further issues.
            handleUnauthorized();
            return false;
        }
    }

    /**
     * Returns the appropriate Font Awesome icon class and a specific color class based on file extension.
     * @param {string} filename - The name of the file.
     * @returns {object} An object containing { iconClass: string, colorClass: string }.
     */
    function getFileIconAndColor(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        let iconClass = 'fas fa-file-alt'; // Default icon
        let colorClass = ''; // Default color class for specific styling

        switch (ext) {
            case 'pdf': iconClass = 'fas fa-file-pdf'; colorClass = 'pdf'; break;
            case 'doc':
            case 'docx': iconClass = 'fas fa-file-word'; colorClass = 'doc'; break;
            case 'txt': iconClass = 'fas fa-file-alt'; colorClass = 'txt'; break;
            case 'md': iconClass = 'fas fa-file-code'; colorClass = 'md'; break;
            case 'json': iconClass = 'fas fa-file-code'; colorClass = 'json'; break;
            case 'html':
            case 'htm': iconClass = 'fas fa-file-code'; colorClass = 'html'; break;
            case 'epub': iconClass = 'fas fa-book-open'; colorClass = 'epub'; break;
            case 'ppt':
            case 'pptx': iconClass = 'fas fa-file-powerpoint'; colorClass = 'ppt'; break;
            case 'csv': iconClass = 'fas fa-file-csv'; colorClass = 'csv'; break;
            case 'odt': iconClass = 'fas fa-file-alt'; colorClass = 'odt'; break;
            case 'enex': iconClass = 'fas fa-file-alt'; colorClass = 'enex'; break;
        }
        return { iconClass, colorClass };
    }

    /**
     * Creates a status badge element with appropriate classes and text.
     * @param {string} status - The status string (e.g., "PENDING", "COMPLETED").
     * @returns {HTMLElement} The span element for the status badge.
     */
    function createStatusBadge(status) {
        const badge = document.createElement('span');
        badge.classList.add('status-badge');
        badge.textContent = status.replace('_', ' ');
        badge.classList.add(status.toLowerCase().replace(/_/g, '-')); // Use kebab-case for CSS
        return badge;
    }

    /**
     * Shows a custom confirmation modal.
     * @param {string} message - The message to display in the modal.
     * @returns {Promise<boolean>} Resolves to true if confirmed, false otherwise.
     */
    function showConfirmationModal(message) {
        return new Promise(resolve => {
            const modalOverlay = document.createElement('div');
            modalOverlay.classList.add('modal-overlay');
            const modalContent = document.createElement('div');
            modalContent.classList.add('modal-content');

            modalContent.innerHTML = `
                <p>${message}</p>
                <div class="modal-buttons">
                    <button id="confirm-yes" class="button-confirm-yes">Yes</button>
                    <button id="confirm-no" class="button-confirm-no">No</button>
                </div>
            `;

            modalOverlay.appendChild(modalContent);
            document.body.appendChild(modalOverlay);

            const confirmYes = document.getElementById('confirm-yes');
            const confirmNo = document.getElementById('confirm-no');

            confirmYes.addEventListener('click', () => {
                document.body.removeChild(modalOverlay);
                resolve(true);
            });

            confirmNo.addEventListener('click', () => {
                document.body.removeChild(modalOverlay);
                resolve(false);
            });
        });
    }

    // --- Document Upload Logic ---
    async function uploadFiles(files) {
        if (files.length === 0) {
            setStatus(uploadStatus, 'Please select or drag files to upload.', 'info');
            fileUpload.disabled = false;
            return;
        }

        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        setStatus(uploadStatus, `Uploading ${files.length} file(s)...`, 'info');
        setStatus(ingestionStatus, 'Waiting for server response...', 'info');
        fileUpload.disabled = true;
        uploadButton.disabled = true; // Disable upload button

        try {
            const response = await fetch(API_UPLOAD_URL, {
                method: 'POST',
                headers: createAuthHeader(), // Send authorization header
                body: formData,
            });

            if (response.status === 401) {
                handleUnauthorized();
                return;
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || `HTTP error! status: ${response.status}`);
            }

            setStatus(uploadStatus, 'Files uploaded to server. Starting ingestion...', 'success');
            setStatus(ingestionStatus, 'Ingestion processing in background. This may take some time...', 'info');

            const taskId = data.task_id;
            const uploadedFileNames = data.filenames;

            // Clear previous table rows and add a temporary loading message or show "No files" initially
            fileListTbody.innerHTML = '';
            if (noFilesRow) noFilesRow.style.display = 'none'; // Hide "No files" while adding new ones

            uploadedFileNames.forEach(filename => {
                // The filename from backend is the exact name, safe to use directly for display and dataset
                const fileInfo = getFileIconAndColor(filename);

                const newRow = document.createElement('tr');
                newRow.id = `file-row-${taskId}-${btoa(filename)}`; // Use base64 for ID for safer filename hashing
                newRow.innerHTML = `
                    <td class="file-name-cell"><i class="${fileInfo.iconClass} file-icon ${fileInfo.colorClass}"></i> ${filename}</td>
                    <td class="file-status-cell"></td>
                    <td>N/A</td> <td><button class="delete-button" data-filename="${filename}" title="Delete ${filename}"><i class="fas fa-trash-alt"></i></button></td>
                `;
                fileListTbody.appendChild(newRow);

                // Update the status badge for newly added files
                const statusCell = newRow.querySelector('.file-status-cell');
                if (statusCell) {
                    const statusBadge = createStatusBadge('PENDING');
                    statusCell.appendChild(statusBadge);
                }
            });

            startPollingIngestionStatus(taskId);

        } catch (error) {
            console.error('Error during upload:', error);
            setStatus(uploadStatus, `Upload failed: ${error.message}`, 'error');
            setStatus(ingestionStatus, '', 'clear');
            fileUpload.disabled = false;
            uploadButton.disabled = false; // Enable upload button on failure
            fileUpload.value = ''; // Clear file input selection
            if (fileListTbody.children.length === 0 && noFilesRow) {
                noFilesRow.style.display = '';
            }
        }
    }

    // --- Ingestion Status Polling Logic ---
    async function startPollingIngestionStatus(taskId) {
        if (pollingIntervalId) {
            clearInterval(pollingIntervalId);
        }

        pollingIntervalId = setInterval(async () => {
            try {
                const response = await fetch(`${API_INGESTION_STATUS_URL}/${taskId}`, {
                    method: 'GET',
                    headers: createAuthHeader(), // Send authorization header
                });

                if (response.status === 401) {
                    handleUnauthorized();
                    clearInterval(pollingIntervalId); // Stop polling on auth error
                    return;
                }

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || `HTTP error! status: ${response.status}`);
                }

                setStatus(ingestionStatus, `Ingestion status: ${data.status}...`, 'info');

                data.files.forEach(fileInfo => {
                    const rowId = `file-row-${taskId}-${btoa(fileInfo.filename)}`;
                    const fileRow = document.getElementById(rowId);

                    if (fileRow) {
                        const statusCell = fileRow.querySelector('.file-status-cell');
                        if (statusCell) {
                            statusCell.innerHTML = ''; // Clear previous content
                            const statusBadge = createStatusBadge(fileInfo.status);
                            statusCell.appendChild(statusBadge);

                            if (fileInfo.status === 'IN_PROGRESS') {
                                const progressContainer = document.createElement('div');
                                progressContainer.classList.add('progress-container');
                                const progressBar = document.createElement('div');
                                progressBar.classList.add('progress-bar');
                                progressBar.style.width = `${fileInfo.progress || 0}%`; // Assuming backend provides progress
                                progressContainer.appendChild(progressBar);
                                statusCell.appendChild(progressContainer);
                            }
                        }
                    } else {
                        // This block handles files that might appear in the backend's task list
                        // but were not initially rendered by the frontend (e.g., if page reloaded).
                        // It ensures they are added to the table.
                        const newRow = document.createElement('tr');
                        newRow.id = rowId;
                        const fileInfoDetails = getFileIconAndColor(fileInfo.filename);

                        newRow.innerHTML = `
                            <td class="file-name-cell"><i class="${fileInfoDetails.iconClass} file-icon ${fileInfoDetails.colorClass}"></i> ${fileInfo.filename}</td>
                            <td class="file-status-cell"></td>
                            <td>N/A</td>
                            <td><button class="delete-button" data-filename="${fileInfo.filename}" title="Delete ${fileInfo.filename}"><i class="fas fa-trash-alt"></i></button></td>
                        `;
                        fileListTbody.appendChild(newRow);

                        const statusCell = newRow.querySelector('.file-status-cell');
                        if (statusCell) {
                            const statusBadge = createStatusBadge(fileInfo.status);
                            statusCell.appendChild(statusBadge);
                            if (fileInfo.status === 'IN_PROGRESS') {
                                const progressContainer = document.createElement('div');
                                progressContainer.classList.add('progress-container');
                                const progressBar = document.createElement('div');
                                progressBar.classList.add('progress-bar');
                                progressBar.style.width = `${fileInfo.progress || 0}%`;
                                progressContainer.appendChild(progressBar);
                                statusCell.appendChild(progressContainer);
                            }
                        }
                    }
                });

                if (data.status === 'COMPLETED') {
                    clearInterval(pollingIntervalId);
                    setStatus(ingestionStatus, 'Ingestion complete! Documents are ready for querying.', 'success');
                    setStatus(uploadStatus, 'Upload & Ingestion successful!', 'success');
                    fileUpload.disabled = false;
                    uploadButton.disabled = false;
                    fileUpload.value = ''; // Clear input
                    pollingIntervalId = null;
                    listFiles(); // Refresh the list to show all currently ingested documents
                } else if (data.status === 'FAILED') {
                    clearInterval(pollingIntervalId);
                    setStatus(ingestionStatus, 'Ingestion failed! Please check server logs for details.', 'error');
                    setStatus(uploadStatus, 'Upload & Ingestion failed!', 'error');
                    fileUpload.disabled = false;
                    uploadButton.disabled = false;
                    fileUpload.value = ''; // Clear input
                    pollingIntervalId = null;
                    listFiles(); // Refresh to ensure status reflects failure
                }

            } catch (error) {
                console.error('Error during ingestion status polling:', error);
                clearInterval(pollingIntervalId);
                setStatus(ingestionStatus, `Ingestion status check failed: ${error.message}`, 'error');
                setStatus(uploadStatus, 'Upload & Ingestion failed!', 'error');
                fileUpload.disabled = false;
                uploadButton.disabled = false;
                fileUpload.value = ''; // Clear input
                pollingIntervalId = null;
            } finally {
                // Ensure "No files" message is shown if the list is empty after polling stops
                if (fileListTbody.children.length === 0 && noFilesRow && pollingIntervalId === null) {
                    noFilesRow.style.display = '';
                }
            }
        }, 3000); // Poll every 3 seconds
    }

    // --- Document Listing & Deletion Logic ---

    /**
     * Lists all currently ingested documents from the backend.
     */
    async function listFiles() {
        fileListTbody.innerHTML = ''; // Clear current list
        if (noFilesRow) noFilesRow.style.display = 'none'; // Hide "No files" temporarily
        setStatus(ingestionStatus, 'Loading existing documents...', 'info');

        try {
            const response = await fetch(API_LIST_FILES_URL, {
                method: 'GET',
                headers: createAuthHeader(), // Send authorization header
            });

            if (response.status === 401) {
                handleUnauthorized();
                return;
            }

            const documents = await response.json();

            if (documents.length === 0) {
                if (noFilesRow) noFilesRow.style.display = ''; // Show "No files" if empty
                setStatus(ingestionStatus, 'No documents currently ingested.', 'info');
                return;
            }

            setStatus(ingestionStatus, 'Documents loaded.', 'success');

            documents.forEach(filename => {
                const fileInfo = getFileIconAndColor(filename);
                const newRow = document.createElement('tr');
                // Use a reliable ID; for simplicity, could be based on filename, or get an actual ID from backend if available
                newRow.id = `file-row-existing-${btoa(filename)}`;
                newRow.innerHTML = `
                    <td class="file-name-cell"><i class="${fileInfo.iconClass} file-icon ${fileInfo.colorClass}"></i> ${filename}</td>
                    <td class="file-status-cell">${createStatusBadge('COMPLETED').outerHTML}</td> <td>N/A</td>
                    <td><button class="delete-button" data-filename="${filename}" title="Delete ${filename}"><i class="fas fa-trash-alt"></i></button></td>
                `;
                fileListTbody.appendChild(newRow);
            });

            // Re-attach event listeners for newly added delete buttons
            attachDeleteButtonListeners();

        } catch (error) {
            console.error('Error listing files:', error);
            setStatus(ingestionStatus, `Failed to load documents: ${error.message}`, 'error');
            if (fileListTbody.children.length === 0 && noFilesRow) {
                noFilesRow.style.display = '';
            }
        }
    }

    /**
     * Attaches event listeners to all delete buttons in the file list.
     * This is useful when the list is dynamically updated.
     */
    function attachDeleteButtonListeners() {
        fileListTbody.querySelectorAll('.delete-button').forEach(button => {
            button.onclick = null; // Remove previous listener to prevent duplicates
            button.addEventListener('click', (event) => {
                const filename = event.currentTarget.dataset.filename;
                const rowElement = event.currentTarget.closest('tr');
                if (filename && rowElement) {
                    deleteFile(filename, rowElement);
                }
            });
        });
    }

    /**
     * Handles the deletion of a file.
     * @param {string} filename - The original filename of the document to delete.
     * @param {HTMLElement} rowElement - The table row element associated with the file.
     */
    async function deleteFile(filename, rowElement) {
        const confirmed = await showConfirmationModal(`Are you sure you want to delete "${filename}"? This action will re-ingest all remaining documents.`);

        if (!confirmed) {
            return;
        }

        setStatus(uploadStatus, `Deleting ${filename}...`, 'info');
        // Disable the specific delete button during operation
        const deleteButton = rowElement.querySelector('.delete-button');
        if (deleteButton) deleteButton.disabled = true;

        try {
            const response = await fetch(`${API_DELETE_FILE_URL}/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
                headers: createAuthHeader(), // Send authorization header
            });

            if (response.status === 401) {
                handleUnauthorized();
                return;
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || `HTTP error! status: ${response.status}`);
            }

            setStatus(uploadStatus, `Successfully deleted "${filename}". Re-ingestion triggered.`, 'success');
            rowElement.remove(); // Remove the row from the table

            // If the table is now empty, show the "No documents" message
            if (fileListTbody.children.length === 0 && noFilesRow) {
                noFilesRow.style.display = '';
            }

            // After deletion, immediately refresh the list to show the current state of documents
            // and potentially updated ingestion status if the backend provides it immediately.
            listFiles();

        } catch (error) {
            console.error(`Error deleting file ${filename}:`, error);
            setStatus(uploadStatus, `Failed to delete "${filename}": ${error.message}`, 'error');
        } finally {
            if (deleteButton) deleteButton.disabled = false; // Re-enable button if still present
        }
    }

    // --- Event Listeners ---

    // Logout Button
    logoutButton.addEventListener('click', () => {
        localStorage.removeItem('adminAccessToken');
        adminAccessToken = null;
        alert('You have been logged out.');
        window.location.href = 'login.html'; // Redirect to login page
    });

    // File Input Change (for traditional click-to-select)
    fileUpload.addEventListener('change', () => {
        uploadFiles(fileUpload.files);
    });

    // Drag and Drop Event Listeners
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('drag-over'), false);
    });

    uploadArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        uploadFiles(files);
    }, false);

    // Initial check for authentication when admin.html loads
    checkAuthentication();
});
