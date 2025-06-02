document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginButton = document.getElementById('login-button');
    const loginStatus = document.getElementById('login-status');

    const API_BASE_URL = 'http://127.0.0.1:8000';
    const API_LOGIN_URL = `${API_BASE_URL}/login`;

    // Helper function to set status messages
    function setStatus(element, message, type = 'info') {
        element.textContent = message;
        element.style.display = 'block'; // Ensure it's visible
        element.classList.remove('status-info', 'status-success', 'status-error');

        if (type === 'error') {
            element.classList.add('status-error');
        } else if (type === 'success') {
            element.classList.add('status-success');
        } else { // 'info' or default
            element.classList.add('status-info');
        }
    }

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        const username = usernameInput.value;
        const password = passwordInput.value;

        loginButton.disabled = true;
        setStatus(loginStatus, 'Logging in...', 'info');

        try {
            // Using FormData to send application/x-www-form-urlencoded as expected by FastAPI's OAuth2PasswordRequestForm
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch(API_LOGIN_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: formData.toString(),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            // Store the access token securely (e.g., in localStorage)
            localStorage.setItem('adminAccessToken', data.access_token);
            
            setStatus(loginStatus, 'Login successful! Redirecting to admin panel...', 'success');
            // Redirect to the admin page after successful login
            window.location.href = 'admin.html';

        } catch (error) {
            console.error('Login error:', error);
            setStatus(loginStatus, `Login failed: ${error.message}`, 'error');
        } finally {
            loginButton.disabled = false;
        }
    });
});