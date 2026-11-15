// Pure countdown timer for a single practice block.
// See docs/frontend.md §js.

export function createTimer(plannedSeconds) {
  let remaining = plannedSeconds;
  let played = 0;
  let running = false;
  let startRunningAt = 0;

  return {
    start(now) {
      running = true;
      startRunningAt = now;
      remaining = plannedSeconds;
      played = 0;
    },

    pause(now) {
      if (running) {
        played += now - startRunningAt;
        remaining = Math.max(0, remaining - (now - startRunningAt));
      }
      running = false;
    },

    resume(now) {
      running = true;
      startRunningAt = now;
    },

    addSeconds(n) {
      remaining += n;
    },

    remaining(now) {
      if (running) {
        return Math.max(0, remaining - (now - startRunningAt));
      }
      return remaining;
    },

    played(now) {
      if (running) {
        return played + (now - startRunningAt);
      }
      return played;
    },

    isDone(now) {
      return this.remaining(now) === 0;
    },

    isRunning() {
      return running;
    },
  };
}
