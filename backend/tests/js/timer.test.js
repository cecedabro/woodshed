// Tests for timer.js — pure countdown timer module.
// Run with: cd backend && node --test tests/js/timer.test.js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createTimer } from "../../app/static/js/timer.js";

test("createTimer returns not started state", () => {
  const t = createTimer(60);
  assert.equal(t.isRunning(), false);
  assert.equal(t.remaining(0), 60);
  assert.equal(t.played(0), 0);
  assert.equal(t.isDone(0), false);
});

test("start sets running state from ms timestamp", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.isRunning(), true);
});

test("remaining returns correct seconds after start", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.remaining(1_001_000), 59);
});

test("played returns correct seconds after start", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.played(1_030_000), 30);
});

test("remaining decreases as ms time advances", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.remaining(1_000_000), 60);
  assert.equal(t.remaining(1_010_000), 50);
  assert.equal(t.remaining(1_030_000), 30);
  assert.equal(t.remaining(1_059_000), 1);
});

test("played increases as ms time advances", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.played(1_000_000), 0);
  assert.equal(t.played(1_010_000), 10);
  assert.equal(t.played(1_030_000), 30);
  assert.equal(t.played(1_059_000), 59);
});

test("isDone false at +59 999ms, true at +60 000ms", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.isDone(1_059_999), false);
  assert.equal(t.isDone(1_060_000), true);
});

test("pause excludes time from played and remaining", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.played(1_010_000), 10);
  assert.equal(t.remaining(1_010_000), 50);

  t.pause(1_010_000);
  assert.equal(t.isRunning(), false);

  // Advancing now while paused should not increase played or decrease remaining
  assert.equal(t.played(1_050_000), 10);
  assert.equal(t.remaining(1_050_000), 50);
});

test("resume continues from pause point", () => {
  const t = createTimer(60);
  t.start(1_000_000);

  t.pause(1_010_000);
  t.resume(1_015_000);

  // 5 more seconds of running → total played = 15
  assert.equal(t.played(1_020_000), 15);
  assert.equal(t.remaining(1_020_000), 45);
});

test("pause at +10 000, resume at +15 000 → played at +20 000 is 15", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  t.pause(1_010_000);
  t.resume(1_015_000);
  assert.equal(t.played(1_020_000), 15);
});

test("addSeconds extends remaining right after start", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  t.addSeconds(60);
  assert.equal(t.remaining(1_000_000), 120);
});

test("addSeconds during running extends remaining", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.remaining(1_005_000), 55);

  t.addSeconds(30);
  assert.equal(t.remaining(1_005_000), 85);
  assert.equal(t.remaining(1_010_000), 80);
});

test("remaining never goes negative", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.remaining(1_060_000), 0);
  assert.equal(t.remaining(1_099_999), 0);
});

test("isDone false at +59 999ms boundary", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.isDone(1_059_999), false);
});

test("isDone true at +60 000ms boundary", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.isDone(1_060_000), true);
});

test("timer does not play while paused, then plays after resume", () => {
  const t = createTimer(30);
  t.start(1_000_000);
  assert.equal(t.remaining(1_015_000), 15);

  t.pause(1_015_000);

  // Large gap while paused
  t.resume(1_100_000);

  // 5 more seconds of running on second interval (15 + 5 = 20)
  assert.equal(t.played(1_105_000), 20);
  assert.equal(t.remaining(1_105_000), 10);
});

test("remaining is 0 after timer completes", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.isDone(1_060_000), true);
  assert.equal(t.remaining(1_200_000), 0);
});

test("pause then addSeconds adjusts remaining", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  t.pause(1_010_000);
  assert.equal(t.remaining(1_010_000), 50);

  t.addSeconds(60);
  assert.equal(t.remaining(1_010_000), 110);

  t.resume(1_010_000);
  assert.equal(t.remaining(1_020_000), 100);
});

test("addSeconds(60) → remaining 119 one second after start", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  t.addSeconds(60);
  assert.equal(t.remaining(1_001_000), 119);
});

test("remaining and played while running with ms values", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  assert.equal(t.remaining(1_010_000), 50);
  assert.equal(t.played(1_010_000), 10);

  assert.equal(t.remaining(1_030_000), 30);
  assert.equal(t.played(1_030_000), 30);

  assert.equal(t.remaining(1_060_000), 0);
  assert.equal(t.played(1_060_000), 60);
});

test("pause then resume — exact 60s total with gap", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  t.pause(1_020_000);
  t.resume(1_025_000);
  assert.equal(t.played(1_040_000), 35);
  assert.equal(t.remaining(1_040_000), 25);
});

test("pause on already paused timer is no-op", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  t.pause(1_010_000);
  t.pause(1_020_000);
  assert.equal(t.isRunning(), false);
  assert.equal(t.played(1_020_000), 10);
  assert.equal(t.remaining(1_020_000), 50);
});

test("addSeconds with negative value", () => {
  const t = createTimer(60);
  t.start(1_000_000);
  t.addSeconds(-10);
  assert.equal(t.remaining(1_000_000), 50);
});
