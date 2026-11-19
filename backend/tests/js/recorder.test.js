// Tests for recorder.js — pickMimeType and module initialization.
// Run with: cd backend && node --test tests/js/recorder.test.js
import { test, describe, beforeEach } from "node:test";
import assert from "node:assert";
import { pickMimeType, createRecorder } from "../../app/static/js/recorder.js";

// ---------- pickMimeType ----------

describe("pickMimeType", function () {
  test("returns first supported type when all are supported", () => {
    const fn = (t) => true;
    assert.equal(pickMimeType(fn), "audio/webm;codecs=opus");
  });

  test("returns audio/mp4 when only that is supported", () => {
    const fn = (t) => t === "audio/mp4";
    assert.equal(pickMimeType(fn), "audio/mp4");
  });

  test("returns audio/ogg when only that is supported", () => {
    const fn = (t) => t === "audio/ogg;codecs=opus";
    assert.equal(pickMimeType(fn), "audio/ogg;codecs=opus");
  });

  test("returns empty string when nothing is supported", () => {
    const fn = () => false;
    assert.equal(pickMimeType(fn), "");
  });

  test("returns empty string when isTypeSupported throws", () => {
    const fn = () => { throw new Error("nope"); };
    assert.equal(pickMimeType(fn), "");
  });

  test("returns empty string when isTypeSupported is undefined (Safari)", () => {
    assert.equal(pickMimeType(undefined), "");
  });

  test("returns empty string when isTypeSupported is not a function", () => {
    assert.equal(pickMimeType(null), "");
    assert.equal(pickMimeType(42), "");
  });
});

// ---------- createRecorder (DOM glue) ----------

describe("createRecorder", function () {
  let MediaRecorderMock;
  let capturedStream;
  let capturedMimeType;
  let mediaStream = null;
  let getUserMediaCalled = false;

  function createMockMediaRecorder(stream, options) {
    capturedMimeType = options?.mimeType;
    capturedStream = stream;
    getUserMediaCalled = true;
    let recording = false;

    return {
      mimeType: options?.mimeType,
      state: "inactive",
      ondataavailable: null,
      onstop: null,

      start() {
        recording = true;
        this.state = "recording";
      },

      stop() {
        if (!recording) return;
        recording = false;
        this.state = "inactive";
        if (this.ondataavailable) {
          this.ondataavailable({ data: new Blob(["fake audio data"], { type: this.mimeType }) });
        }
        if (this.onstop) this.onstop();
      },
    };
  }

  function createDomMock() {
    let clickHandler = null;
    const button = {
      textContent: "Record a take",
      addEventListener(event, handler) {
        if (event === "click") clickHandler = handler;
      },
    };
    const elapsed = { textContent: "" };
    const domElement = {
      querySelector: (sel) => {
        if (sel === "[data-action='record']") return button;
        if (sel === "[data-elapsed]") return elapsed;
        return null;
      },
    };

    Object.defineProperty(domElement, "getClickHandler", {
      value: () => clickHandler,
      configurable: true,
    });

    return { domElement, button, elapsed, getClickHandler: () => clickHandler };
  }

  let originalMediaRecorder;
  let mockFetch;
  let fetchCalls = [];

  beforeEach(() => {
    originalMediaRecorder = global.MediaRecorder;

    capturedStream = null;
    capturedMimeType = null;
    mediaStream = null;
    getUserMediaCalled = false;
    fetchCalls = [];

    mockFetch = async (url, init) => {
      fetchCalls.push({ url, init });
      return {
        ok: true,
        json: async () => ({ id: "take-1" }),
      };
    };

    const mockStream = {
      getTracks: () => [{ enabled: true, stop: () => {} }],
    };
    mediaStream = mockStream;

    global.MediaRecorder = createMockMediaRecorder;
    if (!global.navigator.mediaDevices) {
      Object.defineProperty(global.navigator, "mediaDevices", { value: {} });
    }
    global.navigator.mediaDevices.getUserMedia = () =>
      Promise.resolve(mediaStream);
    global.fetch = mockFetch;
  });

  afterEach(() => {
    global.MediaRecorder = originalMediaRecorder;
  });

  test("initializes without error when DOM element provided", () => {
    const { domElement } = createDomMock();
    const recorder = createRecorder({
      element: domElement,
      itemId: 42,
      bpm: 96,
    });
    assert.ok(recorder);
    assert.equal(typeof recorder.start, "function");
    assert.equal(typeof recorder.stop, "function");
  });

  test("calls onStart when recording starts", async () => {
    let onStartCalled = false;
    let onStopCalled = false;
    let onUploadCalled = false;
    let onErrorCalled = false;

    const { domElement, getClickHandler } = createDomMock();
    const recorder = createRecorder({
      element: domElement,
      itemId: 1,
      bpm: 120,
      onStart: () => { onStartCalled = true; },
      onStop: () => { onStopCalled = true; },
      onUpload: () => { onUploadCalled = true; },
      onRecordingError: () => { onErrorCalled = true; },
    });

    // Trigger the record button click
    const click = getClickHandler();
    click();

    // Wait for getUserMedia and MediaRecorder.start to complete
    await new Promise((r) => setTimeout(r, 50));

    assert.ok(onStartCalled, "onStart should be called");
    assert.ok(getUserMediaCalled, "getUserMedia should have been called");
    assert.ok(capturedMimeType, "should create MediaRecorder with a MIME type");
    assert.strictEqual(capturedMimeType, "audio/webm;codecs=opus");
  });

  test("calls onUpload after recording stops", async () => {
    let onUploadCalled = false;

    const { domElement, getClickHandler } = createDomMock();
    const recorder = createRecorder({
      element: domElement,
      itemId: 1,
      bpm: 100,
      onUpload: () => { onUploadCalled = true; },
      onRecordingError: () => {},
    });

    // Start recording
    const startClick = getClickHandler();
    startClick();

    // Wait for getUserMedia and MediaRecorder.start
    await new Promise((r) => setTimeout(r, 50));

    // Now stop it
    recorder.stop();

    // Wait for onstop → upload to complete
    await new Promise((r) => setTimeout(r, 50));

    assert.ok(onUploadCalled, "onUpload should be called after stop");
    assert.ok(fetchCalls.length > 0, "should have made a fetch call");
    assert.ok(fetchCalls[0].url.includes("/api/items/1/takes"), "should upload to correct URL");
  });

  test("uploads FormData with duration, bpm, and session_block_id", async () => {
    const { domElement, getClickHandler } = createDomMock();
    const recorder = createRecorder({
      element: domElement,
      itemId: 7,
      bpm: 78,
      sessionBlockId: "b-42",
      onUpload: () => {},
      onRecordingError: () => {},
    });

    const startClick = getClickHandler();
    startClick();

    // Wait for recording to start
    await new Promise((r) => setTimeout(r, 50));

    recorder.stop();

    // Wait for upload to complete
    await new Promise((r) => setTimeout(r, 100));

    assert.ok(fetchCalls.length > 0);
    const formData = fetchCalls[0].init.body;
    assert.ok(formData instanceof FormData, "should upload FormData");
    assert.equal(formData.get("bpm"), "78");
    assert.equal(formData.get("session_block_id"), "b-42");
    const duration = formData.get("duration_seconds");
    assert.ok(duration !== null && parseInt(duration, 10) >= 0);
  });

  test("sets button text to 'Stop' when recording, back to 'Record a take' when stopped", async () => {
    let onStartCalled = false;
    const { domElement, button, getClickHandler } = createDomMock();
    const recorder = createRecorder({
      element: domElement,
      itemId: 1,
      onStart: () => { onStartCalled = true; },
      onRecordingError: () => {},
    });

    // Start recording
    const startClick = getClickHandler();
    startClick();

    // Wait for recording to start
    await new Promise((r) => setTimeout(r, 50));

    assert.ok(onStartCalled, "recording should have started");
    assert.equal(button.textContent, "Stop", "button should show 'Stop' while recording");

    // Stop recording
    recorder.stop();
    await new Promise((r) => setTimeout(r, 50));

    assert.equal(button.textContent, "Record a take", "button should show 'Record a take' after stop");
  });

  test("shows elapsed time while recording", async () => {
    let timerEl = { textContent: "" };
    const domElement = {
      querySelector: (sel) => {
        if (sel === "[data-action='record']") return {
          textContent: "Record a take",
          addEventListener: (_, handler) => { handler(); },
        };
        if (sel === "[data-elapsed]") return timerEl;
        return null;
      },
    };

    createRecorder({
      element: domElement,
      itemId: 1,
      bpm: 90,
      onRecordingError: () => {},
    });

    // Wait for recording to start and timer to begin
    await new Promise((r) => setTimeout(r, 500));

    assert.ok(timerEl.textContent.length > 0, "elapsed timer should show time");
    assert.ok(/^\d+:\d{2}$/.test(timerEl.textContent), "elapsed time should be in m:ss format");
  });

  test("auto-stops at 600 seconds with onRecordingError fallback when MediaRecorder unavailable", async () => {
    global.MediaRecorder = undefined;
    let onErrorCalled = false;
    let errorText = "";

    const { domElement, getClickHandler } = createDomMock();
    const recorder = createRecorder({
      element: domElement,
      itemId: 1,
      onRecordingError: (msg) => { onErrorCalled = true; errorText = msg; },
    });

    const click = getClickHandler();
    click();

    // Wait for the recording start logic to fail gracefully
    await new Promise((r) => setTimeout(r, 100));

    assert.ok(onErrorCalled, "onRecordingError should be called");
    assert.ok(errorText.length > 0, "should have an error message");
  });

  test("does not throw when MediaRecorder is undefined", () => {
    global.MediaRecorder = undefined;
    const { domElement } = createDomMock();

    assert.doesNotThrow(() => {
      createRecorder({ element: domElement, itemId: 1 });
    });
  });
});
