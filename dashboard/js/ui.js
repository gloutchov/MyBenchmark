(function (root, factory) {
  "use strict";
  const api = factory(root.LocalAgentDashboardI18n);
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (root) root.LocalAgentDashboardUI = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (I18n) {
  "use strict";

  const t = (key, values) => I18n.translate(key, values);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function formatNumber(value, digits) {
    if (typeof value !== "number" || !Number.isFinite(value)) return t("unknown");
    const locale = I18n.getLanguage() === "it" ? "it-IT" : "en-US";
    return new Intl.NumberFormat(locale, { maximumFractionDigits: digits === undefined ? 1 : digits }).format(value);
  }

  function formatDuration(value) {
    if (typeof value !== "number") return t("unknown");
    if (value < 60) return `${formatNumber(value, 1)} s`;
    const rounded = Math.round(value);
    const minutes = Math.floor(rounded / 60);
    const seconds = rounded % 60;
    return `${minutes} min ${seconds} s`;
  }

  function formatDate(value) {
    if (!value) return t("unknown");
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat(I18n.getLanguage() === "it" ? "it-IT" : "en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(parsed);
  }

  function stateLabel(state) {
    const labels = {
      passed: "passed",
      below_threshold: "below_threshold",
      timeout: "status_timeout",
      error: "status_error",
      missing_score: "status_missing",
      integrity_excluded: "status_excluded",
    };
    return t(labels[state] || "unknown");
  }

  function badge(text, kind) {
    return element("span", `badge badge-${kind || "neutral"}`, text);
  }

  function emptyState(key) {
    return element("p", "empty-state", t(key));
  }

  function applyStaticTranslations() {
    document.documentElement.lang = I18n.getLanguage();
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
      node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
    });
  }

  function renderSource(meta, view) {
    const source = meta && ["snapshot", "local", "import"].includes(meta.source) ? meta.source : "snapshot";
    document.getElementById("source-value").textContent = t(`source_${source}`);
    const dates = view.runs.map((run) => run.finished_at).filter(Boolean).sort();
    const latest = dates.length ? formatDate(dates[dates.length - 1]) : t("unknown");
    document.getElementById("source-meta").textContent = `${t("updated")}: ${latest} · ${t("source_privacy")}`;
  }

  function renderKpis(view) {
    const container = document.getElementById("kpis");
    const items = [
      ["runs", view.summary.runCount, "accent-blue"],
      ["models", view.summary.modelCount, "accent-cyan"],
      ["tasks", view.summary.taskCount, "accent-orange"],
      ["best_score", view.summary.bestScore === null ? t("unknown") : formatNumber(view.summary.bestScore, 1), "accent-green"],
    ];
    container.replaceChildren(
      ...items.map(([label, value, accent]) => {
        const card = element("article", `kpi-card ${accent}`);
        card.append(element("p", "kpi-label", t(label)), element("p", "kpi-value", value));
        if (label === "best_score" && view.summary.bestScore !== null) card.append(element("p", "kpi-note", t("score_suffix")));
        return card;
      })
    );
  }

  function renderIntegrity(view) {
    const container = document.getElementById("integrity-banner");
    const warning = view.summary.disqualifiedCount > 0;
    container.className = `integrity-banner ${warning ? "integrity-warning" : "integrity-ok"}`;
    const copy = element("div", "integrity-copy");
    copy.append(
      element("strong", "", t(warning ? "integrity_warning" : "integrity_ok")),
      element("span", "", warning ? t("integrity_detail", { count: view.summary.disqualifiedCount }) : "")
    );
    const counts = element("div", "outcome-counts");
    counts.append(
      badge(`${t("passed")}: ${view.summary.passedCount}`, "passed"),
      badge(`${t("below_threshold")}: ${view.summary.belowThresholdCount}`, "below"),
      badge(`${t("anomalies")}: ${view.summary.anomalousCount}`, "error")
    );
    container.replaceChildren(copy, counts);
  }

  function scoreCell(value) {
    const wrapper = element("div", "score-cell");
    wrapper.append(element("strong", "", formatNumber(value, 1)));
    if (typeof value === "number") {
      const track = element("span", "score-track");
      const fill = element("span", "score-fill");
      fill.style.width = `${Math.max(0, Math.min(100, value))}%`;
      track.append(fill);
      wrapper.append(track);
    }
    return wrapper;
  }

  function tableShell(headers) {
    const wrapper = element("div", "table-scroll");
    const table = element("table", "data-table");
    const head = document.createElement("thead");
    const row = document.createElement("tr");
    headers.forEach((header) => {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = t(header);
      row.append(cell);
    });
    head.append(row);
    const body = document.createElement("tbody");
    table.append(head, body);
    wrapper.append(table);
    return { wrapper, body };
  }

  function renderLeaderboard(view) {
    const container = document.getElementById("leaderboard");
    if (!view.leaderboard.length) {
      container.replaceChildren(emptyState("no_leaderboard"));
      return;
    }
    const { wrapper, body } = tableShell(["rank", "model", "profile", "overall", "quality", "completion", "duration"]);
    view.leaderboard.forEach((item, index) => {
      const row = document.createElement("tr");
      const position = document.createElement("td");
      position.textContent = String(index + 1);
      position.className = "rank-cell";
      const model = document.createElement("td");
      model.append(element("strong", "model-name", item.model), element("span", "run-id", item.run_id));
      const profile = document.createElement("td");
      profile.append(badge(item.profile, "profile"));
      const overall = document.createElement("td");
      overall.append(scoreCell(item.overall_score));
      const quality = document.createElement("td");
      quality.textContent = formatNumber(item.quality_score, 1);
      const completion = document.createElement("td");
      completion.textContent = typeof item.completion_rate === "number" ? `${formatNumber(item.completion_rate, 1)}%` : t("unknown");
      const duration = document.createElement("td");
      duration.textContent = formatDuration(item.median_duration_seconds);
      row.append(position, model, profile, overall, quality, completion, duration);
      body.append(row);
    });
    container.replaceChildren(wrapper);
  }

  function renderComparison(view) {
    const container = document.getElementById("comparison");
    if (!view.leaderboard.length) {
      container.replaceChildren(emptyState("no_leaderboard"));
      return;
    }
    const rows = [...view.leaderboard]
      .sort((left, right) => (right.overall_score ?? -1) - (left.overall_score ?? -1))
      .slice(0, 6);
    const metrics = [
      ["quality", "quality_score", "bar-blue"],
      ["completion", "completion_rate", "bar-green"],
      ["speed", "speed_score", "bar-orange"],
      ["token_efficiency", "token_efficiency_score", "bar-cyan"],
    ];
    const list = element("div", "comparison-list");
    rows.forEach((row) => {
      const card = element("article", "comparison-row");
      const heading = element("div", "comparison-model");
      heading.append(element("strong", "model-name", row.model), badge(row.profile, "profile"));
      card.append(heading);
      metrics.forEach(([label, key, color]) => {
        const metric = element("div", "metric-row");
        const caption = element("span", "metric-label", t(label));
        const track = element("span", "metric-track");
        const fill = element("span", `metric-fill ${color}`);
        const value = typeof row[key] === "number" ? Math.max(0, Math.min(100, row[key])) : 0;
        fill.style.width = `${value}%`;
        track.append(fill);
        metric.append(caption, track, element("span", "metric-value", formatNumber(row[key], 0)));
        card.append(metric);
      });
      list.append(card);
    });
    container.replaceChildren(list);
  }

  function modelList(models) {
    const list = element("ul", "model-list");
    models.forEach((model) => list.append(element("li", "", model)));
    return list;
  }

  function renderFunnel(view) {
    const container = document.getElementById("funnel");
    if (!view.funnel.length) {
      container.replaceChildren(emptyState("no_funnel"));
      return;
    }
    const grid = element("div", "funnel-grid");
    view.funnel.forEach((stage, index) => {
      const wrapper = element("div", "funnel-stage-wrap");
      const stageNode = element("article", "funnel-stage");
      const heading = element("div", "stage-heading");
      heading.append(element("span", "stage-number", String(index + 1).padStart(2, "0")), element("h3", "", stage.profile));
      stageNode.append(heading);
      const participantTitle = element("p", "stage-label", `${t("participants")} · ${stage.participants.length}`);
      stageNode.append(participantTitle, modelList(stage.participants));
      if (stage.next_profile) {
        const transition = element("div", "transition-summary");
        transition.append(
          badge(`${t("continued")}: ${stage.continued_to_next.length}`, "passed"),
          badge(`${t("not_run_next")}: ${stage.not_run_in_next.length}`, "neutral")
        );
        stageNode.append(transition);
      } else {
        stageNode.append(element("p", "final-stage", t("final_stage")));
      }
      if (stage.new_participants.length && index > 0) {
        stageNode.append(element("p", "stage-note", `${t("new_participants")}: ${stage.new_participants.join(", ")}`));
      }
      wrapper.append(stageNode);
      if (index < view.funnel.length - 1) wrapper.append(element("span", "funnel-arrow", "→"));
      grid.append(wrapper);
    });
    container.replaceChildren(grid);
  }

  function renderTasks(view, onDetails) {
    const container = document.getElementById("tasks");
    if (!view.tasks.length) {
      container.replaceChildren(emptyState("no_tasks"));
      return;
    }
    const { wrapper, body } = tableShell(["model", "case", "profile", "state", "overall", "duration", "output_tokens", "actions"]);
    view.tasks.forEach((task) => {
      const row = document.createElement("tr");
      const model = document.createElement("td");
      model.append(element("strong", "model-name", task.model));
      const caseCell = document.createElement("td");
      const title = I18n.getLanguage() === "it" ? task.case_title : task.case_title_en;
      caseCell.append(element("span", "task-title", title), element("span", "run-id", task.case_id));
      const profile = document.createElement("td");
      profile.append(badge(task.profile, "profile"));
      const state = document.createElement("td");
      const stateKind = task.state === "passed" ? "passed" : task.state === "below_threshold" ? "below" : "error";
      state.append(badge(stateLabel(task.state), stateKind));
      const score = document.createElement("td");
      score.textContent = formatNumber(task.score, 1);
      const duration = document.createElement("td");
      duration.textContent = formatDuration(task.duration_seconds);
      const tokens = document.createElement("td");
      tokens.textContent = formatNumber(task.output_tokens, 0);
      const actions = document.createElement("td");
      const button = element("button", "detail-button", t("details"));
      button.type = "button";
      button.addEventListener("click", () => onDetails(task));
      actions.append(button);
      row.append(model, caseCell, profile, state, score, duration, tokens, actions);
      body.append(row);
    });
    container.replaceChildren(wrapper);
  }

  function renderRuns(view) {
    const container = document.getElementById("run-list");
    container.replaceChildren(
      ...view.runs.map((run) => {
        const details = element("details", "run-card");
        const summary = document.createElement("summary");
        const title = element("span", "run-summary-main");
        title.append(element("strong", "", run.id), badge(run.profile, "profile"));
        summary.append(title, element("span", "run-date", formatDate(run.finished_at)));
        const grid = element("dl", "metadata-grid");
        const entries = [
          ["benchmark_version", run.benchmark_version],
          ["sandbox", `${run.sandbox.backend} · ${t(run.sandbox.enforced ? "enforced" : "not_enforced")}`],
          ["integrity", run.integrity.status],
          ["models", run.participants.length],
          ["commit", run.provenance.repository_commit ? run.provenance.repository_commit.slice(0, 12) : t("unknown")],
        ];
        entries.forEach(([label, value]) => {
          grid.append(element("dt", "", t(label)), element("dd", "", value));
        });
        details.append(summary, grid);
        return details;
      })
    );
  }

  function showTaskDialog(task) {
    const dialog = document.getElementById("task-dialog");
    const title = I18n.getLanguage() === "it" ? task.case_title : task.case_title_en;
    document.getElementById("dialog-title").textContent = title;
    const content = document.getElementById("dialog-content");
    const grid = element("dl", "dialog-grid");
    const entries = [
      ["model", task.model],
      ["profile", task.profile],
      ["run", task.run_id],
      ["state", stateLabel(task.state)],
      ["status", task.status],
      ["overall", formatNumber(task.score, 1)],
      ["max_score", formatNumber(task.max_score, 1)],
      ["repetition", task.repetition],
      ["duration", formatDuration(task.duration_seconds)],
      ["output_tokens", formatNumber(task.output_tokens, 0)],
      ["tool_calls", formatNumber(task.tool_calls, 0)],
      ["tool_errors", formatNumber(task.tool_errors, 0)],
      ["cpu", typeof task.cpu_seconds === "number" ? `${formatNumber(task.cpu_seconds, 2)} s` : t("unknown")],
      ["energy", typeof task.energy_joules === "number" ? `${formatNumber(task.energy_joules, 1)} J` : t("unknown")],
      ["integrity_valid", task.integrity_valid === null ? t("unknown") : t(task.integrity_valid ? "yes" : "no")],
    ];
    entries.forEach(([label, value]) => grid.append(element("dt", "", t(label)), element("dd", "", value)));
    content.replaceChildren(grid);
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  return {
    applyStaticTranslations,
    renderComparison,
    renderFunnel,
    renderIntegrity,
    renderKpis,
    renderLeaderboard,
    renderRuns,
    renderSource,
    renderTasks,
    showTaskDialog,
  };
});
