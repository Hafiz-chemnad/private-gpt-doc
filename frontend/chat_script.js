document.addEventListener('DOMContentLoaded', () => {
    // Get references to all necessary HTML elements for the chat interface
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const chatWindow = document.getElementById('chat-window');
    const queryStatus = document.getElementById('query-status');
    const loadingIndicator = document.getElementById('loading-indicator'); // New!
    const sourcesSidebar = document.getElementById('sources-sidebar'); // New!
    const sourcesList = document.getElementById('sources-list');       // New!
    const newChatButton = document.getElementById('new-chat-button'); // New!
    const clearChatButton = document.getElementById('clear-chat-button'); // New!
    const toggleSourcesButton = document.getElementById('toggle-sources-button'); // New!

    // Define API endpoints. Ensure API_BASE_URL matches your FastAPI server's address.
    const API_BASE_URL = 'http://127.0.0.1:8000';
    const API_QUERY_URL = `${API_BASE_URL}/query`;

    // --- Helper Functions (specific to chat or generic) ---

    /**
     * Appends a new message (user or bot) to the chat window.
     * @param {string} sender - 'user' or 'bot'.
     * @param {string} text - The message content to display.
     * @param {Array<Object>} sources - Optional array of source documents (for bot messages).
     * @param {boolean} isInitial - True if it's the very first message.
     */
    function appendMessage(sender, text, sources = [], isInitial = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', `${sender}-message`);
        if (isInitial) {
            messageDiv.classList.add('initial-message');
        }
        messageDiv.innerHTML = `<p>${text}</p>`;

        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight; // Auto-scroll to the latest message

        // Handle source documents display in the dedicated sidebar
        if (sender === 'bot' && sources.length > 0) {
            displaySourcesInSidebar(sources);
        } else if (sender === 'user' && !isInitial) {
            // Clear sources when user sends a new message (or just keep old ones if preferred)
            clearSourcesSidebar();
        }
    }

    /**
     * Displays source documents in the dedicated sources sidebar.
     * @param {Array<Object>} sources - Array of source documents.
     */
    function displaySourcesInSidebar(sources) {
        sourcesList.innerHTML = ''; // Clear previous sources
        if (sources.length === 0) {
            sourcesList.innerHTML = '<p class="no-sources-message">No specific source documents found for this query.</p>';
            return;
        }

        sources.forEach(source => {
            const sourceItem = document.createElement('div');
            sourceItem.classList.add('source-item');

            const sourcePath = source.metadata && source.metadata.source ? source.metadata.source : 'Unknown Source';
            const sourceFilename = sourcePath.split(/[\\/]/).pop(); // Handles both Unix (/) and Windows (\) paths
            
            const contentSnippet = source.page_content ?
                source.page_content.substring(0, Math.min(source.page_content.length, 250)) + (source.page_content.length > 250 ? '...' : '')
                : 'No content snippet available.';
            
            sourceItem.innerHTML = `<h4>${sourceFilename}</h4><p>${contentSnippet}</p>`;
            sourcesList.appendChild(sourceItem);
        });
    }

    /**
     * Clears the sources sidebar.
     */
    function clearSourcesSidebar() {
        sourcesList.innerHTML = '<p class="no-sources-message">Sources for the AI\'s answer will appear here.</p>';
    }

    /**
     * Shows or hides the loading indicator.
     * @param {boolean} show - True to show, false to hide.
     */
    function showLoadingIndicator(show) {
        loadingIndicator.style.display = show ? 'flex' : 'none'; // Use flex to center spinner
        if (show) {
            chatWindow.scrollTop = chatWindow.scrollHeight; // Scroll to show indicator
        }
    }

    /**
     * Sets a status message in a given HTML element, with optional styling for type.
     * @param {HTMLElement} element - The DOM element to update (e.g., queryStatus).
     * @param {string} message - The text message to display.
     * @param {'info'|'success'|'error'|'clear'} type - Type of message for styling or clearing.
     */
    function setStatus(element, message, type = 'info') {
        element.textContent = message;
        element.style.color = ''; // Reset color first
        element.style.backgroundColor = ''; // Reset background

        // Clear existing classes that might set colors
        element.classList.remove('status-info', 'status-success', 'status-error');

        if (type === 'clear') {
            element.textContent = '';
        } else if (type === 'error') {
            element.classList.add('status-error'); // Use classes for styling
        } else if (type === 'success') {
            element.classList.add('status-success');
        } else { // 'info' or default
            element.classList.add('status-info');
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

        sendButton.disabled = true; // Disable send button
        showLoadingIndicator(true); // Show loading indicator
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

            if (data.error) {
                appendMessage('bot', `Error: ${data.error}`);
                setStatus(queryStatus, `Error: ${data.error}`, 'error');
            } else {
                appendMessage('bot', data.answer, data.source_documents); // Display bot's answer and sources
                setStatus(queryStatus, 'Response generated.', 'success');
            }

        } catch (error) {
            console.error('Error fetching data:', error);
            appendMessage('bot', `An error occurred: ${error.message}. Please check the server logs.`);
            setStatus(queryStatus, `Error: ${error.message}`, 'error');
        } finally {
            sendButton.disabled = false; // Re-enable send button
            showLoadingIndicator(false); // Hide loading indicator
            userInput.focus(); // Set focus back to the input field
        }
    }

    // --- New Action Button Logic ---
    function startNewChat() {
        chatWindow.innerHTML = `
            <div class="message bot-message initial-message">
                <p>Hello! I'm your PrivateGPT assistant. Please ask me questions.</p>
            </div>
            <div class="loading-indicator" id="loading-indicator" style="display: none;">
                <i class="fas fa-spinner fa-spin"></i> Thinking...
            </div>
        `;
        // Re-get reference to the loading indicator as innerHTML replaces it
        // This is a simple approach. For more complex apps, consider not replacing the entire innerHTML.
        document.getElementById('loading-indicator').style.display = 'none'; // Ensure it's hidden
        
        clearSourcesSidebar();
        setStatus(queryStatus, '', 'clear'); // Clear status message
        userInput.value = '';
        autoResizeTextarea(userInput);
        userInput.focus();
        chatWindow.scrollTop = chatWindow.scrollHeight; // Scroll to top for new chat
    }

    function clearAllChatHistory() {
        if (confirm("Are you sure you want to clear the entire chat history? This cannot be undone.")) {
            chatWindow.innerHTML = `
                <div class="message bot-message initial-message">
                    <p>Chat history cleared. Hello! I'm your PrivateGPT assistant. Please ask me questions.</p>
                </div>
                <div class="loading-indicator" id="loading-indicator" style="display: none;">
                    <i class="fas fa-spinner fa-spin"></i> Thinking...
                </div>
            `;
            document.getElementById('loading-indicator').style.display = 'none';
            clearSourcesSidebar();
            setStatus(queryStatus, 'Chat history cleared.', 'info');
            userInput.value = '';
            autoResizeTextarea(userInput);
            userInput.focus();
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }
    }

    function toggleSourcesSidebar() {
        sourcesSidebar.classList.toggle('collapsed');
        // Optionally, you might change the icon here if it's not handled by CSS transforms
    }

    // --- Event Listeners ---
    sendButton.addEventListener('click', sendMessage);

    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) { 
            event.preventDefault();
            sendMessage();
        }
    });

    userInput.addEventListener('input', () => autoResizeTextarea(userInput));

    // New action button event listeners
    newChatButton.addEventListener('click', startNewChat);
    clearChatButton.addEventListener('click', clearAllChatHistory); // Added functionality for "Clear All" on the frontend
    toggleSourcesButton.addEventListener('click', toggleSourcesSidebar);

    // Initial setup: ensure loading indicator is hidden
    showLoadingIndicator(false);
});