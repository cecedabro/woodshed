// Item detail page glue: wires the record button (SPEC 8.1).

import { createRecorder } from "./recorder.js";

const itemEl = document.querySelector("[data-item-id]");
if (!itemEl) {
  // Page does not render a data-item-id; nothing to do.
} else {
  const itemId = parseInt(itemEl.dataset.itemId, 10);
  const recorderEl = document.querySelector("[data-recorder]");
  if (!recorderEl) {
    // No recorder region rendered in the template.
  } else {
    const timerEl = recorderEl.querySelector("[data-elapsed]");

    createRecorder({
      element: recorderEl,
      itemId: itemId,
      bpm: null,
      sessionBlockId: null,
      onStart: () => {
        if (timerEl) timerEl.hidden = false;
      },
      onStop: () => {
        if (timerEl) timerEl.hidden = true;
      },
      onUpload: () => {
        if (timerEl) timerEl.hidden = true;
      },
      onRecordingError: (msg) => {
        alert(msg);
      },
    });
  }
}
