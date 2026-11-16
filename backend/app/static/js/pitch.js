// Pure tuner maths module.
// See docs/frontend.md §js and SPEC §13.

/** Standard guitar tuning: [name, nominal frequency in Hz]. */
export const STANDARD = [
  ["E2", 82.41],
  ["A2", 110.0],
  ["D3", 146.83],
  ["G3", 196.0],
  ["B3", 246.94],
  ["E4", 329.63],
];

/**
 * Detect the fundamental frequency (Hz) from a time-domain signal using
 * autocorrelation with parabolic interpolation.
 *
 * @param {Float32Array} samples - input samples
 * @param {number} sampleRate - sample rate in Hz
 * @returns {number|null} frequency in Hz, or null for silence
 */
export function detectPitch(samples, sampleRate) {
  if (!samples || samples.length < 60) return null;
  const n = samples.length;

  // RMS check — silence
  let sumSq = 0;
  for (let i = 0; i < n; i++) sumSq += samples[i] * samples[i];
  const rms = Math.sqrt(sumSq / n);
  if (rms < 0.01) return null;

  const minLag = Math.floor(sampleRate / 1200);
  const maxLag = Math.floor(sampleRate / 60);
  if (maxLag >= n) return null;

  // Autocorrelation: r[l] = sum(s[i] * s[i+l])
  const r = new Float32Array(maxLag + 1);
  for (let l = 0; l <= maxLag; l++) {
    let s = 0;
    for (let i = 0; i < n - l; i++) s += samples[i] * samples[i + l];
    r[l] = s;
  }

  // Find the best lag: highest correlation that is also a local peak
  let bestLag = minLag;
  let bestVal = r[minLag];
  for (let l = minLag + 1; l <= maxLag; l++) {
    if (r[l] > bestVal) {
      bestVal = r[l];
      bestLag = l;
    }
  }

  // Require the best value to be positive
  if (bestVal <= 0) return null;

  // Parabolic interpolation around the peak
  let lag = bestLag;
  if (bestLag > minLag && bestLag < maxLag) {
    const a = r[bestLag - 1];
    const b = r[bestLag];
    const c = r[bestLag + 1];
    const denom = 2 * (2 * b - a - c);
    if (denom !== 0) {
      lag = bestLag + (a - c) / denom;
    }
  } else if (bestLag === minLag && bestLag < maxLag) {
    // Peak at lower boundary — bias upward if the neighbor is higher
    const delta = r[bestLag + 1] - r[bestLag];
    if (delta > 0) {
      lag = bestLag + 0.5;
    }
  }

  if (lag < 1) return null;
  return sampleRate / lag;
}

/**
 * Map a frequency to the nearest musical note.
 *
 * @param {number} freq - frequency in Hz
 * @param {number} a4 - A4 reference frequency (default 440)
 * @returns {{name: string, octave: number, cents: number, midi: number}}
 */
export function noteFor(freq, a4 = 440) {
  const names = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
  ];
  const midi = Math.round(69 + 12 * Math.log2(freq / a4));
  const cents = 1200 * Math.log2(freq / (a4 * Math.pow(2, (midi - 69) / 12)));
  return {
    name: names[((midi % 12) + 12) % 12],
    octave: Math.floor(midi / 12) - 1,
    cents,
    midi,
  };
}

/**
 * Find the index in STANDARD of the string whose nominal frequency is
 * closest to the given frequency.
 *
 * @param {number} freq - frequency in Hz
 * @returns {number} index into STANDARD
 */
export function nearestString(freq) {
  let best = 0;
  let bestDiff = Math.abs(freq - STANDARD[0][1]);
  for (let i = 1; i < STANDARD.length; i++) {
    const diff = Math.abs(freq - STANDARD[i][1]);
    if (diff < bestDiff) {
      best = i;
      bestDiff = diff;
    }
  }
  return best;
}
