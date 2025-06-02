document.addEventListener('DOMContentLoaded', () => {
    // Get references to all necessary HTML elements
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const chatWindow = document.getElementById('chat-window');
    const fileUpload = document.getElementById('file-upload');
    const fileList = document.getElementById('file-list');
    const uploadStatus = document.getElementById('upload-status');
    const ingestionStatus = document.getElementById('ingestion-status');
    const queryStatus = document.getElementById('query-status');

    // Define API endpoints. Ensure API_BASE_URL matches your FastAPI server's address.
    const API_BASE_URL = 'http://127.0.0.1:8000';
    const API_QUERY_URL = `${API_BASE_URL}/query`;
    const API_UPLOAD_URL = `${API_BASE_URL}/upload_and_ingest`;
    const API_INGESTION_STATUS_URL = `${API_BASE_URL}/ingestion_status`;

    // --- Helper Functions ---

    /**
     * Appends a new message (user or bot) to the chat window.
     * @param {string} sender - 'user' or 'bot'.
     * @param {string} text - The message content to display.
     * @param {Array<Object>} sources - Optional array of source documents (for bot messages).
     */
    function appendMessage(sender, text, sources = []) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);
        messageDiv.innerHTML = `<p>${text}</p>`;

        // If sources are provided (typically for bot messages), display them
        if (sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.classList.add('source-documents');
            sourcesDiv.innerHTML = '<h4>Sources:</h4>';
            sources.forEach(source => {
                // Safely extract source path and get just the filename
                const sourcePath = source.metadata && source.metadata.source ? source.metadata.source : 'Unknown Source';
                const sourceFilename = sourcePath.split(/[\\/]/).pop(); // Handles both Unix (/) and Windows (\) paths
                
                // Truncate content snippet for display to keep it concise
                const contentSnippet = source.page_content ?
                    source.page_content.substring(0, Math.min(source.page_content.length, 250)) + (source.page_content.length > 250 ? '...' : '')
                    : 'No content snippet available.';
                
                sourcesDiv.innerHTML += `<p><strong>${sourceFilename}</strong>: ${contentSnippet}</p>`;
            });
            messageDiv.appendChild(sourcesDiv);
        }

        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight; // Auto-scroll to the latest message
    }

    /**
     * Sets a status message in a given HTML element, with optional styling for type.
     * @param {HTMLElement} element - The DOM element to update (e.g., uploadStatus, ingestionStatus).
     * @param {string} message - The text message to display.
     * @param {'info'|'success'|'error'|'clear'} type - Type of message for styling or clearing.
     */
    function setStatus(element, message, type = 'info') {
        element.textContent = message;
        // Reset color first to clear previous states
        element.style.color = ''; 
        if (type === 'clear') {
            element.textContent = ''; // Clear the text content
        } else if (type === 'error') {
            element.style.color = '#d9534f'; // Red color for errors
        } else if (type === 'success') {
            element.style.color = '#5cb85c'; // Green color for success
        } else { // 'info' or default
            element.style.color = '#555'; // Grey color for informational messages
        }
    }

    /**
     * Dynamically resizes a textarea element based on its content to create an auto-growing effect.
     * @param {HTMLTextAreaElement} element - The textarea element to resize.
     */
    function autoResizeTextarea(element) {
        element.style.height = 'auto'; // Reset height to recalculate
        element.style.height = element.scrollHeight + 'px'; // Set height to fit content
    }

    // --- Chat Logic ---
    async function sendMessage() {
        const query = userInput.value.trim();
        if (!query) return; // Do not send empty queries

        appendMessage('user', query); // Display user's message in chat
        userInput.value = ''; // Clear the input field
        autoResizeTextarea(userInput); // Reset textarea height

        sendButton.disabled = true; // Disable send button to prevent multiple submissions
        setStatus(queryStatus, 'Generating response...', 'info'); // Show loading status

        try {
            const response = await fetch(API_QUERY_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: query }),
            });

            const data = await response.json(); // Parse the JSON response

            if (!response.ok) {
                // If the HTTP response status is not OK (e.g., 400, 500), throw an error
                throw new Error(data.detail || `HTTP error! status: ${response.status}`);
            }

            // Check if the backend's response data contains an 'error' field (for custom backend errors)
            if (data.error) {
                appendMessage('bot', `Error: ${data.error}`);
                setStatus(queryStatus, `Error: ${data.error}`, 'error');
            } else {
                appendMessage('bot', data.answer, data.source_documents); // Display bot's answer and sources
                setStatus(queryStatus, 'Response generated.', 'success');
            }

        } catch (error) {
            console.error('Error fetching data:', error); // Log detailed error to console
            // Display a user-friendly error message in the chat and status area
            appendMessage('bot', `An error occurred: ${error.message}. Please check the server logs.`);
            setStatus(queryStatus, `Error: ${error.message}`, 'error');
        } finally {
            sendButton.disabled = false; // Re-enable send button
            userInput.focus(); // Set focus back to the input field
        }
    }

    // --- Document Upload Logic ---
    let pollingIntervalId = null; // Variable to store the interval ID for polling, allows clearing it later

    async function handleFileUpload() {
        console.log('DEBUG: handleFileUpload function triggered.'); // Debugging line 1

        const files = fileUpload.files; // Get the FileList object from the input
        console.log('DEBUG: Files object:', files); // Debugging line 2
        console.log('DEBUG: Number of files selected:', files.length); // Debugging line 3

        if (files.length === 0) {
            console.log('DEBUG: No files selected, exiting handleFileUpload.'); // Debugging line 4
            setStatus(uploadStatus, 'Please select a file to upload.', 'info');
            fileUpload.disabled = false; // Re-enable file input
            sendButton.disabled = false; // Re-enable chat button
            return;
        }

        const formData = new FormData(); // Create a FormData object to send files
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]); // Append each selected file
        }
        console.log('DEBUG: FormData prepared.'); // Debugging line 5

        // Update UI status messages and disable interactive elements
        setStatus(uploadStatus, `Uploading ${files.length} file(s)...`, 'info');
        setStatus(ingestionStatus, 'Waiting for server response...', 'info');
        fileUpload.disabled = true; // Disable file input during upload
        sendButton.disabled = true; // Disable chat input during upload

        console.log('DEBUG: Attempting to send fetch request to API_UPLOAD_URL:', API_UPLOAD_URL); // Debugging line 6
        try {
            const response = await fetch(API_UPLOAD_URL, {
                method: 'POST',
                body: formData, // FormData automatically sets 'Content-Type': 'multipart/form-data'
            });
            console.log('DEBUG: Fetch request completed, response received. Status:', response.status); // Debugging line 7

            const data = await response.json(); // Parse the JSON response from the backend
            console.log('DEBUG: Response data from upload:', data); // Debugging line 8

            if (!response.ok) {
                // If the HTTP response status is not OK, log and throw an error
                console.error('DEBUG: API upload response not OK. Status:', response.status, 'Details:', data.detail); // Debugging line 9
                throw new Error(data.detail || `HTTP error! status: ${response.status}`);
            }

            // Initial success message for upload, start ingestion message
            setStatus(uploadStatus, 'Files uploaded to server. Starting ingestion...', 'success');
            setStatus(ingestionStatus, 'Ingestion processing in background. This may take some time...', 'info');

            const taskId = data.task_id; // Get the unique task ID from the backend response
            const uploadedFileNames = data.filenames; // Get the list of original filenames

            console.log('DEBUG: Upload successful. Task ID:', taskId, 'Filenames:', uploadedFileNames); // Debugging line 10

            // Clear previous list items and add new ones with initial 'Pending' status
            fileList.innerHTML = ''; 
            uploadedFileNames.forEach(filename => {
                // Sanitize filename to create a valid HTML ID (replace non-alphanumeric with hyphens)
                const safeFilename = filename.replace(/[^a-zA-Z0-9.\-_]/g, '-');
                const listItem = document.createElement('li');
                // Create a unique ID for each list item using task ID and sanitized filename
                listItem.id = `file-${taskId}-${safeFilename}`; 
                listItem.innerHTML = `<i class="fas fa-file-alt"></i> ${filename} <span class="ingestion-status-text">(Pending)</span>`;
                fileList.appendChild(listItem);
            });

            // Start polling the backend for real-time ingestion status updates
            startPollingIngestionStatus(taskId); 
            console.log('DEBUG: Polling started.'); // Debugging line 11

        } catch (error) {
            // Catch any errors during the upload process (network issues, server errors, etc.)
            console.error('Error during upload (caught in handleFileUpload catch block):', error); // Debugging line 12
            setStatus(uploadStatus, `Upload failed: ${error.message}`, 'error');
            setStatus(ingestionStatus, '', 'clear'); // Clear ingestion status on upload failure
            fileUpload.disabled = false; // Re-enable file input
            sendButton.disabled = false; // Re-enable chat button
            fileUpload.value = ''; // Clear selected files in the input field
        }
        // The 'finally' block is intentionally omitted here because we want buttons to remain disabled
        // until the polling process confirms ingestion completion or failure.
    }

    /**
     * Starts a polling mechanism to periodically check the status of an ingestion task.
     * @param {string} taskId - The ID of the ingestion task to monitor.
     */
    async function startPollingIngestionStatus(taskId) {
        console.log('DEBUG: Starting polling for task ID:', taskId); // Debugging line 13
        // Clear any existing polling interval to prevent multiple intervals running simultaneously
        if (pollingIntervalId) {
            clearInterval(pollingIntervalId);
        }

        // Set up a new interval to poll the status every 3 seconds
        pollingIntervalId = setInterval(async () => {
            console.log('DEBUG: Polling for status of task ID:', taskId); // Debugging line 14
            try {
                const response = await fetch(`${API_INGESTION_STATUS_URL}/${taskId}`);
                const data = await response.json(); // Parse the JSON response
                console.log('DEBUG: Polling response data:', data); // Debugging line 15

                if (!response.ok) {
                    // If the HTTP response status is not OK, log and throw an error
                    console.error('DEBUG: API polling response not OK. Status:', response.status, 'Details:', data.detail); // Debugging line 16
                    throw new Error(data.detail || `HTTP error! status: ${response.status}`);
                }

                // Update the overall ingestion status message in the UI
                setStatus(ingestionStatus, `Ingestion status: ${data.status}...`, 'info');

                // Iterate through the 'files' array returned by the backend to update individual file statuses
                data.files.forEach(fileInfo => {
                    // Sanitize filename for use in ID to match the one created during initial rendering
                    const safeFilename = fileInfo.filename.replace(/[^a-zA-Z0-9.\-_]/g, '-');
                    const listItemId = `file-${taskId}-${safeFilename}`;
                    // Find the specific list item's status span
                    const fileStatusSpan = document.querySelector(`#${listItemId} .ingestion-status-text`);
                    
                    if (fileStatusSpan) {
                        // Update the text content with the individual file's status
                        fileStatusSpan.textContent = `(${fileInfo.status})`; 
                        // Apply color based on the individual file's status
                        if (fileInfo.status === 'COMPLETED') {
                            fileStatusSpan.style.color = '#5cb85c'; // Green for completed
                        } else if (fileInfo.status === 'FAILED') {
                            fileStatusSpan.style.color = '#d9534f'; // Red for failed
                        } else {
                            fileStatusSpan.style.color = '#555'; // Grey for pending/in-progress
                        }
                    } else {
                        // This 'else' block handles a scenario where a file might be in the backend's task list
                        // but wasn't initially rendered by the frontend (unlikely with current logic, but robust).
                        const newListItem = document.createElement('li');
                        newListItem.id = listItemId;
                        newListItem.innerHTML = `<i class="fas fa-file-alt"></i> ${fileInfo.filename} <span class="ingestion-status-text">(${fileInfo.status})</span>`;
                        fileList.appendChild(newListItem);
                        const newFileStatusSpan = newListItem.querySelector('.ingestion-status-text');
                        if (newFileStatusSpan) {
                            if (fileInfo.status === 'COMPLETED') {
                                newFileStatusSpan.style.color = '#5cb85c';
                            } else if (fileInfo.status === 'FAILED') {
                                newFileStatusSpan.style.color = '#d9534f';
                            } else {
                                newFileStatusSpan.style.color = '#555';
                            }
                        }
                    }
                });

                // Check the overall task status to determine if polling should stop
                if (data.status === 'COMPLETED') {
                    clearInterval(pollingIntervalId); // Stop polling
                    setStatus(ingestionStatus, 'Ingestion complete! Documents are ready for querying.', 'success');
                    setStatus(uploadStatus, 'Upload & Ingestion successful!', 'success');
                    sendButton.disabled = false; // Re-enable chat button
                    fileUpload.disabled = false; // Re-enable upload button
                    fileUpload.value = ''; // Clear selected files in the input field
                    pollingIntervalId = null; // Clear the stored interval ID
                    console.log('DEBUG: Polling stopped: COMPLETED'); // Debugging line 17
                } else if (data.status === 'FAILED') {
                    clearInterval(pollingIntervalId); // Stop polling
                    setStatus(ingestionStatus, 'Ingestion failed! Please check server logs for details.', 'error');
                    setStatus(uploadStatus, 'Upload & Ingestion failed!', 'error');
                    sendButton.disabled = false; // Re-enable chat button
                    fileUpload.disabled = false; // Re-enable upload button
                    fileUpload.value = ''; // Clear selected files in the input field
                    pollingIntervalId = null; // Clear the stored interval ID
                    console.log('DEBUG: Polling stopped: FAILED'); // Debugging line 18
                }

            } catch (error) {
                // Catch any errors during the polling process (network issues, API errors)
                console.error('Error during ingestion status polling (caught in startPollingIngestionStatus catch block):', error); // Debugging line 19
                clearInterval(pollingIntervalId); // Stop polling on error
                setStatus(ingestionStatus, `Ingestion status check failed: ${error.message}`, 'error');
                setStatus(uploadStatus, 'Upload & Ingestion failed!', 'error');
                sendButton.disabled = false; // Re-enable chat button
                fileUpload.disabled = false; // Re-enable upload button
                fileUpload.value = ''; // Clear selected files in input
                pollingIntervalId = null; // Clear the stored interval ID
            }
        }, 3000); // Poll every 3 seconds (adjust as needed)
    }

    // --- Event Listeners ---
    // Listen for click on the send button to send a message
    sendButton.addEventListener('click', sendMessage);

    // Listen for keypress events in the user input textarea
    userInput.addEventListener('keypress', (event) => {
        // If 'Enter' key is pressed AND 'Shift' key is NOT pressed, send the message
        if (event.key === 'Enter' && !event.shiftKey) { 
            event.preventDefault(); // Prevent default Enter behavior (new line in textarea)
            sendMessage(); // Call the sendMessage function
        }
    });

    // Listen for input changes in the textarea to auto-resize it
    userInput.addEventListener('input', () => autoResizeTextarea(userInput));

    // Listen for changes in the file input (when user selects files)
    fileUpload.addEventListener('change', handleFileUpload); 
});
