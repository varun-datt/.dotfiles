import type { Visit } from "./types.js";

export const FREE_TIME_MINUTES = 120;

/** Gate-in to gate-out in whole minutes; undefined when there is no gate-out scan or it is a trailer drop. */
export function computeDwellMinutes(visit: Visit): number | undefined {
  if (visit.trailerDrop || !visit.gateOutAt) return undefined;
  const ms = Date.parse(visit.gateOutAt) - Date.parse(visit.gateInAt);
  if (Number.isNaN(ms) || ms < 0) return undefined;
  return Math.round(ms / 60_000);
}

/** Minutes beyond the contract's free time; billed as detention. */
export function detentionMinutes(visit: Visit, freeTime = FREE_TIME_MINUTES): number {
  const dwell = computeDwellMinutes(visit);
  return dwell === undefined ? 0 : Math.max(0, dwell - freeTime);
}
