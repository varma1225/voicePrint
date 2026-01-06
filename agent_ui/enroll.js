let audioContext;
let processor;
let input;
let stream;
let leftChannel = [];
let recordingLength = 0;
let sampleRate = 44100;
let startTime;
const timerDisplay = document.getElementById('recordingTimer');
let timerInterval;
let samplesCollected = 0;
const sampleBadge = document.getElementById('sampleBadge');

const recordBtn = document.getElementById('recordBtn');
const submitEnrollBtn = document.getElementById('submitEnrollBtn');
const enrollUserId = document.getElementById('enrollUserId');
const statusBadge = document.getElementById('statusBadge');
const enrollMsg = document.getElementById('enrollMsg');

recordBtn.addEventListener('mousedown', startRecording);
recordBtn.addEventListener('mouseup', stopRecording);
recordBtn.addEventListener('mouseleave', stopRecording);

// Touch support
recordBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    startRecording();
});
recordBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopRecording();
});

async function startRecording() {
    if (audioContext && audioContext.state === "running") return;

    const userId = enrollUserId.value.trim();
    if (!userId) {
        enrollMsg.textContent = "Please enter an Agent ID first.";
        enrollMsg.style.color = "var(--danger)";
        return;
    }

    try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        sampleRate = audioContext.sampleRate;

        input = audioContext.createMediaStreamSource(stream);
        processor = audioContext.createScriptProcessor(4096, 1, 1);

        leftChannel = [];
        recordingLength = 0;

        processor.onaudioprocess = function (e) {
            leftChannel.push(new Float32Array(e.inputBuffer.getChannelData(0)));
            recordingLength += 4096;
        };

        input.connect(processor);
        processor.connect(audioContext.destination);

        recordBtn.classList.add('recording');
        statusBadge.textContent = "Recording...";
        statusBadge.classList.add('active');

        timerDisplay.style.display = 'block';
        startTime = Date.now();
        timerInterval = setInterval(() => {
            const elapsed = (Date.now() - startTime) / 1000;
            timerDisplay.textContent = elapsed.toFixed(1) + 's';
        }, 100);

    } catch (err) {
        console.error("Error accessing microphone:", err);
        enrollMsg.textContent = "Error accessing microphone. Please check permissions.";
        enrollMsg.style.color = "var(--danger)";
    }
}

function stopRecording() {
    if (audioContext && audioContext.state !== "closed" && audioContext.state !== undefined) {
        if (processor) processor.disconnect();
        if (input) input.disconnect();
        if (stream) stream.getTracks().forEach(track => track.stop());
        audioContext.close();

        recordBtn.classList.remove('recording');
        statusBadge.textContent = "Processing Audio...";
        clearInterval(timerInterval);

        // Flatten the data
        let samples = new Float32Array(recordingLength);
        let offset = 0;
        for (let i = 0; i < leftChannel.length; i++) {
            samples.set(leftChannel[i], offset);
            offset += leftChannel[i].length;
        }

        // Create WAV blob
        const wavBlob = createWavBlob(samples, sampleRate);
        window.lastAudioBlob = wavBlob;

        statusBadge.textContent = "Recording Captured";
        submitEnrollBtn.disabled = false;
    }
}

function createWavBlob(samples, sampleRate) {
    let buffer = new ArrayBuffer(44 + samples.length * 2);
    let view = new DataView(buffer);

    /* RIFF identifier */
    writeString(view, 0, 'RIFF');
    /* file length */
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

    // Write PCM samples
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([view], { type: 'audio/wav' });
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}

submitEnrollBtn.addEventListener('click', async () => {
    const userId = enrollUserId.value.trim();
    if (!window.lastAudioBlob || !userId) return;

    submitEnrollBtn.disabled = true;
    submitEnrollBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enrolling...';
    enrollMsg.textContent = "";

    const formData = new FormData();
    formData.append('audio', window.lastAudioBlob, 'enrollment.wav');
    formData.append('user_id', userId);

    try {
        const response = await fetch('http://localhost:5000/enroll', {
            method: 'POST',
            body: formData
        });

        // Check if response is JSON
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            const data = await response.json();
            if (response.ok) {
                enrollMsg.textContent = "✅ " + data.message;
                enrollMsg.style.color = "var(--success)";

                // Track samples in session
                samplesCollected++;
                sampleBadge.textContent = `Samples: ${samplesCollected}/3`;
                sampleBadge.style.display = 'inline-block';

                if (samplesCollected >= 3) {
                    enrollMsg.textContent = "✅ Profile Robust! Redirecting...";
                    setTimeout(() => {
                        window.location.href = 'login.html';
                    }, 2000);
                } else {
                    statusBadge.textContent = "Ready for Next Sample";
                    statusBadge.classList.remove('active');
                    submitEnrollBtn.textContent = "Complete Enrollment";
                    submitEnrollBtn.disabled = true;
                }
            } else {
                throw new Error(data.error || "Enrollment failed");
            }
        } else {
            // Probably an HTML error page
            const text = await response.text();
            console.error("Server returned non-JSON:", text);
            throw new Error("Server error. Please check server logs.");
        }
    } catch (err) {
        console.error(err);
        enrollMsg.textContent = "❌ " + err.message;
        enrollMsg.style.color = "var(--danger)";
        submitEnrollBtn.disabled = false;
        submitEnrollBtn.textContent = "Complete Enrollment";
    }
});
