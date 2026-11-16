// Session runner logic — pure module.
// See docs/frontend.md §js.

import { createTimer } from "./timer.js";

export function createRunner(blocks, deps) {
  let currentIndex = -1;
  let loggedBlocks = [];
  let done = false;
  let sessionId = null;
  let currentBpm = 0;
  let currentTimer = null;

  function start() {
    sessionId = null;
    const promise = deps.api.startSession();
    promise.then(function(id) {
      sessionId = id;
    });
    done = false;
    currentIndex = 0;
    currentBpm = 0;
    _setupTimer();
  }

  function _setupTimer() {
    const block = blocks[currentIndex];
    currentTimer = createTimer(block.planned_seconds);
    currentTimer.start(deps.now());
    currentBpm = block.bpm || 80;
  }

  function tick() {
    if (done) return;
    if (currentIndex < 0 || currentIndex >= blocks.length) {
      done = true;
      return;
    }
    if (!currentTimer || !currentTimer.isDone(deps.now())) {
      return;
    }
    _logCurrentBlock();
    deps.cue();
    currentIndex++;
    if (currentIndex >= blocks.length) {
      done = true;
      if (sessionId) {
        deps.api.finish(sessionId);
      }
    } else {
      _setupTimer();
    }
  }

  function _logCurrentBlock() {
    const block = blocks[currentIndex];
    const played = currentTimer.played(deps.now());
    if (!sessionId) return;
    deps.api.logBlock(sessionId, {
      item_id: block.item_id,
      position: currentIndex,
      planned_seconds: block.planned_seconds,
      played_seconds: Math.round(played),
      bpm: currentBpm,
    });
    loggedBlocks.push({
      item_id: block.item_id,
      position: currentIndex,
      planned_seconds: block.planned_seconds,
      played_seconds: Math.round(played),
      bpm: currentBpm,
    });
  }

  function pause() {
    if (currentTimer && currentTimer.isRunning()) {
      currentTimer.pause(deps.now());
    }
  }

  function resume() {
    if (currentTimer && !currentTimer.isRunning()) {
      currentTimer.resume(deps.now());
    }
  }

  function skip() {
    if (done) return;
    if (currentIndex < 0 || currentIndex >= blocks.length) return;
    if (currentTimer && currentTimer.isDone(deps.now())) return;
    _logCurrentBlock();
    deps.cue();
    currentIndex++;
    if (currentIndex < blocks.length) {
      _setupTimer();
    }
  }

  function addMinute() {
    if (currentTimer) {
      currentTimer.addSeconds(60);
    }
  }

  function setBpm(bpm) {
    currentBpm = bpm;
  }

  function finish() {
    if (sessionId && !done) {
      deps.api.finish(sessionId);
      done = true;
    }
  }

  function current() {
    if (done || currentIndex < 0 || currentIndex >= blocks.length) {
      return {
        index: null,
        title: null,
        remaining: 0,
        bpm: 0,
        paused: false,
        done: true,
      };
    }
    const block = blocks[currentIndex];
    const paused = currentTimer && !currentTimer.isRunning();
    const isComplete = currentTimer && currentTimer.isDone(deps.now());
    return {
      index: currentIndex,
      title: block.title,
      remaining: currentTimer ? currentTimer.remaining(deps.now()) : 0,
      bpm: currentBpm,
      paused: paused && !isComplete,
      done: isComplete,
    };
  }

  return {
    start: start,
    tick: tick,
    pause: pause,
    resume: resume,
    skip: skip,
    addMinute: addMinute,
    setBpm: setBpm,
    finish: finish,
    current: current,
  };
}
