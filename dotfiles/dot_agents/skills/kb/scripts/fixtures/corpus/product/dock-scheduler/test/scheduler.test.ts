import { test } from "node:test";
import assert from "node:assert/strict";
import { allocateSlot } from "../src/scheduler.js";
import { SlotBook, SlotConflictException } from "../src/slots.js";
import type { Arrival } from "../src/types.js";

const arrival = (id: string): Arrival => ({
  messageId: id,
  site: "north",
  carrierId: "ridgeway",
  asn: `ASN-${id}`,
  bookedStart: "2026-10-01T09:00:00Z",
  gateInAt: "2026-10-01T07:50:00Z",
});

test("early truck takes a free door", () => {
  const book = new SlotBook(["d1", "d2"], () => 0);
  const result = allocateSlot(book, arrival("a1"), "2026-10-01T08:00:00Z");
  assert.equal(result.kind, "door");
});

test("early truck goes to staging when every door is held", () => {
  const book = new SlotBook(["d1"], () => 0);
  book.hold("h0", "northline", { site: "north", door: "d1", start: "2026-10-01T08:00:00Z" });
  const result = allocateSlot(book, arrival("a2"), "2026-10-01T08:00:00Z");
  assert.deepEqual(result, { kind: "staging", callForwardAt: "2026-10-01T08:40:00.000Z" });
});

test("second hold on the same slot conflicts", () => {
  const book = new SlotBook(["d1"], () => 0);
  const key = { site: "north", door: "d1", start: "2026-10-01T08:00:00Z" };
  book.hold("h1", "northline", key);
  assert.throws(() => book.hold("h2", "ridgeway", key), SlotConflictException);
});

test("repeating a hold with the same holdRequestId is idempotent", () => {
  const book = new SlotBook(["d1"], () => 0);
  const key = { site: "north", door: "d1", start: "2026-10-01T08:00:00Z" };
  const first = book.hold("h1", "northline", key);
  assert.equal(book.hold("h1", "northline", key), first);
});
