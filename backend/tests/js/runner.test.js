import { describe, it } from 'node:test';
import assert from 'node:assert';
import { createRunner } from '../../app/static/js/runner.js';

describe('createRunner', () => {
  function makeDeps(options = {}) {
    let { startSessionId, nowValue } = options;
    let finished = false;
    let loggedBlocks = [];
    const api = {
      startSession() { return Promise.resolve(startSessionId || 'sess-1'); },
      finish(sid) { finished = true; },
      logBlock(sid, data) { loggedBlocks.push({ sid, ...data }); }
    };
    const deps = { api, now: () => nowValue, cue: () => {} };
    return { deps, api, getFinished: () => finished, getLoggedBlocks: () => loggedBlocks };
  }

  it('should start with session id from deps.api.startSession', async () => {
    const blocks = [{ id: 'b1', title: 'Blues scale', planned_seconds: 300, item_id: 1 }];
    const { deps, getFinished } = makeDeps({ startSessionId: 'sess-123', nowValue: 1_000_000 });
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps);
    run.start();
    assert.strictEqual(run.current().title, 'Blues scale');
    assert.strictEqual(run.current().remaining, 300);
    assert.strictEqual(getFinished(), false);
  });

  it('should tick remaining time and played time', async () => {
    const blocks = [{ id: 'b1', title: 'Test block', planned_seconds: 30, item_id: 1 }];
    let nowVal = 1_000_000;
    const { deps } = makeDeps({ nowValue: nowVal });
    const deps2 = { ...deps, now: () => nowVal };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps2);
    run.start();
    nowVal = 1_025_000;
    run.tick();
    const state = run.current();
    assert.strictEqual(state.remaining, 5);
    assert.strictEqual(state.done, false);
  });

  it('should pause and resume correctly', async () => {
    const blocks = [{ id: 'b1', title: 'Test block', planned_seconds: 30, item_id: 1 }];
    let nowVal = 1_000_000;
    const { deps } = makeDeps({ nowValue: nowVal });
    const deps2 = { ...deps, now: () => nowVal };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps2);
    run.start();
    nowVal = 1_005_000;
    run.tick();
    assert.strictEqual(run.current().remaining, 25);
    run.pause();
    assert.strictEqual(run.current().paused, true);
    assert.strictEqual(run.current().remaining, 25);
    nowVal = 1_050_000;
    run.tick();
    assert.strictEqual(run.current().remaining, 25);
    run.resume();
    nowVal = 1_057_000;
    run.tick();
    assert.strictEqual(run.current().remaining, 18);
  });

  it('should skip to next block and reset timer', async () => {
    const blocks = [
      { id: 'b1', title: 'Block 1', planned_seconds: 30, item_id: 1 },
      { id: 'b2', title: 'Block 2', planned_seconds: 60, item_id: 2 }
    ];
    let nowVal = 1_000_000;
    const { deps } = makeDeps({ nowValue: nowVal });
    const deps2 = { ...deps, now: () => nowVal };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps2);
    run.start();
    run.skip();
    assert.strictEqual(run.current().title, 'Block 2');
    assert.strictEqual(run.current().remaining, 60);
    nowVal = 1_010_000;
    run.tick();
    assert.strictEqual(run.current().remaining, 50);
  });

  it('should finish when last block ends', async () => {
    let finished = false;
    const blocks = [{ id: 'b1', title: 'Last block', planned_seconds: 10, item_id: 1 }];
    const api = {
      startSession() { return Promise.resolve('sess-1'); },
      finish(sid) { finished = true; },
      logBlock(sid, data) { }
    };
    let nowVal = 1_000_000;
    const deps = { api, now: () => nowVal, cue: () => {} };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps);
    run.start();
    await Promise.resolve();
    nowVal = 1_010_000;
    run.tick();
    assert.strictEqual(finished, true);
  });

  it('should add seconds via addMinute', async () => {
    const blocks = [{ id: 'b1', title: 'Test', planned_seconds: 10, item_id: 1 }];
    let nowVal = 1_000_000;
    const { deps } = makeDeps({ nowValue: nowVal });
    const deps2 = { ...deps, now: () => nowVal };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps2);
    run.start();
    run.addMinute();
    assert.strictEqual(run.current().remaining, 70);
  });

  it('should set bpm via setBpm', async () => {
    const blocks = [{ id: 'b1', title: 'Test', planned_seconds: 10, item_id: 1 }];
    let nowVal = 1_000_000;
    const { deps } = makeDeps({ nowValue: nowVal });
    const deps2 = { ...deps, now: () => nowVal };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps2);
    run.start();
    run.setBpm(120);
    assert.strictEqual(run.current().bpm, 120);
  });

  it('should return session data via current()', async () => {
    const blocks = [{ id: 'b1', title: 'Test', planned_seconds: 30, item_id: 1 }];
    let nowVal = 1_000_000;
    const { deps } = makeDeps({ nowValue: nowVal });
    const deps2 = { ...deps, now: () => nowVal };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps2);
    run.start();
    const state = run.current();
    assert.strictEqual(state.title, 'Test');
    assert.strictEqual(state.remaining, 30);
    assert.strictEqual(state.index, 0);
  });

  it('uses start_bpm for the first block and logs it', async () => {
    const blocks = [{ title: 'Song', planned_seconds: 10, item_id: 1, start_bpm: 72 }];
    let nowVal = 1_000_000;
    const { api, getLoggedBlocks } = makeDeps();
    const deps2 = { api, now: () => nowVal, cue: () => {} };
    const run = (await import('../../app/static/js/runner.js')).createRunner(blocks, deps2);
    run.start();
    await new Promise((r) => setTimeout(r, 0)); // startSession resolves
    assert.strictEqual(run.current().bpm, 72);
    nowVal += 10_000;
    run.tick();
    await new Promise((r) => setTimeout(r, 0));
    assert.strictEqual(getLoggedBlocks()[0].bpm, 72);
  });
});

describe('finish and the logged BPM', () => {
  function setup(extra = {}) {
    let nowVal = 1_000_000;
    const logged = [];
    let finished = 0;
    const deps = {
      api: {
        startSession: () => Promise.resolve('s'),
        logBlock: (sid, data) => logged.push(data),
        finish: () => { finished++; },
      },
      now: () => nowVal,
      cue: () => {},
      ...extra,
    };
    const runner = createRunner(
      [{ item_id: 1, title: 'A', planned_seconds: 60, start_bpm: 90 },
       { item_id: 2, title: 'B', planned_seconds: 60, start_bpm: 100 }], deps);
    return { runner, logged, advance: (ms) => { nowVal += ms; }, finished: () => finished };
  }

  it('finish logs the block in progress, then finishes once', async () => {
    const { runner, logged, advance, finished } = setup();
    runner.start();
    await new Promise((r) => setTimeout(r, 0));
    advance(30_000);
    runner.finish();
    runner.finish();
    assert.strictEqual(logged.length, 1);
    assert.strictEqual(logged[0].played_seconds, 30);
    assert.strictEqual(logged[0].bpm, 90);
    assert.strictEqual(finished(), 1);
    assert.strictEqual(runner.current().done, true);
  });

  it('bpmToLog can make the logged BPM null (metronome off)', async () => {
    const { runner, logged, advance } = setup({ bpmToLog: () => null });
    runner.start();
    await new Promise((r) => setTimeout(r, 0));
    advance(60_000);
    runner.tick();
    assert.strictEqual(logged[0].bpm, null);
  });
});

describe('skip on the last block', () => {
  it('finishes the session', async () => {
    let nowVal = 0;
    let finished = 0;
    const runner = createRunner([{ item_id: 1, title: 'A', planned_seconds: 60 }], {
      api: { startSession: () => Promise.resolve('s'), logBlock: () => {}, finish: () => { finished++; } },
      now: () => nowVal,
      cue: () => {},
    });
    runner.start();
    await new Promise((r) => setTimeout(r, 0));
    nowVal = 20_000;
    runner.skip();
    assert.strictEqual(finished, 1);
    assert.strictEqual(runner.current().done, true);
  });
});
