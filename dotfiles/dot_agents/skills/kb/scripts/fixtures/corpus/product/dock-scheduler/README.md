# dock-scheduler

Books dock door slots, holds early trucks at the gate, and computes dwell for reports and detention billing.

## Modules
- `src/slots.ts`: `SlotBook`, the in-memory slot book per site, and `SlotConflictException`.
- `src/scheduler.ts`: `allocateSlot`, which picks a free door or sends an early truck to the staging lane (decision 2026-07-22).
- `src/dwell.ts`: `computeDwellMinutes` and detention.
- `src/api/handlers.ts`: HTTP endpoints (`POST /slots/hold`, `POST /slots/release`).
- `src/queue.ts`: consumer for `dock.arrivals`, dead-lettering to `dock.arrivals.dlq`.

## Configuration (environment)
| Variable | Default | Meaning |
| --- | --- | --- |
| `DOCK_SLOTS_MAX` | 40 | Maximum concurrent holds per site |
| `SLOT_MINUTES` | 60 | Slot length |
| `HOLD_TTL_SECONDS` | 900 | Unconfirmed holds expire after this |
| `EARLY_ARRIVAL_CALL_FORWARD_MINUTES` | 20 | Call a staged truck forward this long before its slot |
| `DLQ_MAX_DELIVERIES` | 5 | Deliveries before a message is dead-lettered |

## Run
`npm test`
