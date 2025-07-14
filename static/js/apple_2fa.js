
// Apple 2FA functionality
console.log('Apple 2FA module loaded');

let currentSessionId = null;

function show2FAModal() {
    const modal = document.getElementById('twoFactorModal');
    if (modal) {
        modal.style.display = 'block';
        const codeInput = document.getElementById('verificationCode');
        if (codeInput) {
            codeInput.focus();
        }
    }
}

function hide2FAModal() {
    const modal = document.getElementById('twoFactorModal');
    if (modal) {
        modal.style.display = 'none';
        const codeInput = document.getElementById('verificationCode');
        if (codeInput) {
            codeInput.value = '';
        }
    }
}

async function submit2FA() {
    const verificationCode = document.getElementById('verificationCode').value;

    if (!verificationCode || verificationCode.length !== 6) {
        alert('Please enter a valid 6-digit verification code');
        return;
    }

    try {
        const response = await fetch('/api/auth/apple', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                verification_code: verificationCode
            })
        });

        const data = await response.json();

        if (response.ok && !data.requires_2fa) {
            hide2FAModal();
            // Retry the original search
            const searchForm = document.getElementById('searchForm');
            if (searchForm) {
                handleSearch({preventDefault: () => {}});
            }
        } else {
            alert('Invalid verification code. Please try again.');
        }

    } catch (error) {
        console.error('2FA verification error:', error);
        alert('Error verifying code: ' + error.message);
    }
}

function cancel2FA() {
    hide2FAModal();
    currentSessionId = null;
    const resultsDiv = document.getElementById('searchResults');
    if (resultsDiv) {
        resultsDiv.innerHTML = '<p>Search cancelled.</p>';
    }
}

// Allow Enter key in verification code input
document.addEventListener('DOMContentLoaded', function() {
    const codeInput = document.getElementById('verificationCode');
    if (codeInput) {
        codeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                submit2FA();
            }
        });
    }

    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        const modal = document.getElementById('twoFactorModal');
        if (event.target === modal) {
            cancel2FA();
        }
    });
});