import type { IncomingMessage, ServerResponse } from "node:http";
import { SlotBook, SlotCapacityException, SlotConflictException } from "../slots.js";
import type { SlotKey } from "../types.js";

const MAX_BODY_BYTES = 16 * 1024;

function send(res: ServerResponse, code: number, body: unknown): void {
  res.writeHead(code, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

async function readJson(req: IncomingMessage): Promise<unknown> {
  let size = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new Error("body too large");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

function parseHold(body: unknown): { holdRequestId: string; carrierId: string; key: SlotKey } | undefined {
  if (typeof body !== "object" || body === null) return undefined;
  const b = body as Record<string, unknown>;
  const str = (v: unknown) => typeof v === "string" && v.length > 0 && v.length <= 64;
  if (!str(b.holdRequestId) || !str(b.carrierId) || !str(b.site) || !str(b.door) || !str(b.start)) return undefined;
  if (Number.isNaN(Date.parse(b.start as string))) return undefined;
  return {
    holdRequestId: b.holdRequestId as string,
    carrierId: b.carrierId as string,
    key: { site: b.site as string, door: b.door as string, start: b.start as string },
  };
}

export function makeHandler(book: SlotBook) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    if (req.method === "POST" && req.url === "/slots/hold") {
      let input;
      try {
        input = parseHold(await readJson(req));
      } catch {
        return send(res, 400, { error: "invalid JSON body" });
      }
      if (!input) return send(res, 400, { error: "holdRequestId, carrierId, site, door and start are required" });
      try {
        const hold = book.hold(input.holdRequestId, input.carrierId, input.key);
        return send(res, 201, hold);
      } catch (e) {
        if (e instanceof SlotConflictException) return send(res, 409, { error: e.message });
        if (e instanceof SlotCapacityException) return send(res, 429, { error: e.message });
        throw e;
      }
    }
    if (req.method === "POST" && req.url === "/slots/release") {
      let input;
      try {
        input = parseHold(await readJson(req));
      } catch {
        return send(res, 400, { error: "invalid JSON body" });
      }
      if (!input) return send(res, 400, { error: "site, door and start are required" });
      return send(res, book.release(input.key) ? 200 : 404, {});
    }
    send(res, 404, { error: "not found" });
  };
}
