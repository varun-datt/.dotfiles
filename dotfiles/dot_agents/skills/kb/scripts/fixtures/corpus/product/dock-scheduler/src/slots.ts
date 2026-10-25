import { DOCK_SLOTS_MAX, HOLD_TTL_SECONDS } from "./config.js";
import type { DoorId, Hold, SlotKey } from "./types.js";

export class SlotConflictException extends Error {
  constructor(public readonly key: SlotKey) {
    super("slot already held");
    this.name = "SlotConflictException";
  }
}

export class SlotCapacityException extends Error {
  constructor(public readonly site: string) {
    super(`site ${site} has reached DOCK_SLOTS_MAX`);
    this.name = "SlotCapacityException";
  }
}

const keyOf = (k: SlotKey) => `${k.site}|${k.door}|${k.start}`;

export class SlotBook {
  private readonly holds = new Map<string, Hold>();

  constructor(
    private readonly doors: DoorId[],
    private readonly now: () => number = Date.now,
    private readonly maxHolds: number = DOCK_SLOTS_MAX,
  ) {}

  hold(holdRequestId: string, carrierId: string, key: SlotKey): Hold {
    this.expire();
    const existing = this.holds.get(keyOf(key));
    if (existing) {
      if (existing.holdRequestId === holdRequestId) return existing;
      throw new SlotConflictException(key);
    }
    if (this.activeCount(key.site) >= this.maxHolds) {
      throw new SlotCapacityException(key.site);
    }
    const hold: Hold = { holdRequestId, carrierId, key, expiresAt: this.now() + HOLD_TTL_SECONDS * 1000 };
    this.holds.set(keyOf(key), hold);
    return hold;
  }

  release(key: SlotKey): boolean {
    return this.holds.delete(keyOf(key));
  }

  isFree(key: SlotKey): boolean {
    this.expire();
    return !this.holds.has(keyOf(key));
  }

  freeDoors(site: string, start: string): DoorId[] {
    return this.doors.filter((door) => this.isFree({ site, door, start }));
  }

  activeCount(site: string): number {
    let n = 0;
    for (const h of this.holds.values()) if (h.key.site === site) n++;
    return n;
  }

  private expire(): void {
    const t = this.now();
    for (const [k, h] of this.holds) if (h.expiresAt <= t) this.holds.delete(k);
  }
}
