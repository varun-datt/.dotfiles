export type DoorId = string;

export interface SlotKey {
  site: string;
  door: DoorId;
  /** Slot start, ISO 8601 UTC. */
  start: string;
}

export interface Hold {
  holdRequestId: string;
  carrierId: string;
  key: SlotKey;
  expiresAt: number;
}

export interface Arrival {
  messageId: string;
  site: string;
  carrierId: string;
  asn: string;
  bookedStart: string;
  gateInAt: string;
}

export type Allocation =
  | { kind: "door"; hold: Hold }
  | { kind: "staging"; callForwardAt: string };

export interface Visit {
  gateInAt: string;
  gateOutAt?: string;
  trailerDrop?: boolean;
}
