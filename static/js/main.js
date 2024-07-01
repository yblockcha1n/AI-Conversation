const recordButton = document.getElementById("recordButton");
const resetButton = document.getElementById("resetButton");
const transcriptDiv = document.getElementById("transcript");
const responseDiv = document.getElementById("response");
const audioPlayer = document.getElementById("audioPlayer");
const statusDiv = document.getElementById("status");

let mediaRecorder;
let recordedChunks = [];
let isRecording = false;
let conversationHappened = false;

recordButton.addEventListener("click", toggleRecording);
resetButton.addEventListener("click", resetConversation);

function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

function startRecording() {
    recordedChunks = [];
    isRecording = true;
    recordButton.classList.add("recording");
    statusDiv.textContent = "録音中...";
    resetButton.disabled = true;

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.start();

            mediaRecorder.addEventListener("dataavailable", event => {
                recordedChunks.push(event.data);
            });

            mediaRecorder.addEventListener("stop", handleRecordingStop);
        });
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        isRecording = false;
        recordButton.classList.remove("recording");
        statusDiv.textContent = "処理中...";
        recordButton.disabled = true;
    }
}

function handleRecordingStop() {
    const audioBlob = new Blob(recordedChunks, { type: "audio/mp3" });
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.mp3");

    fetch("/transcribe", {
        method: "POST",
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw err; });
        }
        return response.json();
    })
    .then(data => {
        transcriptDiv.textContent = data.transcript;
        responseDiv.textContent = data.response;
        audioPlayer.src = data.audio_url;
        audioPlayer.play();
        statusDiv.textContent = "AI応答再生中...";
        conversationHappened = true;
        resetButton.disabled = false;

        audioPlayer.addEventListener("ended", () => {
            statusDiv.textContent = "";
            recordButton.disabled = false;
            setTimeout(() => {
                fetch("/delete_audio", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ audio_url: data.audio_url })
                });
            }, 1000);
        });
    })
    .catch(error => {
        console.error('Error:', error);
        statusDiv.textContent = error.error || "エラーが発生しました。もう一度お試しください。";
        recordButton.disabled = false;
        resetButton.disabled = !conversationHappened;
    });
}

function resetConversation() {
    fetch("/reset_conversation", {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === "success") {
            transcriptDiv.textContent = "";
            responseDiv.textContent = "";
            statusDiv.textContent = "会話がリセットされました。";
            setTimeout(() => {
                statusDiv.textContent = "";
            }, 3000);
            conversationHappened = false;
            resetButton.disabled = true;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        statusDiv.textContent = "リセット中にエラーが発生しました。";
    });
}

audioPlayer.addEventListener("play", () => {
    recordButton.disabled = true;
});

audioPlayer.addEventListener("ended", () => {
    recordButton.disabled = false;
});
