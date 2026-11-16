// Pure localStorage persistence for metronome preferences.
// Used by both metronome-page.js and run-page.js.

const VOLUME_KEY = "woodshed_metronome_volume";
const BPM_KEY = "woodshed_metronome_bpm";
const BEATS_KEY = "woodshed_metronome_beats";

const DEFAULTS = { volume: 0.5, bpm: 80, beats: 4 };

const VALID_BEATS = new Set([2, 3, 4, 6]);

/**
 * Load metronome preferences from storage.
 * Falls back to defaults for missing, NaN, or out-of-range values.
 * @param {Storage} storage
 * @returns {{volume: number, bpm: number, beats: number}}
 */
export function loadPrefs(storage) {
  let volume = DEFAULTS.volume;
  let bpm = DEFAULTS.bpm;
  let beats = DEFAULTS.beats;

  try {
    // Volume
    const v = parseFloat(storage.getItem(VOLUME_KEY));
    if (!Number.isNaN(v)) volume = Math.max(0, Math.min(1, v));

    // BPM — clamp to 20–400; fall back if NaN
    const rawBpm = parseInt(storage.getItem(BPM_KEY), 10);
    if (!Number.isNaN(rawBpm)) bpm = Math.max(20, Math.min(400, rawBpm));

    // Beats — fall back if missing / NaN / not in valid set
    const rawBeats = parseInt(storage.getItem(BEATS_KEY), 10);
    if (!Number.isNaN(rawBeats) && VALID_BEATS.has(rawBeats)) beats = rawBeats;
  } catch (_) {
    /* storage unavailable */
  }

  return { volume, bpm, beats };
}

/**
 * Save metronome preferences to storage.
 * @param {Storage} storage
 * @param {{volume: number, bpm: number, beats: number}} prefs
 */
export function savePrefs(storage, prefs) {
  try {
    storage.setItem(VOLUME_KEY, String(prefs.volume));
    storage.setItem(BPM_KEY, String(prefs.bpm));
    storage.setItem(BEATS_KEY, String(prefs.beats));
  } catch (_) {
    /* storage unavailable */
  }
}
