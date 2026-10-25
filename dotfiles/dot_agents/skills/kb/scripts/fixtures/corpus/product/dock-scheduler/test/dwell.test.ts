import { test } from "node:test";
import assert from "node:assert/strict";
import { computeDwellMinutes, detentionMinutes } from "../src/dwell.js";

test("dwell is gate-in to gate-out in minutes", () => {
  assert.equal(computeDwellMinutes({ gateInAt: "2026-10-01T08:00:00Z", gateOutAt: "2026-10-01T09:12:00Z" }), 72);
});

test("missing gate-out scan gives no dwell", () => {
  assert.equal(computeDwellMinutes({ gateInAt: "2026-10-01T08:00:00Z" }), undefined);
});

test("trailer drop gives no dwell", () => {
  assert.equal(
    computeDwellMinutes({ gateInAt: "2026-10-01T08:00:00Z", gateOutAt: "2026-10-01T08:10:00Z", trailerDrop: true }),
    undefined,
  );
});

test("detention starts after the free time", () => {
  assert.equal(detentionMinutes({ gateInAt: "2026-10-01T08:00:00Z", gateOutAt: "2026-10-01T10:30:00Z" }), 30);
});
