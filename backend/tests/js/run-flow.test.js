import { describe, it } from 'node:test';
import assert from 'node:assert';
import { createRunner } from '../../app/static/js/runner.js';

describe('Runner flow (SPEC 5.3–5.4)', () => {
  it('two 60 s blocks — nothing logged before 60 s, one logBlock at 60 s', async () => {
    let nowVal = 1_700_000_000_000;
    let cueCount = 0;
    let loggedBlocks = [];
    let finishCallCount = 0;

    const api = {
      startSession() { return Promise.resolve('sess-1'); },
      finish(sid) { finishCallCount++; },
      logBlock(sid, data) { loggedBlocks.push({ sid, ...data }); },
    };
    const deps = { api, now: () => nowVal, cue: () => { cueCount++; } };

    const blocks = [
      { item_id: 1, title: 'Blues scale', planned_seconds: 60, bpm: 80 },
      { item_id: 2, title: 'Pentatonic', planned_seconds: 60, bpm: 100 },
    ];

    const runner = createRunner(blocks, deps);
    runner.start();
    await Promise.resolve(); // let sessionId microtask resolve

    // Tick every 250 ms — nothing logged before 60 s
    for (let i = 1; i <= 239; i++) {
      nowVal = 1_700_000_000_000 + i * 250;
      runner.tick();
    }
    assert.strictEqual(loggedBlocks.length, 0, 'nothing logged before 60 s');
    assert.strictEqual(cueCount, 0);

    // At 60 s exactly one logBlock with played_seconds: 60 (an integer) and the cue once
    nowVal = 1_700_000_060_000;
    runner.tick();
    assert.strictEqual(loggedBlocks.length, 1);
    assert.strictEqual(loggedBlocks[0].played_seconds, 60);
    assert.strictEqual(Number.isInteger(loggedBlocks[0].played_seconds), true,
      'played_seconds is an integer');
    assert.strictEqual(loggedBlocks[0].item_id, 1);
    assert.strictEqual(loggedBlocks[0].planned_seconds, 60);
    assert.strictEqual(cueCount, 1);
    assert.strictEqual(finishCallCount, 0);

    // Runner is now on block 2
    assert.strictEqual(runner.current().index, 1);
    assert.strictEqual(runner.current().title, 'Pentatonic');
    assert.strictEqual(runner.current().remaining, 60);
  });

  it('two 60 s blocks — second block logs at 120 s, finish called once', async () => {
    let nowVal = 1_700_000_000_000;
    let cueCount = 0;
    let loggedBlocks = [];
    let finishCallCount = 0;

    const api = {
      startSession() { return Promise.resolve('sess-2'); },
      finish(sid) { finishCallCount++; },
      logBlock(sid, data) { loggedBlocks.push({ sid, ...data }); },
    };
    const deps = { api, now: () => nowVal, cue: () => { cueCount++; } };

    const blocks = [
      { item_id: 1, title: 'Blues scale', planned_seconds: 60, bpm: 80 },
      { item_id: 2, title: 'Pentatonic', planned_seconds: 60, bpm: 100 },
    ];

    const runner = createRunner(blocks, deps);
    runner.start();
    await Promise.resolve();

    // Tick every 250 ms through both blocks
    for (let i = 1; i <= 479; i++) {
      nowVal = 1_700_000_000_000 + i * 250;
      runner.tick();
    }

    // After 119.75 s: block 1 logged, block 2 not yet
    assert.strictEqual(loggedBlocks.length, 1);
    assert.strictEqual(loggedBlocks[0].item_id, 1);
    assert.strictEqual(cueCount, 1);

    // At 120 s (tick 480), both blocks done
    nowVal = 1_700_000_120_000;
    runner.tick();
    assert.strictEqual(loggedBlocks.length, 2);
    assert.strictEqual(loggedBlocks[0].played_seconds, 60);
    assert.strictEqual(loggedBlocks[0].item_id, 1);
    assert.strictEqual(loggedBlocks[1].played_seconds, 60);
    assert.strictEqual(loggedBlocks[1].item_id, 2);
    assert.strictEqual(cueCount, 2);
    assert.strictEqual(finishCallCount, 1);
    assert.strictEqual(runner.current().done, true);
  });

  it('pause of 10 s in block 1 moves its end to 70 s and does not count as played', async () => {
    let nowVal = 1_700_000_000_000;
    let cueCount = 0;
    let loggedBlocks = [];
    let finishCallCount = 0;

    const api = {
      startSession() { return Promise.resolve('sess-3'); },
      finish(sid) { finishCallCount++; },
      logBlock(sid, data) { loggedBlocks.push({ sid, ...data }); },
    };
    const deps = { api, now: () => nowVal, cue: () => { cueCount++; } };

    const blocks = [
      { item_id: 1, title: 'Blues scale', planned_seconds: 60, bpm: 80 },
      { item_id: 2, title: 'Pentatonic', planned_seconds: 60, bpm: 100 },
    ];

    const runner = createRunner(blocks, deps);
    runner.start();
    await Promise.resolve();

    // Play for 50 seconds
    nowVal = 1_700_000_050_000;
    runner.tick();
    assert.strictEqual(runner.current().remaining, 10);
    assert.strictEqual(runner.current().done, false);
    assert.strictEqual(loggedBlocks.length, 0);

    // Pause for 10 seconds
    runner.pause();
    assert.strictEqual(runner.current().paused, true);

    // Advance time while paused — nothing should happen
    nowVal = 1_700_000_060_000;
    runner.tick();
    assert.strictEqual(runner.current().paused, true);
    assert.strictEqual(runner.current().remaining, 10);
    assert.strictEqual(loggedBlocks.length, 0);

    // Resume
    runner.resume();
    assert.strictEqual(runner.current().paused, false);

    // Continue playing — need 10 more seconds to finish block 1
    nowVal = 1_700_000_070_000;
    runner.tick();
    assert.strictEqual(loggedBlocks.length, 1);
    assert.strictEqual(loggedBlocks[0].played_seconds, 60);
    assert.strictEqual(cueCount, 1);
    assert.strictEqual(runner.current().index, 1);
    assert.strictEqual(runner.current().title, 'Pentatonic');

    // Block 2 starts at 70 s, finishes at 130 s
    nowVal = 1_700_000_130_000;
    runner.tick();
    assert.strictEqual(loggedBlocks.length, 2);
    assert.strictEqual(loggedBlocks[1].played_seconds, 60);
    assert.strictEqual(finishCallCount, 1);
    assert.strictEqual(runner.current().done, true);
  });
});
