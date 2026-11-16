import { describe, it } from 'node:test';
import assert from 'node:assert';
import {
  beatIndex, blockClasses, formatTime, linksHidden, mainLabel, navTitle, nextText,
  runnerView, usedFraction,
} from '../../app/static/js/runner-view.js';

describe('runner view (docs/design.md runner recipe)', () => {
  it('block 2 of 4: first done, second current, rest empty', () => {
    assert.deepStrictEqual(blockClasses(1, 4), ['is-done', 'is-current', '', '']);
  });

  it('before the start nothing is marked; after the end everything is done', () => {
    assert.deepStrictEqual(blockClasses(-1, 3), ['', '', '']);
    assert.deepStrictEqual(blockClasses(null, 3), ['is-done', 'is-done', 'is-done']);
  });

  it('beat 5 with 4 per bar lights span 1', () => {
    assert.strictEqual(beatIndex(5, 4), 1);
    assert.strictEqual(beatIndex(0, 4), 0);
    assert.strictEqual(beatIndex(6, 3), 0);
  });

  it('main button: Start, then Pause, Resume when paused', () => {
    assert.strictEqual(mainLabel({ started: false, paused: false }), 'Start');
    assert.strictEqual(mainLabel({ started: true, paused: false }), 'Pause');
    assert.strictEqual(mainLabel({ started: true, paused: true }), 'Resume');
  });

  it('nav title: Ready, "2 of 4", Done', () => {
    assert.strictEqual(navTitle({ started: false, index: 0, count: 4 }), 'Ready');
    assert.strictEqual(navTitle({ started: true, index: 1, count: 4 }), '2 of 4');
    assert.strictEqual(navTitle({ started: true, index: null, count: 4 }), 'Done');
  });

  it('only the current block\'s links are visible', () => {
    assert.deepStrictEqual(linksHidden([0, 0, 1, 2], 1), [true, true, false, true]);
    assert.deepStrictEqual(linksHidden([0, 1], null), [true, true]);
  });

  it('next text names the next block or says it is the last', () => {
    assert.strictEqual(nextText(0, ['A', 'B']), 'Next: B');
    assert.strictEqual(nextText(1, ['A', 'B']), 'Last block');
  });

  it('formats time and the used fraction', () => {
    assert.strictEqual(formatTime(600), '10:00');
    assert.strictEqual(formatTime(59.001), '1:00');
    assert.strictEqual(formatTime(-5), '0:00');
    assert.strictEqual(usedFraction(30, 60), 0.5);
    assert.strictEqual(usedFraction(90, 60), 0);
  });

  it('runnerView combines it for one state', () => {
    const blocks = [
      { title: 'Scales', planned_seconds: 300 },
      { title: 'Song', planned_seconds: 600 },
    ];
    const v = runnerView({ started: true, index: 1, paused: true, remaining: 300 }, blocks, 3);
    assert.deepStrictEqual(v, {
      blocks: ['is-done', 'is-current'],
      title: '2 of 2',
      main: 'Resume',
      blockTitle: 'Song',
      next: 'Last block',
      time: '5:00',
      of: 'of 10:00',
      used: 0.5,
      beats: 3,
    });
  });
});
