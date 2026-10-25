import { EARLY_ARRIVAL_CALL_FORWARD_MINUTES } from "./config.js";
import type { SlotBook } from "./slots.js";
import type { Allocation, Arrival } from "./types.js";

/**
 * Early-arrival rule (decision 2026-07-22): take a free door now if one exists,
 * otherwise send the truck to the staging lane and call it forward before its booked slot.
 */
export function allocateSlot(book: SlotBook, arrival: Arrival, slotStart: string): Allocation {
  const free = book.freeDoors(arrival.site, slotStart);
  if (free.length > 0) {
    const hold = book.hold(arrival.messageId, arrival.carrierId, {
      site: arrival.site,
      door: free[0],
      start: slotStart,
    });
    return { kind: "door", hold };
  }
  const booked = Date.parse(arrival.bookedStart);
  const callForwardAt = new Date(booked - EARLY_ARRIVAL_CALL_FORWARD_MINUTES * 60_000).toISOString();
  return { kind: "staging", callForwardAt };
}
