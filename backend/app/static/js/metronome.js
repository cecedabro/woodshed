// Pure metronome module — scheduling maths.
// See docs/frontend.md §js and SPEC §6.

/**
 * Round and clamp a BPM value to the valid range [20, 400].
 */
export function clampBpm(bpm) {
  return Math.max(20, Math.min(400, Math.round(bpm)));
}

/**
 * Compute beat times for a metronome schedule.
 *
 * @param {number} startTime  - start time in milliseconds
 * @param {number} bpm       - beats per minute
 * @param {number} beatsPerBar - accents every Nth beat
 * @param {number} fromBeat  - first beat index to include
 * @param {number} untilTime - exclusive end time in milliseconds
 * @returns {{time: number, beat: number, accent: boolean}[]}
 */
export function beatTimes(startTime, bpm, beatsPerBar, fromBeat, untilTime) {
  const interval = 60000 / bpm;
  const beats = [];

  for (let k = fromBeat; ; k++) {
    const time = startTime + k * interval;
    if (time >= untilTime) break;

    beats.push({
      time,
      beat: k,
      accent: k % beatsPerBar === 0,
    });
  }

  return beats;
}

/**
 * Compute the average tempo from tap timestamps.
 *
 * Taps more than 2000 ms apart restart the sequence.
 * Uses the last 4 taps (3 intervals). Fewer than 2 taps returns null.
 *
 * @param {number[]} tapsMs - sorted timestamps in milliseconds
 * @returns {number|null}
 */
export function tapTempo(tapsMs) {
  if (tapsMs.length < 2) return null;

  // Filter: restart sequence on gaps > 2000ms
  let filtered = [tapsMs[0]];
  for (let i = 1; i < tapsMs.length; i++) {
    const gap = tapsMs[i] - tapsMs[i - 1];
    if (gap > 2000) {
      filtered = [tapsMs[i]];
    } else {
      filtered.push(tapsMs[i]);
    }
  }

  // Take the last 4 taps
  const lastTaps = filtered.slice(-4);
  if (lastTaps.length < 2) return null;

  // Average interval between consecutive taps
  let totalInterval = 0;
  for (let i = 1; i < lastTaps.length; i++) {
    totalInterval += lastTaps[i] - lastTaps[i - 1];
  }

  const avgInterval = totalInterval / (lastTaps.length - 1);
  const bpm = 60000 / avgInterval;

  return clampBpm(bpm);
}

// --- Metronome class (look-ahead scheduler) ---

/**
 * Metronome class using the standard look-ahead scheduling pattern.
 *
 * A 25 ms setInterval asks beatTimes() for beats in the next 100 ms
 * and schedules short oscillator clicks at the exact audioContext.currentTime
 * values (1000 Hz accent, 800 Hz other beats, 30 ms).
 */
export class Metronome {
  /**
   * @param {AudioContext} audioContext  - real or fake AudioContext
   */
  constructor(audioContext) {
    this._ctx = audioContext;
    this._bpm = 80;
    this._beatsPerBar = 4;
    this._volume = 0.5;
    this._playing = false;
    this._timerId = null;
    this._nextBeatIndex = 0;
    this._startTime = 0;
    this._cue = null; // optional callback for block-end cue
    this._onBeatCb = null;
  }

  /**
   * Register a callback invoked on each scheduled beat.
   * Called with { beat, accent } — use for lighting .beats.
   * @param {{(info: {beat: number, accent: boolean}): void} | null} cb
   */
  onBeat(cb) {
    this._onBeatCb = cb;
  }

  /**
   * Start playing at the given BPM (must not be called while already playing).
   *
   * Stores startTime = ctx.currentTime * 1000 + 50 once; every tick calls
   * beatTimes(startTime, bpm, beatsPerBar, nextBeat, now + 100) with that
   * same startTime, so beat k stays at startTime + k·60000/bpm.
   * @param {number} bpm
   */
  start(bpm) {
    this._bpm = clampBpm(bpm);
    this._playing = true;
    this._nextBeatIndex = 0;
    this._startTime = this._ctx.currentTime * 1000 + 50;
    this._tryResumeContext();
    this._tick();
    this._timerId = setInterval(() => this._tick(), 25);
  }

  /** Stop playing and clear the scheduler interval. */
  stop() {
    this._playing = false;
    if (this._timerId !== null) {
      clearInterval(this._timerId);
      this._timerId = null;
    }
    this._nextBeatIndex = 0;
  }

  /**
   * Change BPM while playing.
   *
   * Restarts the count: new startTime = the time of the next unscheduled beat,
   * nextBeat = 0.
   * @param {number} bpm
   */
  setBpm(bpm) {
    this._bpm = clampBpm(bpm);
    const nowMs = this._ctx.currentTime * 1000;
    const interval = 60000 / this._bpm;
    // Find k where startTime_new + k * interval is just after now
    const k = Math.floor(nowMs / interval);
    this._startTime = nowMs - k * interval;
    this._nextBeatIndex = 0;
  }

  /**
   * Change beats per bar (2–7).
   * @param {number} n
   */
  setBeatsPerBar(n) {
    this._beatsPerBar = Math.max(2, Math.min(7, Math.round(n)));
  }

  /**
   * Set volume (0–1).
   * @param {number} v
   */
  setVolume(v) {
    this._volume = Math.max(0, Math.min(1, v));
  }

  /** Set a cue callback invoked when the metronome plays a block-end cue. */
  setCue(callback) {
    this._cue = callback;
  }

  /**
   * Play a one-shot cue sound (for block transitions).
   */
  playCue() {
    if (this._ctx.state === "closed") return;
    const ctx = this._ctx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.value = this._volume;
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.08);
    if (this._cue) this._cue();
  }

  /**
   * Try to resume the AudioContext (needed for iOS – must be in a user-gesture handler).
   * @private
   */
  _tryResumeContext() {
    const ctx = this._ctx;
    if (ctx.state === "suspended") {
      ctx.resume();
    }
  }

  /**
   * The 25 ms tick – looks ahead and schedules beats.
   * @private
   */
  _tick() {
    if (!this._playing) return;
    const ctx = this._ctx;
    const nowMs = ctx.currentTime * 1000;
    const lookAheadMs = 100;
    const scheduleAheadMs = 50;

    // Generate beats for the next look-ahead window using the fixed startTime
    // so beat k stays at startTime + k·60000/bpm.
    let beats = beatTimes(
      this._startTime,
      this._bpm,
      this._beatsPerBar,
      this._nextBeatIndex,
      nowMs + lookAheadMs
    );

    for (const beat of beats) {
      // Skip beats that are already in the past (can happen after setBpm)
      if (beat.time < nowMs) continue;

      this._scheduleBeat(beat);

      // Notify the onBeat callback
      if (this._onBeatCb) {
        this._onBeatCb({ beat: beat.beat, accent: beat.accent, time: beat.time });
      }
    }

    // Advance the beat index for the next round
    if (beats.length > 0) {
      this._nextBeatIndex = beats[beats.length - 1].beat + 1;
    }
  }

  /**
   * Schedule a single click via AudioContext oscillator.
   * @private
   * @param {{time: number, beat: number, accent: boolean}} beat
   */
  _scheduleBeat(beat) {
    const ctx = this._ctx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    const freq = beat.accent ? 1000 : 800;
    osc.frequency.value = freq;
    gain.gain.value = this._volume;

    // 30 ms click
    const when = beat.time / 1000; // convert to seconds for audioContext.currentTime
    osc.start(when);
    osc.stop(when + 0.03);
  }
}
