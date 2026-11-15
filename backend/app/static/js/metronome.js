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
