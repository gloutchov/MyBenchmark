"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const app = require("../app.js");

test("rejects an unsupported schema", () => {
  assert.throws(() => app.validateDashboardData({ schema_version: 99 }));
});

test("the baseline must be replaced with a working view", () => {
  const view = app.createDashboardView({ schema_version: 1, profile_order: [], runs: [], funnel: [] }, {});
  assert.notDeepEqual(view.profiles, []);
});
