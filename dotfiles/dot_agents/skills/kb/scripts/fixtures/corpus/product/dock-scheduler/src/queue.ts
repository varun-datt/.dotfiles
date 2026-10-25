import { DLQ_MAX_DELIVERIES } from "./config.js";
import type { Arrival } from "./types.js";

export interface Broker {
  publish(queue: string, body: string, headers: Record<string, string>, delayMs?: number): Promise<void>;
}

export interface Delivery {
  body: string;
  deliveryCount: number;
  headers: Record<string, string>;
}

/** Delay before redelivery n (1-based), per the 2026-05-12 decision: 1 s, 5 s, 30 s, 2 min, 10 min. */
const BACKOFF_MS = [1_000, 5_000, 30_000, 120_000, 600_000];

export class ArrivalsConsumer {
  private readonly seen = new Set<string>();

  constructor(
    private readonly broker: Broker,
    private readonly handle: (a: Arrival) => Promise<void>,
    private readonly queue = "dock.arrivals",
  ) {}

  async onMessage(d: Delivery): Promise<void> {
    let arrival: Arrival;
    try {
      arrival = JSON.parse(d.body) as Arrival;
    } catch {
      return this.deadLetter(d, "unparseable body");
    }
    if (this.seen.has(arrival.messageId)) return;
    try {
      await this.handle(arrival);
      this.seen.add(arrival.messageId);
    } catch (e) {
      const reason = e instanceof Error ? e.message : String(e);
      if (d.deliveryCount >= DLQ_MAX_DELIVERIES) return this.deadLetter(d, reason);
      const delay = BACKOFF_MS[Math.min(d.deliveryCount, BACKOFF_MS.length) - 1];
      await this.broker.publish(this.queue, d.body, d.headers, delay);
    }
  }

  private async deadLetter(d: Delivery, reason: string): Promise<void> {
    await this.broker.publish(`${this.queue}.dlq`, d.body, { ...d.headers, "x-failure-reason": reason });
  }
}
