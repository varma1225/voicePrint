document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const userIdInput = document.getElementById('userId');
    const loginBtn = document.getElementById('loginBtn');
    const errorMsg = document.getElementById('errorMsg');

    const userId = userIdInput.value.trim();
    if (!userId) return;

    // UI Loading State
    loginBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verifying...';
    loginBtn.disabled = true;
    errorMsg.textContent = "";

    try {
        const response = await fetch('http://localhost:5000/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ user_id: userId })
        });

        const data = await response.json();

        if (response.ok) {
            // Login Success
            sessionStorage.setItem('voice_agent_id', userId);
            window.location.href = 'index.html';
        } else {
            // Login Failed
            throw new Error(data.error || 'Login failed');
        }
    } catch (err) {
        console.error(err);
        errorMsg.textContent = err.message;
        loginBtn.innerHTML = 'Login <i class="fa-solid fa-arrow-right" style="margin-left: 0.5rem"></i>';
        loginBtn.disabled = false;
    }
});
