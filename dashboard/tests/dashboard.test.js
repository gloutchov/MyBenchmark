"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "../..");
const Core = require(path.join(ROOT, "dashboard/js/core.js"));
const I18n = require(path.join(ROOT, "dashboard/js/i18n.js"));
const fixture = JSON.parse(
  fs.readFileSync(path.join(ROOT, "cases/results_dashboard/fixture/dashboard-data.json"), "utf8")
);

function alternateDataset() {
  const run = JSON.parse(JSON.stringify(fixture.runs[0]));
  run.id = "alternate-run";
  run.profile = "custom";
  run.participants = ["model-unseen"];
  run.leaderboard = [
    {
      ...run.leaderboard[0],
      rank: 1,
      model: "model-unseen",
      overall_score: 77,
      quality_score: 81,
      median_duration_seconds: 55,
    },
  ];
  run.tasks = [
    {
      ...run.tasks[0],
      model: "model-unseen",
      case_id: "new-case",
      case_title: "Caso nuovo",
      case_title_en: "New case",
      category: "alternate",
      score: 81,
      state: "passed",
    },
  ];
  return {
    schema_version: 1,
    profile_order: ["custom"],
    runs: [run],
    funnel: [
      {
        profile: "custom",
        run_ids: [run.id],
        participants: ["model-unseen"],
        new_participants: ["model-unseen"],
        next_profile: null,
        continued_to_next: [],
        not_run_in_next: [],
      },
    ],
  };
}

test("validates the frozen dataset and rejects malformed input", () => {
  assert.equal(Core.validateDashboardData(fixture), true);
  assert.throws(
    () => Core.validateDashboardData({ schema_version: 99, profile_order: [], runs: [], funnel: [] }),
    /schema/i
  );
  const duplicate = JSON.parse(JSON.stringify(fixture));
  duplicate.runs.push(JSON.parse(JSON.stringify(duplicate.runs[0])));
  assert.throws(() => Core.validateDashboardData(duplicate), /duplicate/i);
  const leaked = JSON.parse(JSON.stringify(fixture));
  leaked.runs[0].tasks[0].final_response = "PRIVATE-RESPONSE";
  assert.throws(() => Core.validateDashboardData(leaked), /fields/i);
  const invalidState = JSON.parse(JSON.stringify(fixture));
  invalidState.runs[0].tasks[0].state = "mystery";
  assert.throws(() => Core.validateDashboardData(invalidState), /metadata/i);
});

test("creates filtered and sorted views without mutating the dataset", () => {
  const before = JSON.stringify(fixture);
  const view = Core.createDashboardView(fixture, {
    profile: "smoke",
    model: "qwen3.5:9b-mlx",
    query: "targeted",
    sortBy: "median_duration_seconds",
    sortDirection: "asc",
  });
  assert.deepEqual(view.availableModels.includes("qwen3.5:9b-mlx"), true);
  assert.ok(view.leaderboard.every((row) => row.profile === "smoke" && row.model === "qwen3.5:9b-mlx"));
  assert.ok(view.tasks.every((row) => row.model === "qwen3.5:9b-mlx"));
  assert.equal(view.funnel[0].profile, "smoke");
  assert.equal(JSON.stringify(fixture), before);
});

test("merges alternate datasets, deduplicates identical runs, and rejects collisions", () => {
  const alternate = alternateDataset();
  const merged = Core.mergeDashboardData([fixture, fixture, alternate]);
  assert.equal(merged.runs.length, fixture.runs.length + 1);
  assert.deepEqual(merged.profile_order, ["smoke", "standard", "full", "custom"]);
  assert.equal(merged.funnel.at(-1).profile, "custom");

  const collision = alternateDataset();
  collision.runs[0].id = fixture.runs[0].id;
  collision.funnel[0].run_ids = [fixture.runs[0].id];
  assert.throws(() => Core.mergeDashboardData([fixture, collision]), /collision/i);
});

test("rebuilds neutral funnel semantics", () => {
  const merged = Core.mergeDashboardData([fixture]);
  const smoke = merged.funnel.find((stage) => stage.profile === "smoke");
  assert.ok(smoke.continued_to_next.includes("qwen3.5:9b-mlx"));
  assert.ok(smoke.not_run_in_next.includes("gpt-oss:20b"));
  assert.equal(smoke.not_run_in_next.includes("qwen3.5:9b-mlx"), false);
  const view = Core.createDashboardView(merged, {});
  const uniqueDisqualified = new Set(
    merged.runs.flatMap((run) => run.integrity.disqualified_models)
  );
  assert.equal(view.summary.disqualifiedCount, uniqueDisqualified.size);
});

test("keeps Italian and English dictionaries synchronized", () => {
  assert.equal(I18n.validateDictionaries(), true);
  I18n.setLanguage("it");
  assert.match(I18n.translate("not_run_next"), /eseguit/i);
  I18n.setLanguage("en");
  assert.match(I18n.translate("not_run_next"), /not run/i);
});

test("committed classic-script snapshot reproduces the reviewed fixture", () => {
  const script = fs.readFileSync(path.join(ROOT, "dashboard/data/snapshot.js"), "utf8");
  const context = { window: {} };
  vm.runInNewContext(script, context, { filename: "snapshot.js" });
  assert.deepEqual(JSON.parse(JSON.stringify(context.window.LOCALAGENT_DASHBOARD_DATA)), fixture);
  assert.equal(context.window.LOCALAGENT_DASHBOARD_META.source, "snapshot");
});

test("official assets are semantic and contain no remote runtime hooks", () => {
  const files = ["dashboard/index.html", "dashboard/styles.css", "dashboard/js/app.js", "dashboard/js/ui.js"];
  const source = files.map((file) => fs.readFileSync(path.join(ROOT, file), "utf8")).join("\n");
  const html = fs.readFileSync(path.join(ROOT, "dashboard/index.html"), "utf8").toLowerCase();
  for (const token of ["<main", "<section", "<h1", "<label", 'type="file"', "aria-live", "skip-link", "<dialog"]) {
    assert.ok(html.includes(token), `missing ${token}`);
  }
  assert.doesNotMatch(source, /https?:\/\/|websocket|sendbeacon|xmlhttprequest|\bfetch\s*\(/i);
  assert.match(source, /@media/);
  assert.match(source, /:focus-visible/);
  assert.match(source, /prefers-color-scheme/);
  assert.match(source, /localStorage/);
});
