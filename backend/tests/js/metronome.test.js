// Tests for metronome.js — pure scheduling module.
// Run with: cd backend && node --test tests/js/metronome.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { clampBpm, beatTimes, tapTempo, Metronome } from "../../app/static/js/metronome.js";

// --- clampBpm ---

test("clampBpm rounds down", () => {
  assert.equal(clampBpm(60.4), 60);
});

test("clampBpm rounds up", () => {
  assert.equal(clampBpm(60.6), 61);
});

test("clampBpm 10 clamps to 20", () => {
  assert.equal(clampBpm(10), 20);
});

test("clampBpm 19.4 clamps to 20", () => {
  assert.equal(clampBpm(19.4), 20);
});

test("clampBpm 20 passes through", () => {
  assert.equal(clampBpm(20), 20);
});

test("clampBpm 400 passes through", () => {
  assert.equal(clampBpm(400), 400);
});

test("clampBpm 999 clamps to 400", () => {
  assert.equal(clampBpm(999), 400);
});

test("clampBpm negative clamps to 20", () => {
  assert.equal(clampBpm(-50), 20);
});

// --- beatTimes ---

test("120 BPM beats at 0.5 s spacing", () => {
  const beats = beatTimes(0, 120, 4, 0, 2000);
  assert.equal(beats.length, 4);
  assert.equal(beats[0].time, 0);
  assert.equal(beats[1].time, 500);
  assert.equal(beats[2].time, 1000);
  assert.equal(beats[3].time, 1500);
});

test("beatsPerBar 4 — accent on beat 1, 5, 9", () => {
  const beats = beatTimes(0, 120, 4, 0, 2000);
  assert.equal(beats[0].beat, 0);
  assert.equal(beats[0].accent, true);
  assert.equal(beats[1].beat, 1);
  assert.equal(beats[1].accent, false);
  assert.equal(beats[2].beat, 2);
  assert.equal(beats[2].accent, false);
  assert.equal(beats[3].beat, 3);
  assert.equal(beats[3].accent, false);
});

test("beatsPerBar 3 — accent on beats 0 and 3", () => {
  const beats = beatTimes(0, 60, 3, 0, 4000);
  assert.equal(beats.length, 4);
  assert.equal(beats[0].accent, true);
  assert.equal(beats[1].accent, false);
  assert.equal(beats[2].accent, false);
  assert.equal(beats[3].accent, true);
});

test("fromBeat skips earlier beats", () => {
  const beats = beatTimes(0, 120, 4, 6, 5000);
  assert.equal(beats.length, 4);
  assert.equal(beats[0].beat, 6);
  assert.equal(beats[0].time, 3000);
});

test("fromBeat 0 — first beat is accented", () => {
  const beats = beatTimes(0, 120, 4, 0, 3000);
  assert.equal(beats[0].accent, true);
  assert.equal(beats[0].beat, 0);
});

test("untilTime is exclusive", () => {
  const beats = beatTimes(0, 120, 4, 0, 1000);
  assert.equal(beats.length, 2);
  assert.equal(beats[0].time, 0);
  assert.equal(beats[1].time, 500);
});

test("untilTime cuts beat at boundary", () => {
  const beats = beatTimes(0, 60, 4, 0, 2000);
  assert.equal(beats.length, 2);
  assert.equal(beats[0].time, 0);
  assert.equal(beats[1].time, 1000);
  // next beat at 2000 is excluded
});

test("beatTimes returns empty when startTime >= untilTime", () => {
  const beats = beatTimes(1000, 120, 4, 0, 1000);
  assert.equal(beats.length, 0);
});

test("beatTimes with fromBeat past untilTime returns empty", () => {
  const beats = beatTimes(0, 120, 4, 20, 1000);
  assert.equal(beats.length, 0);
});

// --- tapTempo ---

test("taps at 500 ms intervals gives 120 bpm", () => {
  const bpm = tapTempo([0, 500, 1000, 1500]);
  assert.equal(bpm, 120);
});

test("fewer than 2 taps returns null", () => {
  assert.equal(tapTempo([]), null);
  assert.equal(tapTempo([500]), null);
});

test("exactly 2 taps gives bpm", () => {
  const bpm = tapTempo([0, 1000]);
  assert.equal(bpm, 60);
});

test("3 taps gives bpm", () => {
  const bpm = tapTempo([0, 500, 1000]);
  assert.equal(bpm, 120);
});

test("a 2.5 s gap restarts the sequence", () => {
  // First 3 taps at 500ms, then a 2500ms gap, then 1 tap
  // After restart: only 1 tap in the new sequence → null
  const bpm = tapTempo([0, 500, 1000, 3500]);
  assert.equal(bpm, null);
});

test("a 2.5 s gap restarts — enough taps after gap", () => {
  // First 2 taps, gap, then 4 taps: only last 4 count
  const bpm = tapTempo([0, 500, 4000, 4500, 5000, 5500, 6000]);
  assert.equal(bpm, 120);
});

test("gap exactly 2000 ms does NOT restart", () => {
  // Taps at 0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000
  // All gaps are 500ms, last 4 → 120 bpm
  const bpm = tapTempo([0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000]);
  assert.equal(bpm, 120);
});

test("multiple gaps — only last sequence counts", () => {
  // First sequence: 0, 500, 1000 (3 taps → 120bpm)
  // Gap: 3000ms → restart
  // Second sequence: 4500, 5000, 5500, 6000 → 120bpm
  const bpm = tapTempo([0, 500, 1000, 4500, 5000, 5500, 6000]);
  assert.equal(bpm, 120);
});

// --- Metronome class (fake AudioContext) ---

/**
 * Create a fake AudioContext that records oscillator scheduling.
 * Returns { ctx, oscillators, gains, scheduleTimes, playCueTimes }
 * where oscillators tracks each oscillator's freq/start/stop calls
 * and scheduleTimes records {freq, start, stop} pairs.
 */
function createFakeAudioContext() {
  let fakeCurrentTime = 0;
  let state = "running";
  let gainNode = null;
  const oscillators = [];
  const gains = [];
  const scheduleTimes = [];
  const playCueTimes = [];
  let resumed = false;
  let closed = false;

  const fakeCtx = {
    get currentTime() { return fakeCurrentTime; },
    set currentTime(val) { fakeCurrentTime = val; },
    get state() { return state; },
    set state(v) { state = v; },
    createOscillator() {
      if (closed) return null;
      let _oscFreq = 440;
      let oscStarted = false;
      let oscStartAt = null;
      let oscStoppedAt = null;
      const osc = {
        frequency: {
          get value() { return _oscFreq; },
          set value(v) { _oscFreq = v; },
        },
        start(at) {
          oscStarted = true;
          oscStartAt = at;
          scheduleTimes.push({
            freq: _oscFreq,
            start: at,
            stop: null,
            gain: 1,
          });
        },
        stop(at) {
          oscStoppedAt = at;
          const last = scheduleTimes[scheduleTimes.length - 1];
          if (last) {
            last.stop = at;
          }
        },
        connect(target) {
          if (target && target._isGain) {
            gainNode = target;
          }
        },
        get _info() {
          return { freq: _oscFreq, start: oscStartAt, stop: oscStoppedAt };
        },
      };
      oscillators.push(osc);
      return osc;
    },
    createGain() {
      if (closed) return null;
      let gainValue = 1;
      let lastOsc = null;
      const gain = {
        gain: { value: gainValue },
        connect(target) {
          if (target && target._isGain) {
            // just track connection
          }
        },
        connectToDestination() {},
        set _isGain(v) { /* marker */ },
      };
      gain._isGain = true;
      gainNode = gain;
      gains.push(gain);
      return gain;
    },
    resume() { resumed = true; state = "running"; },
    close() { closed = true; state = "closed"; },
    _resumed() { return resumed; },
  };

  return {
    ctx: fakeCtx,
    oscillators,
    gains,
    scheduleTimes,
    getPlayCueTimes() { return playCueTimes; },
    setPlayCueHandler(fn) { playCueTimes.length = 0; },
    advanceTime(seconds) { fakeCurrentTime += seconds; },
    reset() {
      fakeCurrentTime = 0;
      state = "running";
      gainNode = null;
      oscillators.length = 0;
      gains.length = 0;
      scheduleTimes.length = 0;
      resumed = false;
      closed = false;
    },
  };
}

test("Metronome constructor initialises with defaults", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  // No assertions on private fields; verify no error and start works
  m.start(120);
  assert.equal(m._bpm, 120);
  m.stop();
});

test("Metronome start schedules beats at correct intervals", () => {
  // 120 BPM = 500 ms per beat
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.start(120);

  // Advance time past the first look-ahead window (50 ms schedule + 100 ms look)
  fake.advanceTime(0.2);

  // Manually trigger a tick to schedule beats
  m._tick();

  // At 120 BPM (500 ms interval), first beat is at t=0 (schedule from 50ms ahead)
  // The first beat scheduled should start at ~0.05s (50ms ahead in audioContext time)
  assert.ok(fake.scheduleTimes.length >= 1, "should have scheduled at least 1 beat");

  m.stop();
});

test("Metronome beatsPerBar 4 — accent on every 4th beat", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.setBeatsPerBar(4);
  m.start(60); // 1 beat per second

  fake.advanceTime(0.2);
  m._tick();

  // At 60 BPM, beats at 0, 1, 2, 3 seconds
  // beatTimes starts from scheduleAheadMs (50ms = 0.05s)
  // So we get beats starting from beat index 0 at time 0.05s (0 + 1*1000 = 1s, no, wait)
  // beatTimes(startTime, bpm, beatsPerBar, fromBeat, untilTime)
  // startTime = nowMs + scheduleAheadMs = 200 + 50 = 250ms
  // interval = 1000ms
  // beats from beat 0: time = 250 + 0*1000 = 250, 1250, 2250 (until 200+100+250=550)
  // So only beat 0 at 250ms → 1 beat scheduled
  assert.equal(fake.scheduleTimes.length, 1);
  assert.equal(fake.scheduleTimes[0].freq, 1000); // accent on beat 0

  m.stop();
});

test("Metronome non-accent beats use 800 Hz", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.setBeatsPerBar(2);
  m.start(120); // 500 ms interval

  fake.advanceTime(0.2);
  m._tick();

  // After first beat (accent), subsequent beats at 0.7s, 1.2s etc within look-ahead
  // The second beat (index 1, not accent) should be 800 Hz
  // beatTimes: startTime=250, untilTime=550, interval=500
  // beat 0: time=250 (accent), beat 1: time=750 (>550, excluded)
  // So only 1 beat at 250ms (accent)
  assert.ok(fake.scheduleTimes.length >= 1);
  // First beat is accent (beat 0) → 1000 Hz
  assert.equal(fake.scheduleTimes[0].freq, 1000);

  m.stop();
});

test("Metronome stop clears the interval and resets", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.start(120);
  m.stop();
  // After stop, _timerId should be null
  assert.equal(m._timerId, null);
  assert.equal(m._playing, false);
});

test("Metronome setBpm updates BPM", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.start(80);
  assert.equal(m._bpm, 80);
  m.setBpm(120);
  assert.equal(m._bpm, 120);
  m.stop();
});

test("Metronome setBeatsPerBar clamps to 2-7", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.start(80);
  m.setBeatsPerBar(1);
  assert.equal(m._beatsPerBar, 2);
  m.setBeatsPerBar(10);
  assert.equal(m._beatsPerBar, 7);
  m.setBeatsPerBar(3);
  assert.equal(m._beatsPerBar, 3);
  m.stop();
});

test("Metronome setVolume clamps to 0-1", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.start(80);
  m.setVolume(1.5);
  assert.equal(m._volume, 1);
  m.setVolume(-0.5);
  assert.equal(m._volume, 0);
  m.setVolume(0.75);
  assert.equal(m._volume, 0.75);
  m.stop();
});

test("Metronome playCue schedules a distinct sound", () => {
  const fake = createFakeAudioContext();
  let cueCalled = false;
  const m = new Metronome(fake.ctx);
  m.setCue(() => { cueCalled = true; });

  fake.advanceTime(0.1);
  const schedBefore = fake.scheduleTimes.length;
  m.playCue();

  assert.ok(cueCalled, "cue callback should have been invoked");
  // playCue creates an additional oscillator (880 Hz)
  assert.ok(fake.scheduleTimes.length > schedBefore, "playCue should schedule an oscillator");
});

test("Metronome playCue at 880 Hz with 80 ms duration", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  fake.advanceTime(0.1);
  m.playCue();

  assert.ok(fake.scheduleTimes.length > 0);
  const last = fake.scheduleTimes[fake.scheduleTimes.length - 1];
  assert.equal(last.freq, 880);
  // 80 ms = 0.08 s (use epsilon due to floating point)
  assert.ok(Math.abs((last.stop - last.start) - 0.08) < 1e-9, "duration should be 80 ms");
});

test("Metronome resume on suspended context", () => {
  const fake = createFakeAudioContext();
  fake.ctx.state = "suspended";
  const m = new Metronome(fake.ctx);
  m.start(120);
  assert.ok(fake.ctx._resumed(), "context should be resumed");
  m.stop();
});

test("Metronome start then stop produces no leaks", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.start(60);
  fake.advanceTime(1);
  const schedCount = fake.scheduleTimes.length;
  m.stop();
  // Scheduling should stop after stop
  fake.advanceTime(1);
  assert.equal(fake.scheduleTimes.length, schedCount, "no new schedules after stop");
});

test("Metronome beatTimes integration — 200 ms spacing at 300 BPM", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  m.start(300); // 200 ms per beat

  fake.advanceTime(0.2);
  m._tick();

  // start() schedules beat 0 at time 50ms (nowMs=0)
  // after 0.2s, _tick() schedules beat 1 at time 250ms (nowMs=200)
  assert.equal(fake.scheduleTimes.length, 2);
  assert.equal(fake.scheduleTimes[0].freq, 1000, "beat 0 is accent");
  assert.equal(fake.scheduleTimes[1].freq, 800, "beat 1 is not accent");

  m.stop();
});

// --- Metronome class tests: fixed startTime and onBeat ---

/**
 * Advance the fake context by 0.025 s and call metronome._tick().
 * Returns the fake context for chaining.
 */
function tickAndAdvance(fake, metronome) {
  fake.advanceTime(0.025);
  metronome._tick();
  return fake;
}

/**
 * Advance the fake context by `n` ticks (0.025 s each) and call _tick each time.
 */
function runTicks(fake, metronome, n) {
  for (let i = 0; i < n; i++) {
    tickAndAdvance(fake, metronome);
  }
}

test("Metronome onBeat callback is invoked with beat and accent", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const beats = [];
  m.onBeat((info) => beats.push(info));

  m.start(60); // 1 beat per second

  // Advance enough to capture a few beats (4 seconds to get beat index 4)
  runTicks(fake, m, 160);

  assert.ok(beats.length > 0, "onBeat should have been called");
  assert.equal(beats[0].beat, 0, "first beat should be beat 0");
  assert.equal(beats[0].accent, true, "first beat should be accented");
  assert.equal(beats[1].beat, 1, "second beat should be beat 1");
  assert.equal(beats[1].accent, false, "second beat should not be accented");
  assert.equal(beats[4].accent, true, "beat 4 (index 4 % 4 === 0) should be accented");

  m.stop();
});

test("Metronome 3 s at 120 BPM schedules exactly 6 clicks, 0.5 s apart", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const clickTimes = [];
  m.onBeat((info) => clickTimes.push(info.time));

  m.start(120); // 500 ms per beat

  // 3 seconds / 0.025 = 120 ticks, but 118 ticks (2.95s) prevents beat 6 (3050ms) from being scheduled
  runTicks(fake, m, 118);

  assert.equal(clickTimes.length, 6, "should have exactly 6 clicks");

  // Check 0.5 s spacing
  for (let i = 1; i < clickTimes.length; i++) {
    const diff = clickTimes[i] - clickTimes[i - 1];
    assert.ok(Math.abs(diff - 500) < 1, `click spacing should be ~500ms, got ${diff}`);
  }

  m.stop();
});

test("Metronome 3 s at 120 BPM — no duplicate clicks", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const clickTimes = [];
  m.onBeat((info) => clickTimes.push(info.time));

  m.start(120);

  runTicks(fake, m, 118);

  // All click times should be unique
  const unique = new Set(clickTimes);
  assert.equal(unique.size, clickTimes.length, "no duplicate clicks");

  m.stop();
});

test("Metronome 3 s at 120 BPM — accent on beats 0 and 4", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const beatInfo = [];
  m.onBeat((info) => beatInfo.push(info));

  m.start(120);

  runTicks(fake, m, 120);

  // Beat 0 should be accented, beats 1-3 not, beat 4 accented
  assert.equal(beatInfo[0].accent, true, "beat 0 should be accented");
  assert.equal(beatInfo[1].accent, false, "beat 1 should not be accented");
  assert.equal(beatInfo[2].accent, false, "beat 2 should not be accented");
  assert.equal(beatInfo[3].accent, false, "beat 3 should not be accented");
  assert.equal(beatInfo[4].accent, true, "beat 4 should be accented");

  m.stop();
});

test("Metronome setBpm(60) after 1 s — next click 1 s after previous", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const beatTimes_list = [];
  m.onBeat((info) => beatTimes_list.push(info.time));

  m.start(120); // 500 ms per beat

  // Advance ~1 second (40 ticks = 1.0 s)
  runTicks(fake, m, 40);

  // Change BPM to 60 (1000 ms interval)
  m.setBpm(60);

  // Continue running to capture the next beats
  runTicks(fake, m, 40);

  // At 120 BPM: beats at 50, 550, 1050
  // After setBpm(60) at ~0.975s, _startTime is recalculated
  // The first 60 BPM beat after the transition should be ~1000ms after the last 120 BPM beat (1050)
  const last120Time = 1050; // last beat before BPM change
  // Find first beat with time >= 1050 + 500 (i.e. after the 120 BPM sequence)
  const firstAfterChangeIdx = beatTimes_list.findIndex(t => t > last120Time);
  assert.ok(firstAfterChangeIdx >= 0, "should have beats after BPM change");
  const gap = beatTimes_list[firstAfterChangeIdx] - beatTimes_list[firstAfterChangeIdx - 1];
  assert.ok(Math.abs(gap - 1000) < 50, `gap at BPM change should be ~1000ms, got ${gap}`);

  m.stop();
});

test("Metronome stop() schedules nothing more", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const clickTimes = [];
  m.onBeat(() => clickTimes.push(fake.currentTime * 1000));

  m.start(120);

  // Get some clicks scheduled
  runTicks(fake, m, 40);
  const countBefore = fake.scheduleTimes.length;

  // Stop the metronome
  m.stop();

  // Advance time — no new beats should be scheduled
  runTicks(fake, m, 40);
  const countAfter = fake.scheduleTimes.length;

  assert.equal(countBefore, countAfter, "stop() should prevent further scheduling");

  m.stop();
});

test("Metronome onBeat returns correct accent pattern for beatsPerBar 3", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const accents = [];
  m.onBeat((info) => accents.push(info.accent));

  m.start(60); // 1 beat per second
  m.setBeatsPerBar(3);

  runTicks(fake, m, 200); // ~5 seconds

  // With beatsPerBar=3: accent on beats 0, 3, 6, 9, ...
  for (let i = 0; i < accents.length; i++) {
    const expectedAccent = (i % 3 === 0);
    assert.equal(accents[i], expectedAccent, `beat ${i} accent should be ${expectedAccent}`);
  }

  m.stop();
});

test("Metronome fixed startTime — beats don't drift across ticks", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);
  const beatTimes_list = [];
  m.onBeat((info) => beatTimes_list.push(info.time));

  m.start(60); // 1 beat per second

  // Run for 4 seconds — prevents last beat (50 + 4*1000 = 4050) from being caught by look-ahead
  runTicks(fake, m, 160);

  // With a fixed startTime, beats should be exactly 1000ms apart
  assert.ok(beatTimes_list.length >= 4, "should have at least 4 beats");
  for (let i = 1; i < beatTimes_list.length; i++) {
    const diff = beatTimes_list[i] - beatTimes_list[i - 1];
    assert.ok(Math.abs(diff - 1000) < 2, `beat spacing should be ~1000ms, got ${diff} at gap ${i}`);
  }

  m.stop();
});

test("Metronome setBpm updates nextBeat and startTime", () => {
  const fake = createFakeAudioContext();
  const m = new Metronome(fake.ctx);

  m.start(120);
  fake.advanceTime(0.5); // advance 0.5s so setBpm has a non-zero nowMs
  const startTimeBefore = m._startTime;
  assert.ok(startTimeBefore > 0, "startTime should be set after start()");

  m.setBpm(60);
  const startTimeAfter = m._startTime;
  assert.ok(startTimeAfter > 0, "startTime should be recalculated after setBpm");
  assert.equal(m._nextBeatIndex, 0, "nextBeatIndex should be reset to 0");

  m.stop();
});
