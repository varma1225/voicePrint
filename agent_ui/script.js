document.addEventListener('DOMContentLoaded', () => {
    // 🔒 AUTH CHECK
    const currentUserId = sessionStorage.getItem('voice_agent_id');
    if (!currentUserId) {
        window.location.replace('login.html');
        return;
    }

    // Update Agent UI info
    document.querySelector('.agent-profile .name').textContent = currentUserId;
    document.querySelector('.agent-profile img').src = `https://ui-avatars.com/api/?name=${currentUserId}&background=random`;

    // ROBUST LOGOUT LOGIC (Event Delegation)
    document.body.addEventListener('click', (e) => {
        // Check if clicked element is the logout button or inside it
        const btn = e.target.closest('#sidebarLogoutBtn');

        if (btn) {
            console.log("Logout Clicked (via delegation)");
            e.preventDefault();
            e.stopPropagation();

            sessionStorage.removeItem('voice_agent_id');
            window.location.replace('login.html');
        }
    });

    const simulateBtn = document.getElementById('simulateCallBtn');
    const idleState = document.getElementById('idleState');
    const incomingCallState = document.getElementById('incomingCallState');
    const activeCallState = document.getElementById('activeCallState');

    const declineBtn = document.getElementById('declineBtn');
    const answerBtn = document.getElementById('answerBtn');
    const hangupBtn = document.getElementById('hangupBtn');

    const customerDetails = document.getElementById('customerDetails');
    const infoPlaceholder = document.getElementById('infoPlaceholder');
    const verificationBadge = document.getElementById('verificationBadge');

    const verificationStatus = document.getElementById('verificationStatus');
    const statusText = verificationStatus.querySelector('.status-text');
    const progressBar = document.getElementById('verifyProgressBar');
    const verificationResult = document.getElementById('verificationResult');

    // Audio context for sound effects (optional expansion)

    // State
    let callTimerInterval;
    let verificationTimeout;

    // Simulation: Incoming Call
    simulateBtn.addEventListener('click', () => {
        idleState.classList.add('hidden');
        incomingCallState.classList.remove('hidden');
    });

    // Action: Decline Call
    declineBtn.addEventListener('click', resetToIdle);

    // Action: Answer Call
    answerBtn.addEventListener('click', () => {
        incomingCallState.classList.add('hidden');
        activeCallState.classList.remove('hidden');

        // Show customer info
        infoPlaceholder.classList.add('hidden');
        customerDetails.classList.remove('hidden');

        // Start call timer
        startCallTimer();

        // Start Recording instead of Simulation
        startRecording();
    });

    // Action: Hang Up
    hangupBtn.addEventListener('click', resetToIdle);

    function resetToIdle() {
        // Reset Views
        incomingCallState.classList.add('hidden');
        activeCallState.classList.add('hidden');
        idleState.classList.remove('hidden');

        // Reset Info Panel
        customerDetails.classList.add('hidden');
        infoPlaceholder.classList.remove('hidden');
        verificationBadge.className = 'badge';
        verificationBadge.textContent = 'Unverified';

        // Reset Verification Status
        statusText.textContent = 'Waiting for voice input...';
        progressBar.style.width = '0%';
        verificationResult.className = 'verification-result hidden';
        verificationResult.innerHTML = '';

        // Stop Timers
        clearInterval(callTimerInterval);
        clearTimeout(verificationTimeout);
        document.getElementById('callTimer').textContent = '00:00';
    }

    function startCallTimer() {
        let seconds = 0;
        const timerElement = document.getElementById('callTimer');

        callTimerInterval = setInterval(() => {
            seconds++;
            const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
            const secs = (seconds % 60).toString().padStart(2, '0');
            timerElement.textContent = `${mins}:${secs}`;
        }, 1000);
    }

    function startRecording() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert("Microphone not supported in this browser.");
            return;
        }

        statusText.textContent = "🎙️ Recording voice for verification...";
        verificationBadge.textContent = "Recording";
        verificationBadge.className = "badge";

        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                const source = audioContext.createMediaStreamSource(stream);
                const processor = audioContext.createScriptProcessor(4096, 1, 1);

                const samples = [];

                source.connect(processor);
                processor.connect(audioContext.destination);

                processor.onaudioprocess = function (e) {
                    const inputData = e.inputBuffer.getChannelData(0);
                    for (let i = 0; i < inputData.length; i++) {
                        samples.push(inputData[i]);
                    }
                };

                // Visual progress
                let progress = 0;
                const recordTime = 7000;
                const intervalTime = 100;
                const step = 100 / (recordTime / intervalTime);

                const progressInterval = setInterval(() => {
                    progress += step;
                    if (progress >= 100) progress = 100;
                    progressBar.style.width = `${progress}%`;
                }, intervalTime);

                // Stop recording after time
                setTimeout(() => {
                    source.disconnect();
                    processor.disconnect();
                    clearInterval(progressInterval);

                    // Stop tracks
                    stream.getTracks().forEach(track => track.stop());

                    // Enhance: Encode to WAV
                    const wavBlob = encodeWAV(samples, audioContext.sampleRate);
                    uploadAudio(wavBlob);

                    statusText.textContent = "Processing audio...";
                }, recordTime);

            })
            .catch(err => {
                console.error("Error accessing microphone:", err);
                statusText.textContent = "❌ Microphone access denied";
                verificationBadge.textContent = "Error";
                verificationBadge.classList.add("failed");
            });
    }

    function encodeWAV(samples, sampleRate) {
        const buffer = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buffer);

        /* RIFF identifier */
        writeString(view, 0, 'RIFF');
        /* RIFF chunk length */
        view.setUint32(4, 36 + samples.length * 2, true);
        /* RIFF type */
        writeString(view, 8, 'WAVE');
        /* format chunk identifier */
        writeString(view, 12, 'fmt ');
        /* format chunk length */
        view.setUint32(16, 16, true);
        /* sample format (raw) */
        view.setUint16(20, 1, true);
        /* channel count */
        view.setUint16(22, 1, true);
        /* sample rate */
        view.setUint32(24, sampleRate, true);
        /* byte rate (sample rate * block align) */
        view.setUint32(28, sampleRate * 2, true);
        /* block align (channel count * bytes per sample) */
        view.setUint16(32, 2, true);
        /* bits per sample */
        view.setUint16(34, 16, true);
        /* data chunk identifier */
        writeString(view, 36, 'data');
        /* data chunk length */
        view.setUint32(40, samples.length * 2, true);

        floatTo16BitPCM(view, 44, samples);

        return new Blob([view], { type: 'audio/wav' });
    }

    function floatTo16BitPCM(output, offset, input) {
        for (let i = 0; i < input.length; i++, offset += 2) {
            let s = Math.max(-1, Math.min(1, input[i]));
            output.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }
    }

    function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    function uploadAudio(blob) {
        statusText.textContent = "📤 Sending to VoiceShield Server...";

        const formData = new FormData();
        formData.append("audio", blob, "recording.wav");

        // Add User ID for verification
        const userId = sessionStorage.getItem('voice_agent_id');
        if (userId) {
            formData.append("user_id", userId);
        } else {
            console.warn("No User ID found in session");
        }

        fetch('http://localhost:5000/upload', {
            method: 'POST',
            body: formData
        })
            .then(response => {
                if (response.ok) {
                    statusText.textContent = "✅ Audio sent for verification";
                    verificationResult.innerHTML = '<i class="fa-solid fa-clock"></i> Waiting for analysis...';
                    verificationResult.className = "verification-result";
                    verificationResult.classList.remove('hidden');

                    // Poll for result
                    pollStatus();
                } else {
                    throw new Error("Upload failed");
                }
            })
            .catch(error => {
                console.error("Upload error:", error);
                statusText.textContent = "❌ Upload Failed";
                verificationResult.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Server Error';
                verificationResult.className = "verification-result error";
                verificationResult.classList.remove('hidden');
            });
    }

    function pollStatus() {
        let attempts = 0;
        const maxAttempts = 20; // 20 seconds timeout

        const interval = setInterval(() => {
            attempts++;
            if (attempts > maxAttempts) {
                clearInterval(interval);
                statusText.textContent = "⚠️ Verification Timeout";
                return;
            }

            fetch('http://localhost:5000/check_status')
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'verified') {
                        clearInterval(interval);
                        statusText.textContent = "Verification Complete";
                        verificationResult.innerHTML = `<i class="fa-solid fa-check-circle"></i> Identity Verified (${Math.round(data.similarity * 100)}%)`;
                        verificationResult.className = "verification-result success";
                        verificationBadge.textContent = "Verified";
                        verificationBadge.className = "badge verified";
                    } else if (data.status === 'failed') {
                        clearInterval(interval);
                        statusText.textContent = "Verification Failed";
                        verificationResult.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Identity Mismatch (${Math.round(data.similarity * 100)}%)`;
                        verificationResult.className = "verification-result error";
                        verificationBadge.textContent = "Failed";
                        verificationBadge.className = "badge failed";

                        // SILENT AUTO HANGUP
                        setTimeout(() => {
                            console.log("Auto-terminating call due to verification failure");
                            hangupBtn.click();
                        }, 2000);
                    }
                })
                .catch(err => console.error("Polling error:", err));
        }, 1000);
    }
});
