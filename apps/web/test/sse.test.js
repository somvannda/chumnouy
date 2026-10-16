import test from "node:test";
import assert from "node:assert/strict";

import { createSseParser } from "../src/lib/sse.js";

function collect() {
  const events = [];
  return { events, parser: createSseParser((event) => events.push(event)) };
}

test("parses one event", () => {
  const { events, parser } = collect();
  parser.push('event: ready\ndata: {"a":1}\n\n');
  assert.deepEqual(events, [{ event: "ready", data: { a: 1 } }]);
});

test("buffers an event split across chunks", () => {
  const { events, parser } = collect();
  parser.push("event: mes");
  assert.deepEqual(events, []);
  parser.push('sage\ndata: {"body":"hi"}\n');
  assert.deepEqual(events, []);
  parser.push("\n");
  assert.deepEqual(events, [{ event: "message", data: { body: "hi" } }]);
});

test("parses several events from one chunk", () => {
  const { events, parser } = collect();
  parser.push('event: ready\ndata: {"n":1}\n\nevent: done\ndata: {"n":2}\n\n');
  assert.deepEqual(events.map((event) => event.event), ["ready", "done"]);
  assert.equal(events[1].data.n, 2);
});

test("ignores heartbeat comments and defaults to the message event", () => {
  const { events, parser } = collect();
  parser.push(": keep-alive\n\n");
  parser.push('data: {"body":"x"}\n\n');
  assert.deepEqual(events, [{ event: "message", data: { body: "x" } }]);
});

test("joins multi-line data and tolerates non-JSON", () => {
  const { events, parser } = collect();
  parser.push("event: note\ndata: plain text\n\n");
  assert.deepEqual(events, [{ event: "note", data: null }]);
  events.length = 0;
  parser.push('event: multi\ndata: {"a":\ndata: 1}\n\n');
  assert.deepEqual(events, [{ event: "multi", data: { a: 1 } }]);
});

test("handles CRLF and flushes a trailing event", () => {
  const { events, parser } = collect();
  parser.push('event: ready\r\ndata: {"ok":true}\r\n\r\n');
  assert.deepEqual(events, [{ event: "ready", data: { ok: true } }]);
  events.length = 0;
  parser.push('event: tail\ndata: {"ok":false}');
  assert.deepEqual(events, []);
  parser.flush();
  assert.deepEqual(events, [{ event: "tail", data: { ok: false } }]);
});
