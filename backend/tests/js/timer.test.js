// Tests for timer.js — pure countdown timer module.
// Run with: cd backend && node --test tests/js/timer.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createTimer } from "../../app/static/js/timer.js";

test("remaining and played while running", () => {
  const t = createTimer(60);
  assert.equal(t.remaining(0), 60);
  assert.equal(t.played(0), 0);
  assert.equal(t.isRunning(), false);

  t.start(0);
  assert.equal(t.remaining(10), 50);
  assert.equal(t.played(10), 10);
  assert.equal(t.isRunning(), true);

  assert.equal(t.remaining(30), 30);
  assert.equal(t.played(30), 30);

  assert.equal(t.remaining(60), 0);
  assert.equal(t.played(60), 60);
});

test("pause excludes time from played", () => {
  const t = createTimer(60);
  t.start(0);
  assert.equal(t.played(20), 20);
  assert.equal(t.remaining(20), 40);

  t.pause(20);
  assert.equal(t.isRunning(), false);

  // Advancing now while paused should not increase played
  assert.equal(t.played(50), 20);
  assert.equal(t.remaining(50), 40);
});

test("resume continues from pause point", () => {
  const t = createTimer(60);
  t.start(0);
  assert.equal(t.played(20), 20);
  assert.equal(t.remaining(20), 40);

  t.pause(20);
  t.resume(20);
  assert.equal(t.isRunning(), true);

  // 15 more seconds of running
  assert.equal(t.played(35), 35);
  assert.equal(t.remaining(35), 25);
});

test("addSeconds extends remaining", () => {
  const t = createTimer(60);
  t.start(0);
  assert.equal(t.remaining(10), 50);

  t.addSeconds(60);
  assert.equal(t.remaining(10), 110);

  assert.equal(t.remaining(20), 100);
  assert.equal(t.played(20), 20);
});

test("isDone is true exactly when remaining reaches 0", () => {
  const t = createTimer(60);
  t.start(0);
  assert.equal(t.isDone(0), false);
  assert.equal(t.isDone(30), false);
  assert.equal(t.isDone(59), false);
  assert.equal(t.isDone(60), true);
});

test("remaining never goes negative", () => {
  const t = createTimer(60);
  t.start(0);

  // Advance far past the planned duration
  assert.equal(t.remaining(999), 0);

  // Pause and resume should also not go negative
  t.pause(60);
  t.resume(60);
  assert.equal(t.remaining(999), 0);
  assert.equal(t.played(999), 999);
});

test("remaining is 0 on timer that completed, even if now advances past end", () => {
  const t = createTimer(60);
  t.start(0);
  assert.equal(t.isDone(60), true);

  // remaining stays at 0 even far past the end
  assert.equal(t.remaining(1000), 0);
});

test("started timer does not play while paused, then plays after resume", () => {
  const t = createTimer(30);
  t.start(0);
  assert.equal(t.remaining(15), 15);

  t.pause(15);

  // Large gap while paused
  t.resume(100);

  // Only 5 seconds of actual running on second interval
  assert.equal(t.played(105), 20);
  assert.equal(t.remaining(105), 10);
});

test("createTimer returns not started state", () => {
  const t = createTimer(60);
  assert.equal(t.isRunning(), false);
  assert.equal(t.remaining(0), 60);
  assert.equal(t.played(0), 0);
  assert.equal(t.isDone(0), false);
});

test("pause then addSeconds adjusts remaining", () => {
  const t = createTimer(60);
  t.start(0);
  t.pause(10);
  assert.equal(t.remaining(10), 50);

  t.addSeconds(60);
  assert.equal(t.remaining(10), 110);

  t.resume(10);
  assert.equal(t.remaining(20), 100);
});
