import test from "node:test";
import assert from "node:assert/strict";

import {
  buildQuery,
  formatRelativeTime,
  initials,
  priorityTone,
  statusTone,
  truncate,
  viewParams,
} from "../src/lib/format.js";

test("initials", () => {
  assert.equal(initials("Sok Dara"), "SD");
  assert.equal(initials("Dara"), "DA");
  assert.equal(initials("  "), "?");
  assert.equal(initials("a b c"), "AC");
});

test("truncate", () => {
  assert.equal(truncate("short", 20), "short");
  assert.equal(truncate("a".repeat(30), 10).length, 10);
  assert.ok(truncate("a".repeat(30), 10).endsWith("…"));
});

test("statusTone / priorityTone fall back to neutral", () => {
  assert.equal(statusTone("resolved"), "success");
  assert.equal(statusTone("open"), "brand");
  assert.equal(statusTone("nonsense"), "neutral");
  assert.equal(priorityTone("urgent"), "danger");
  assert.equal(priorityTone("normal"), "neutral");
});

test("formatRelativeTime", () => {
  const now = Date.parse("2026-10-14T12:00:00Z");
  assert.equal(formatRelativeTime("2026-10-14T11:59:45Z", now), "just now");
  assert.equal(formatRelativeTime("2026-10-14T11:55:00Z", now), "5m ago");
  assert.equal(formatRelativeTime("2026-10-14T09:00:00Z", now), "3h ago");
  assert.equal(formatRelativeTime("2026-10-13T12:00:00Z", now), "1d ago");
  assert.equal(formatRelativeTime(null, now), "");
  assert.equal(formatRelativeTime("not-a-date", now), "");
});

test("buildQuery skips empty values", () => {
  assert.equal(buildQuery({ status: "open", q: "" }), "?status=open");
  assert.equal(buildQuery({ status: "open", q: "card" }), "?status=open&q=card");
  assert.equal(buildQuery({}), "");
  assert.equal(buildQuery({ assignee: undefined, limit: 0 }), "?limit=0");
});

test("viewParams maps saved views to filters", () => {
  assert.deepEqual(viewParams("open"), { status: "open" });
  assert.deepEqual(viewParams("unassigned"), { assignee: "none" });
  assert.deepEqual(viewParams("all"), {});
  assert.deepEqual(viewParams("unknown"), {});
});
