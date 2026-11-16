// What the runner page shows for a given state — pure functions, no DOM.
// run-page.js applies the results; tests/js/runner-view.test.js checks them.

/** "m:ss" for a number of seconds (rounded up, never negative). */
export function formatTime(seconds) {
  const total = Math.max(0, Math.ceil(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * Classes for the block bar: done blocks, the current one, the rest empty.
 * index -1 = not started (all empty); null = finished (all done).
 */
export function blockClasses(index, count) {
  const out = [];
  for (let i = 0; i < count; i++) {
    if (index === null || i < index) out.push("is-done");
    else if (i === index) out.push("is-current");
    else out.push("");
  }
  return out;
}

/** Which beat dot lights up for metronome beat `beat` (0-based count since start). */
export function beatIndex(beat, beatsPerBar) {
  return ((beat % beatsPerBar) + beatsPerBar) % beatsPerBar;
}

/** Label of the main button. */
export function mainLabel({ started, paused }) {
  if (!started) return "Start";
  return paused ? "Resume" : "Pause";
}

/** Nav bar title: "Ready" before the start, "2 of 4" while running, "Done" at the end. */
export function navTitle({ started, index, count }) {
  if (!started) return "Ready";
  if (index === null) return "Done";
  return `${index + 1} of ${count}`;
}

/** Line under the title: the next block, or that this is the last one. */
export function nextText(index, titles) {
  if (index === null) return "";
  return index + 1 < titles.length ? `Next: ${titles[index + 1]}` : "Last block";
}

/** For each link's block number, whether it is hidden (only the current block's show). */
export function linksHidden(linkBlocks, index) {
  return linkBlocks.map((b) => b !== (index ?? -1));
}

/** Fraction of the block used, for the progress bar (0 … 1). Both in seconds. */
export function usedFraction(remaining, plannedSeconds) {
  if (!plannedSeconds) return 0;
  const used = 1 - remaining / plannedSeconds;
  return Math.max(0, Math.min(1, used));
}

/** Everything the page needs for one state, in one object. `remaining` is in seconds (timer.js). */
export function runnerView(state, blocks, beatsPerBar = 4) {
  const { started, index, paused, remaining } = state;
  const count = blocks.length;
  const block = index === null ? null : blocks[index];
  return {
    blocks: blockClasses(started ? index : -1, count),
    title: navTitle({ started, index, count }),
    main: mainLabel({ started, paused }),
    blockTitle: block ? block.title : "",
    next: nextText(index, blocks.map((b) => b.title)),
    time: block ? formatTime(remaining) : "0:00",
    of: block ? `of ${formatTime(block.planned_seconds)}` : "",
    used: block ? usedFraction(remaining, block.planned_seconds) : 1,
    beats: beatsPerBar,
  };
}
