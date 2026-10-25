export const DOCK_SLOTS_MAX = Number(process.env.DOCK_SLOTS_MAX ?? 40);
export const SLOT_MINUTES = Number(process.env.SLOT_MINUTES ?? 60);
export const HOLD_TTL_SECONDS = Number(process.env.HOLD_TTL_SECONDS ?? 900);
export const EARLY_ARRIVAL_CALL_FORWARD_MINUTES = Number(process.env.EARLY_ARRIVAL_CALL_FORWARD_MINUTES ?? 20);
export const DLQ_MAX_DELIVERIES = Number(process.env.DLQ_MAX_DELIVERIES ?? 5);
