// JS unit tests run with `node --test tests/js/` (no npm packages). See docs/frontend.md §js.
import { test } from "node:test";
import assert from "node:assert/strict";

test("node test runner works", () => {
  assert.equal(1 + 1, 2);
});
