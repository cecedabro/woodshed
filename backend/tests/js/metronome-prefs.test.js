// Tests for metronome-prefs.js — loadPrefs and savePrefs pure functions.
// Run with: cd backend && node --test tests/js/metronome-prefs.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPrefs, savePrefs } from "../../app/static/js/metronome-prefs.js";

// --- Fake storage ---

function createStorage() {
  const store = {};
  return {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null;
    },
    setItem(key, value) {
      store[key] = String(value);
    },
  };
}

// --- loadPrefs: defaults when empty ---

test("loadPrefs returns defaults when storage is empty", () => {
  const storage = createStorage();
  const prefs = loadPrefs(storage);
  assert.equal(prefs.volume, 0.5);
  assert.equal(prefs.bpm, 80);
  assert.equal(prefs.beats, 4);
});

// --- loadPrefs: round trip ---

test("loadPrefs round trip — stores and restores volume, bpm, beats", () => {
  const storage = createStorage();
  savePrefs(storage, { volume: 0.8, bpm: 120, beats: 3 });
  const prefs = loadPrefs(storage);
  assert.equal(prefs.volume, 0.8);
  assert.equal(prefs.bpm, 120);
  assert.equal(prefs.beats, 3);
});

// --- loadPrefs: bad volume falls back ---

test("loadPrefs invalid volume falls back to 0.5", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_volume", "abc");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.volume, 0.5);
});

test("loadPrefs volume 1.5 clamps to 1", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_volume", "1.5");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.volume, 1);
});

test("loadPrefs volume -0.2 clamps to 0", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_volume", "-0.2");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.volume, 0);
});

// --- loadPrefs: bad BPM falls back / clamps ---

test("loadPrefs 'abc' BPM falls back to 80", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_bpm", "abc");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.bpm, 80);
});

test("loadPrefs 999 BPM clamps to 400", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_bpm", "999");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.bpm, 400);
});

test("loadPrefs -10 BPM clamps to 20", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_bpm", "-10");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.bpm, 20);
});

test("loadPrefs NaN BPM falls back to 80", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_bpm", "NaN");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.bpm, 80);
});

// --- loadPrefs: beats validation ---

test("loadPrefs beats 5 falls back to 4", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_beats", "5");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.beats, 4);
});

test("loadPrefs beats 0 falls back to 4", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_beats", "0");
  const prefs = loadPrefs(storage);
  assert.equal(prefs.beats, 4);
});

test("loadPrefs accepts valid beats values 2, 3, 4, 6", () => {
  const storage = createStorage();
  storage.setItem("woodshed_metronome_beats", "6");
  assert.equal(loadPrefs(storage).beats, 6);

  storage.setItem("woodshed_metronome_beats", "3");
  assert.equal(loadPrefs(storage).beats, 3);

  storage.setItem("woodshed_metronome_beats", "2");
  assert.equal(loadPrefs(storage).beats, 2);
});

// --- savePrefs ---

test("savePrefs writes all three keys as strings", () => {
  const storage = createStorage();
  savePrefs(storage, { volume: 0.3, bpm: 100, beats: 2 });
  assert.equal(storage.getItem("woodshed_metronome_volume"), "0.3");
  assert.equal(storage.getItem("woodshed_metronome_bpm"), "100");
  assert.equal(storage.getItem("woodshed_metronome_beats"), "2");
});
