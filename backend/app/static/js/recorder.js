// Browser recorder: pick the best MIME type, toggle recording, upload takes.
// See docs/frontend.md §js — recorder.js.
// SPEC 8.1-8.2: record button on runner and /items/{id}; auto-stop at 10 min.

export function pickMimeType(isTypeSupported) {
  if (typeof isTypeSupported !== "function") {
    return typeof MediaRecorder !== "undefined" &&
           isTypeSupported("audio/mp4")
      ? "audio/mp4"
      : "";
  }
  for (const t of [
    "audio/webm;codecs=opus",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ]) {
    try {
      if (isTypeSupported(t)) return t;
    } catch (_) { /* some browsers throw on unknown types */ }
  }
  return "";
}

export function createRecorder({ element, itemId, bpm, sessionBlockId, onStart, onStop, onUpload, onRecordingError }) {
  const button = element?.querySelector("[data-action='record']");
  const timerEl = element?.querySelector("[data-elapsed]");

  let mediaRecorder = null;
  let chunks = [];
  let started = false;
  let recordingAt = 0;
  let elapsedId = null;
  let maxTimerId = null;
  let stream = null;

  function stopRecording() {
    if (maxTimerId !== null) {
      clearTimeout(maxTimerId);
      maxTimerId = null;
    }
    if (elapsedId !== null) {
      clearInterval(elapsedId);
      elapsedId = null;
    }
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
  }

  function uploadTake(durationSeconds) {
    const formData = new FormData();
    const blob = new Blob(chunks, { type: mediaRecorder?.mimeType || "audio/webm" });
    formData.append("file", blob, "take.webm");
    formData.append("duration_seconds", String(Math.round(durationSeconds)));
    if (bpm != null) formData.append("bpm", String(bpm));
    if (sessionBlockId != null) formData.append("session_block_id", String(sessionBlockId));

    fetch(`/api/items/${itemId}/takes`, { method: "POST", body: formData })
      .then(function(res) { return res.json(); })
      .then(function(_data) { onUpload(); })
      .catch(function(err) {
        console.error("Take upload failed", err);
        onRecordingError("Upload failed. Please try again.");
      });
  }

  function startRecording() {
    started = true;
    recordingAt = Date.now();
    chunks = [];

    const mimeType = pickMimeType(function(t) {
      return typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t);
    });

    if (!mimeType || typeof MediaRecorder === "undefined") {
      started = false;
      onRecordingError("Recording not supported in this browser.");
      return;
    }

    if (button) {
      button.textContent = "Stop";
    }

    const navigatorMedia = navigator.mediaDevices;
    if (!navigatorMedia?.getUserMedia) {
      started = false;
      onRecordingError("No microphone access.");
      return;
    }

    navigatorMedia.getUserMedia({ audio: true }).then(function(s) {
      if (!started) {
        s.getTracks().forEach(function(t) { t.stop(); });
        return;
      }
      stream = s;

      try {
        mediaRecorder = new MediaRecorder(s, { mimeType: mimeType });
      } catch (_) {
        started = false;
        onRecordingError("Could not create a MediaRecorder.");
        return;
      }

      mediaRecorder.ondataavailable = function(e) {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };
      mediaRecorder.start(1000);

      // Elapsed time display
      elapsedId = setInterval(function() {
        if (timerEl) {
          const elapsed = Math.floor((Date.now() - recordingAt) / 1000);
          const m = Math.floor(elapsed / 60);
          const s = elapsed % 60;
          timerEl.textContent = `${m}:${String(s).padStart(2, "0")}`;
        }
      }, 200);

      // Auto-stop at 10 minutes
      maxTimerId = setTimeout(function() {
        if (started) stopRecording();
      }, 600_000);

      if (onStart) onStart();
    }).catch(function(err) {
      started = false;
      console.error("getUserMedia failed", err);
      onRecordingError("Microphone access denied.");
    });
  }

  function stopRecordingRecording() {
    if (!started) return;
    started = false;

    if (button) {
      button.textContent = "Record a take";
    }

    if (elapsedId !== null) {
      clearInterval(elapsedId);
      elapsedId = null;
    }
    if (maxTimerId !== null) {
      clearTimeout(maxTimerId);
      maxTimerId = null;
    }

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.onstop = function() {
        const duration = (Date.now() - recordingAt) / 1000;
        uploadTake(duration);
      };
      mediaRecorder.stop();
      mediaRecorder = null;
    } else {
      uploadTake((Date.now() - recordingAt) / 1000);
    }

    stopRecording();

    if (timerEl) timerEl.textContent = "";
    if (onStop) onStop();
  }

  button?.addEventListener("click", function() {
    if (started) {
      stopRecordingRecording();
    } else {
      startRecording();
    }
  });

  return {
    start: startRecording,
    stop: stopRecordingRecording,
  };
}
