/*
 * RRKAL Web Preview frontend.
 *
 * This file is intentionally a UI adapter. Backend services decide crawler
 * readiness, credential gates, download-plan outcomes, seed paging, and import
 * status. JavaScript keeps temporary screen state, calls JSON endpoints, and
 * renders the backend display contracts.
 */

// Page-level state mirrors backend payloads for rendering only. The maps below
// should not become a second source of business truth; refresh actions must call
// the API again.
let assets = [];
let selectedAssetId = "";
let selectedAssetDetail = null;
let selectedSourceType = "all";
let activeWorkspace = "assets";
let latestAdapterReview = null;
let recentEvents = [];
let missions = [];
let projectMaturity = null;
let crawlerAssetDownloadImportResult = null;
const assetPlanOutcomes = new Map();
const assetPlanPassports = new Map();
const assetListingOutcomes = new Map();
const autoEnumeratedAssetIds = new Set();
const assetSeedPages = new Map();
const favoriteSeedUids = new Set();
const defaultSeedEnumerationRequest = Object.freeze({
  listing_mode: "complete_seed",
  max_results: 1000,
  max_pages: 0,
});
const seedPageSize = 50;

// DOM anchors are collected once at startup. Most render functions below are
// pure-ish transformations from current state to HTML fragments.
const assetGrid = document.querySelector("#assetGrid");
const assetFilter = document.querySelector("#assetFilter");
const healthFilter = document.querySelector("#healthFilter");
const sourceTypeFilters = document.querySelector("#sourceTypeFilters");
const sourceTypeCount = document.querySelector("#sourceTypeCount");
const passport = document.querySelector("#passport");
const boundsForm = document.querySelector("#boundsForm");
const formState = document.querySelector("#formState");
const contentReviewBadge = document.querySelector("#contentReviewBadge");
const resultJson = document.querySelector("#resultJson");
const serverState = document.querySelector("#serverState");
const assetCount = document.querySelector("#assetCount");
const healthyCount = document.querySelector("#healthyCount");
const needsBoundsCount = document.querySelector("#needsBoundsCount");
const visibleCount = document.querySelector("#visibleCount");
const missionCount = document.querySelector("#missionCount");
const missionQueue = document.querySelector("#missionQueue");
const selectedHero = document.querySelector("#selectedHero");
const payloadPreviewButton = document.querySelector("#payloadPreviewButton");
const buildPlanButton = document.querySelector("#buildPlanButton");
const refreshButton = document.querySelector("#refreshButton");
const copyJsonButton = document.querySelector("#copyJsonButton");
const workspaceButtons = document.querySelectorAll("[data-workspace]");
const workspacePanels = document.querySelectorAll("[data-workspace-panel]");
const crawlerAssetDownloadButton = document.querySelector("#crawlerAssetDownloadButton");
const downloaderRefreshButton = document.querySelector("#downloaderRefreshButton");
const downloaderQueue = document.querySelector("#downloaderQueue");
const reviewReturnButton = document.querySelector("#reviewReturnButton");
const reviewSummary = document.querySelector("#reviewSummary");
const maturityRefreshButton = document.querySelector("#maturityRefreshButton");
const maturitySummary = document.querySelector("#maturitySummary");
const maturityGrid = document.querySelector("#maturityGrid");
const eventRefreshButton = document.querySelector("#eventRefreshButton");
const eventList = document.querySelector("#eventList");

refreshButton.addEventListener("click", loadAssets);
assetFilter.addEventListener("input", renderAssetGrid);
healthFilter.addEventListener("change", renderAssetGrid);
payloadPreviewButton.addEventListener("click", () => submitBounds(false));
buildPlanButton.addEventListener("click", handleBuildPlanClick);
copyJsonButton.addEventListener("click", copyJson);
workspaceButtons.forEach((button) => button.addEventListener("click", () => showWorkspace(button.dataset.workspace)));
crawlerAssetDownloadButton.addEventListener("click", () => runCrawlerAssetDownloadImportById(selectedAssetId));
downloaderRefreshButton.addEventListener("click", renderDownloaderWorkspace);
reviewReturnButton.addEventListener("click", () => showWorkspace("assets"));
maturityRefreshButton.addEventListener("click", () => loadProjectMaturity());
eventRefreshButton.addEventListener("click", () => loadRecentEvents());

loadAssets();
renderMissionQueue();
showWorkspace(activeWorkspace);

async function loadAssets(options = {}) {
  // Main refresh path: health -> asset cards -> filters -> selected asset
  // detail. Auto-enumeration is guarded so reloads do not repeatedly crawl.
  const autoEnumerateSelected = options.autoEnumerateSelected !== false;
  setServerState("讀取中", "neutral");
  try {
    const health = await getJson("/api/health");
    const payload = await getJson("/api/crawler-assets");
    assets = payload.assets || [];
    await loadProjectMaturity({ quiet: true });
    selectedSourceType = selectedSourceTypeStillExists() ? selectedSourceType : "all";
    renderOverview(health);
    renderHealthFilter();
    renderSourceTypeFilters();
    renderAssetGrid();
    renderDownloaderWorkspace();
    renderReviewWorkspace();
    addMission("Web Preview 已連線", `讀取 ${assets.length} 個 crawler asset / ${serverRuntimeLabel(health)}`);
    if (!selectedAssetId && assets.length) {
      await selectAsset(assets[0].asset_id, { autoEnumerate: autoEnumerateSelected });
    } else if (selectedAssetId) {
      await selectAsset(selectedAssetId, { autoEnumerate: autoEnumerateSelected });
    }
  } catch (error) {
    setServerState("讀取失敗", "danger");
    writeJson({ error: String(error) });
  }
}

function renderOverview(health) {
  const healthCounts = countBy(assets, (asset) => asset.health?.status_code || "unknown");
  assetCount.textContent = String(assets.length);
  healthyCount.textContent = String(healthCounts.healthy || 0);
  needsBoundsCount.textContent = String(healthCounts.needs_bounds || 0);
  setServerState(serverRuntimeLabel(health), "success", serverRuntimeTitle(health));
}

function serverRuntimeLabel(health) {
  const server = health?.server || {};
  if (server.host && server.port) {
    return `${server.host}:${server.port}`;
  }
  return `${health?.surface || "web_preview"}`;
}

function serverRuntimeTitle(health) {
  const server = health?.server || {};
  if (!server.port) {
    return "";
  }
  if (server.port_scanned) {
    return `原定 port ${server.requested_port} 已被占用，Web Preview 改用 ${server.port}。`;
  }
  return `Web Preview 使用預設 port ${server.port}。`;
}

function renderHealthFilter() {
  const selected = healthFilter.value || "all";
  const statuses = Object.keys(countBy(assets, (asset) => asset.health?.status_code || "unknown")).sort();
  healthFilter.innerHTML = '<option value="all">全部</option>';
  for (const status of statuses) {
    healthFilter.appendChild(new Option(statusLabel(status), status));
  }
  healthFilter.value = statuses.includes(selected) ? selected : "all";
}

function renderSourceTypeFilters() {
  const counts = Object.entries(countBy(assets, (asset) => asset.source_type || "unknown"))
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  sourceTypeCount.textContent = String(counts.length);
  const buttons = [
    filterButton("all", "全部範式", assets.length),
    ...counts.map(([type, count]) => filterButton(type, type, count)),
  ];
  sourceTypeFilters.innerHTML = buttons.join("");
  sourceTypeFilters.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      selectedSourceType = button.dataset.sourceType;
      renderSourceTypeFilters();
      renderAssetGrid();
    });
  });
}

function filterButton(type, label, count) {
  const active = selectedSourceType === type ? " active" : "";
  return `
    <button class="filter-chip${active}" type="button" data-source-type="${escapeHtml(type)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(count))}</strong>
    </button>
  `;
}

function renderAssetGrid() {
  const visible = filteredAssets();
  visibleCount.textContent = String(visible.length);
  assetGrid.innerHTML = "";
  if (!visible.length) {
    assetGrid.innerHTML = `
      <div class="empty-state wide">
        <strong>沒有符合條件的爬蟲資產</strong>
        <p>請清除搜尋字串或切回全部範式。</p>
      </div>
    `;
    return;
  }
  for (const asset of visible) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `asset-slot ${asset.asset_id === selectedAssetId ? "selected" : ""}`;
    button.addEventListener("click", () => selectAsset(asset.asset_id));
    button.addEventListener("dblclick", () => prepareOpenCommand(asset));
    button.innerHTML = assetSlotHtml(asset);
    assetGrid.appendChild(button);
  }
}

function showWorkspace(name) {
  // Workspaces are presentation tabs. Switching tabs should not mutate backend
  // state; it only rerenders the relevant cached payloads.
  activeWorkspace = name || "assets";
  workspaceButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.workspace === activeWorkspace);
  });
  workspacePanels.forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.workspacePanel !== activeWorkspace);
  });
  if (activeWorkspace === "downloader") {
    renderDownloaderWorkspace();
  } else if (activeWorkspace === "review") {
    renderReviewWorkspace();
  } else if (activeWorkspace === "maturity") {
    loadProjectMaturity({ quiet: true });
  } else if (activeWorkspace === "events") {
    loadRecentEvents({ quiet: true });
  }
}

async function loadProjectMaturity(options = {}) {
  if (!maturityGrid || !maturitySummary) return;
  try {
    projectMaturity = await getJson("/api/project-maturity");
    renderMaturityWorkspace();
    if (!options.quiet) {
      addMission("成熟度矩陣已讀取", projectMaturity.matrix_version || "project maturity");
      writeJson(projectMaturity);
    }
  } catch (error) {
    maturitySummary.innerHTML = `<div class="empty-state wide"><strong>成熟度讀取失敗</strong><p>${escapeHtml(String(error))}</p></div>`;
    if (!options.quiet) writeJson({ error: String(error), endpoint: "project_maturity" });
  }
}

function renderMaturityWorkspace() {
  if (!maturityGrid || !maturitySummary) return;
  const payload = projectMaturity || {};
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const closure = payload.canonical_delivery_scope || {};
  maturitySummary.innerHTML = `
    <section class="maturity-summary-card">
      <span class="eyebrow">Delivery Scope</span>
      <strong>${escapeHtml(String(closure.closure_percent ?? "unknown"))}% / ${escapeHtml(closure.status || "unknown")}</strong>
      <p>${escapeHtml(payload.answer_template_zh_TW || payload.reporting_rule || "請使用成熟度矩陣，不要用單一百分比描述整體產品。")}</p>
    </section>
  `;
  if (!rows.length) {
    maturityGrid.innerHTML = `
      <div class="empty-state wide">
        <strong>尚無成熟度列</strong>
        <p>後端沒有回傳 rows；請檢查 project maturity JSON。</p>
      </div>
    `;
    return;
  }
  maturityGrid.innerHTML = rows.map((row) => maturityCardHtml(row)).join("");
}

function maturityCardHtml(row) {
  const tone = toneClass(row.display_tone || row.display_profile?.display_tone || "neutral");
  const icon = row.status_icon || row.display_profile?.status_icon || "?";
  const limitations = Array.isArray(row.current_limitations) ? row.current_limitations : [];
  const nextActions = Array.isArray(row.next_actions) ? row.next_actions : [];
  return `
    <article class="maturity-card ${tone}">
      <div class="maturity-card-head">
        <span class="maturity-icon" aria-hidden="true">${escapeHtml(icon)}</span>
        <div>
          <strong>${escapeHtml(row.area_label || row.area_id || "maturity area")}</strong>
          <span>${escapeHtml(row.display_label || row.maturity_label_zh_TW || row.maturity_level || "unknown")}</span>
        </div>
      </div>
      <p>${escapeHtml(row.deliverable_scope || "")}</p>
      ${limitations.length ? `<ul>${limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
      ${nextActions.length ? `<footer>${escapeHtml(nextActions[0])}</footer>` : ""}
    </article>
  `;
}

function renderDownloaderWorkspace() {
  if (!downloaderQueue) return;
  const queueAssets = assets.filter((asset) => (
    hasPlanOutcomeBadge(latestPlanOutcomeForAsset(asset)) || hasPlanPassport(latestPlanPassportForAsset(asset))
  ));
  const rows = [];
  if (crawlerAssetDownloadImportResult) {
    rows.push(crawlerAssetDownloadImportRowHtml(crawlerAssetDownloadImportResult));
  }
  rows.push(...queueAssets.map((asset) => downloaderRowHtml(asset)));
  if (!rows.length) {
    downloaderQueue.innerHTML = `
      <div class="empty-state wide">
        <strong>尚無下載計畫結果</strong>
        <p>先在爬蟲資產分頁輸入界域並建立下載計畫；這裡會顯示後端回傳的 plan outcome / passport。</p>
      </div>
    `;
    return;
  }
  downloaderQueue.innerHTML = rows.join("");
}

async function runCrawlerAssetDownloadImportById(assetId) {
  // Formal asset-level path: bounds form values -> backend resolved plan ->
  // download/import pipeline. This is not the old public CSV demo route.
  if (!assetId) {
    addMission("請先選擇爬蟲資產", "下載 / 匯入需要一個已選取的入口資產。");
    return;
  }
  if (!crawlerAssetDownloadButton) return;
  const asset = assets.find((item) => item.asset_id === assetId);
  const originalText = crawlerAssetDownloadButton.textContent;
  crawlerAssetDownloadButton.disabled = true;
  crawlerAssetDownloadButton.textContent = "下載中...";
  addMission("正式下載 / 匯入開始", asset?.display_name || assetId);
  try {
    if (selectedAssetId !== assetId) {
      await selectAsset(assetId, { autoEnumerate: false });
    }
    const payload = await postJson(
      `/api/crawler-assets/${encodeURIComponent(assetId)}/download-import`,
      currentBoundsFormValues(),
    );
    crawlerAssetDownloadImportResult = payload;
    writeJson(payload);
    if (payload.plan_outcome) {
      rememberAssetPlanOutcome(assetId, payload.plan_outcome);
      rememberAssetPlanPassport(assetId, payload.plan_passport);
    }
    if (payload.adapter_review) {
      latestAdapterReview = payload.adapter_review;
      renderReviewWorkspace();
    }
    const downloadImport = payload.download_import || {};
    if (downloadImport.succeeded) {
      addMission("正式下載 / 匯入完成", `${downloadImport.stage || "completed"} / ${asset?.display_name || assetId}`);
    } else {
      addMission("正式下載 / 匯入未完成", downloadImportNextActionText(payload, downloadImport));
    }
    addCallbackDiagnosticsMission(payload);
    renderDownloaderWorkspace();
    refreshSelectedAssetOutcomeViews();
    loadRecentEvents({ quiet: true });
  } catch (error) {
    writeJson({ error: String(error), endpoint: "crawler_asset_download_import", asset_id: assetId });
    addMission("正式下載 / 匯入失敗", String(error));
  } finally {
    crawlerAssetDownloadButton.disabled = false;
    crawlerAssetDownloadButton.textContent = originalText;
  }
}

async function runCrawlerSeedDownloadImportById(assetId, datasetUid) {
  // Seed-level path acts on one catalog seed row that the user can see. It does
  // not rerun source discovery; the backend validates seed ownership.
  if (!assetId || !datasetUid) {
    addMission("請先選擇 seed", "seed 下載 / 匯入需要一個已枚舉的 dataset_uid。");
    return;
  }
  const asset = assets.find((item) => item.asset_id === assetId);
  addMission("seed 下載 / 匯入開始", `${asset?.display_name || assetId} / ${datasetUid}`);
  try {
    if (selectedAssetId !== assetId) {
      await selectAsset(assetId, { autoEnumerate: false });
    }
    const payload = await postJson(
      `/api/crawler-assets/${encodeURIComponent(assetId)}/seed-download-import`,
      {
        ...currentBoundsFormValues(),
        dataset_uid: datasetUid,
      },
    );
    crawlerAssetDownloadImportResult = payload;
    writeJson(payload);
    if (payload.plan_outcome) {
      rememberAssetPlanOutcome(assetId, payload.plan_outcome);
      rememberAssetPlanPassport(assetId, payload.plan_passport);
    }
    if (payload.adapter_review) {
      latestAdapterReview = payload.adapter_review;
      renderReviewWorkspace();
    }
    const downloadImport = payload.download_import || {};
    if (downloadImport.succeeded) {
      addMission("seed 下載 / 匯入完成", `${downloadImport.stage || "completed"} / ${datasetUid}`);
    } else {
      addMission("seed 下載 / 匯入未完成", downloadImportNextActionText(payload, downloadImport));
    }
    addCallbackDiagnosticsMission(payload);
    renderDownloaderWorkspace();
    refreshSelectedAssetOutcomeViews();
    loadRecentEvents({ quiet: true });
  } catch (error) {
    writeJson({ error: String(error), endpoint: "crawler_seed_download_import", asset_id: assetId, dataset_uid: datasetUid });
    addMission("seed 下載 / 匯入失敗", String(error));
  }
}

async function runSeedSchemaProbeById(assetId, datasetUid) {
  // Seed probe is a UI convenience wrapper over the backend schema-probe
  // endpoint. It picks a visible seed URL, but the backend still owns column
  // inference and bounds-form enrichment.
  if (!assetId || !datasetUid) {
    addMission("請先選擇 seed", "欄位探測需要一筆已枚舉 seed。");
    return;
  }
  const seed = findVisibleSeed(assetId, datasetUid);
  const entry = schemaProbeEntryForSeed(seed);
  if (!Object.keys(entry).length) {
    addMission("seed 缺少可探測 URL", datasetUid);
    writeJson({ asset_id: assetId, dataset_uid: datasetUid, next_action: "choose_seed_with_api_url" });
    return;
  }
  addMission("探測 seed 欄位", `${assetId} / ${datasetUid}`);
  try {
    if (selectedAssetId !== assetId) {
      await selectAsset(assetId, { autoEnumerate: false });
    }
    const payload = await postJson(
      `/api/crawler-assets/${encodeURIComponent(assetId)}/bounds-form/schema-probe`,
      { entry, row_limit: 5 },
    );
    if (selectedAssetDetail?.card?.asset_id === assetId) {
      selectedAssetDetail.bound_form = payload.bound_form;
    }
    renderBoundsForm(payload.bound_form);
    writeJson(payload);
    addMission("欄位探測完成", payload.next_action_label || payload.bound_form?.display_label || "欄位探測完成");
  } catch (error) {
    writeJson({ error: String(error), endpoint: "seed_schema_probe", asset_id: assetId, dataset_uid: datasetUid, entry });
    addMission("欄位探測失敗", String(error));
  }
}

function currentBoundsFormValues() {
  const values = {};
  if (!boundsForm) return values;
  for (const element of boundsForm.elements) {
    if (element.name) {
      values[element.name] = element.value;
    }
  }
  return values;
}

function crawlerAssetDownloadImportRowHtml(payload) {
  const result = payload.download_result || {};
  const artifacts = result.artifacts || {};
  const downloadImport = payload.download_import || result.download_import || {};
  const succeeded = Boolean(downloadImport.succeeded || result.succeeded);
  const tone = succeeded ? "success" : "warning";
  const label = succeeded ? "下載 / 匯入完成" : "需要檢查";
  const callbackDiagnostics = downloadImportCallbackDiagnostics(payload);
  const callbackChip = callbackDiagnostics.count
    ? `<span class="context-chip warning">${escapeHtml(callbackDiagnostics.displayLabel)} ${escapeHtml(String(callbackDiagnostics.count))}</span>`
    : "";
  return `
    <article class="download-row ${tone}">
      <div class="download-row-head">
        <div>
          <span class="eyebrow">Crawler Asset Download</span>
          <strong>${escapeHtml(payload.asset_id || result.asset_id || "crawler asset")}</strong>
        </div>
        <span class="plan-badge ${tone}">${escapeHtml(label)}</span>
      </div>
      <div class="queue-metrics">
        ${heroMetric("Stage", downloadImportStageText(downloadImport, result))}
        ${heroMetric("Submitted", downloadImport.result?.submitted || 0)}
        ${heroMetric("Completed", downloadImport.result?.completed || 0)}
        ${heroMetric("Imported", downloadImport.result?.imported || 0)}
        ${heroMetric("SQLite", artifacts.curated_sqlite ? "OK" : "-")}
      </div>
      <div class="context-chip-row">
        <span class="context-chip">crawler_asset_path</span>
        <span class="context-chip">download_import_pipeline</span>
        <span class="context-chip">${escapeHtml(planOutcomeLabel(payload.plan_outcome, null, "計畫狀態"))}</span>
        ${callbackChip}
      </div>
      <p>${escapeHtml(downloadImportNextActionText(payload, downloadImport))}</p>
      ${callbackDiagnosticsHtml(callbackDiagnostics)}
      <dl class="artifact-list">
        <div><dt>Downloads</dt><dd>${escapeHtml(artifacts.downloads_root || "")}</dd></div>
        <div><dt>Plan</dt><dd>${escapeHtml(artifacts.plan || "")}</dd></div>
        <div><dt>SQLite</dt><dd>${escapeHtml(artifacts.curated_sqlite || "")}</dd></div>
      </dl>
    </article>
  `;
}

function downloadImportNextActionText(payload, downloadImport = {}) {
  return payload.next_action_label || downloadImport.next_action_label || "檢查下載 / 匯入結果";
}

function downloadImportStageText(downloadImport = {}, result = {}) {
  return displayTextOrFallback(
    "下載狀態待確認",
    downloadImport.stage_label,
    downloadImport.display_stage_label,
    result.stage_label,
    result.display_stage_label,
  );
}

function downloadImportCallbackDiagnostics(payload) {
  const downloadImport = payload.download_import || {};
  const diagnostics = payload.callback_diagnostics || downloadImport.callback_diagnostics || {};
  const errors = Array.isArray(diagnostics.errors)
    ? diagnostics.errors
    : Array.isArray(downloadImport.callback_errors)
      ? downloadImport.callback_errors
      : [];
  const count = Number(diagnostics.count || downloadImport.callback_error_count || errors.length || 0);
  return {
    count: Number.isFinite(count) ? count : 0,
    displayLabel: diagnostics.display_label || (count ? "進度回報有警告" : "進度回報正常"),
    nextActionLabel: diagnostics.next_action_label || "",
    summary: diagnostics.summary || "",
    errors,
  };
}

function callbackDiagnosticsHtml(diagnostics) {
  if (!diagnostics.count) return "";
  const errorPreview = diagnostics.errors.slice(0, 2).join(" / ");
  return `
    <p class="callback-diagnostics">
      ${escapeHtml(diagnostics.displayLabel)}：${escapeHtml(diagnostics.nextActionLabel || diagnostics.summary || "檢查事件紀錄或 UI 進度回報")}
      ${errorPreview ? `<br><small>${escapeHtml(errorPreview)}</small>` : ""}
    </p>
  `;
}

function addCallbackDiagnosticsMission(payload) {
  const diagnostics = downloadImportCallbackDiagnostics(payload);
  if (!diagnostics.count) return;
  addMission(
    diagnostics.displayLabel,
    diagnostics.nextActionLabel || diagnostics.summary || "檢查事件紀錄或 UI 進度回報",
  );
}

function downloaderRowHtml(asset) {
  const outcome = latestPlanOutcomeForAsset(asset) || {};
  const passport = latestPlanPassportForAsset(asset) || {};
  const tone = toneClass(outcome.display_tone || passport.display_tone);
  const label = planOutcomeLabel(outcome, passport, "計畫結果");
  const nextAction = displayTextOrFallback(
    "等待後端下一步",
    outcome.next_action_label,
    passport.next_action_label,
    asset.next_action_label,
    passport.next_action,
    asset.next_action,
  );
  const contentReview = outcome.content_review?.has_review || passport.content_review_count
    ? `<span class="context-chip warning">內容待辦 ${escapeHtml(String(outcome.content_review?.count || passport.content_review_count || 0))}</span>`
    : "";
  const staleChip = passport.stale
    ? `<span class="context-chip warning">${escapeHtml(stalePassportLabel(passport))}</span>`
    : "";
  const snapshotChip = passport.candidate_snapshot_changed
    ? `<span class="context-chip warning">候選快照已變更</span>`
    : "";
  return `
    <article class="download-row ${tone}">
      <div class="download-row-head">
        <div>
          <span class="eyebrow">Download Plan</span>
          <strong>${escapeHtml(asset.display_name)}</strong>
        </div>
        <span class="plan-badge ${tone}">${escapeHtml(label)}</span>
      </div>
      <div class="queue-metrics">
        ${heroMetric("Candidates", passport.candidate_count || 0)}
        ${heroMetric("Direct", passport.direct_download_count || outcome.direct_download_count || 0)}
        ${heroMetric("Review", passport.review_required_count || outcome.review_required_count || 0)}
        ${heroMetric("Adapter", passport.adapter_review_count || 0)}
      </div>
      <div class="context-chip-row">
        <span class="context-chip">${escapeHtml(shortPattern(asset.source_type))}</span>
        <span class="context-chip">${escapeHtml(asset.provider_id || "provider unknown")}</span>
        ${contentReview}
        ${staleChip}
        ${snapshotChip}
      </div>
      <p>${escapeHtml(nextAction)}</p>
      <div class="download-row-actions">
        <button type="button" class="primary-button" onclick="runCrawlerAssetDownloadImportById('${escapeAttr(asset.asset_id)}')">下載 / 匯入</button>
        <button type="button" class="secondary-button" onclick="focusAssetFromWorkspace('${escapeAttr(asset.asset_id)}')">檢視資產</button>
      </div>
    </article>
  `;
}

async function focusAssetFromWorkspace(assetId) {
  await selectAsset(assetId);
  showWorkspace("assets");
}

async function loadSeedPage(assetId, page = 1, { append = false } = {}) {
  // Read already-enumerated local catalog seeds. "Show more" appends another
  // local page; live remote completeness is shown through listing metadata.
  const payload = await getJson(`/api/crawler-assets/${encodeURIComponent(assetId)}/seeds?page=${page}&page_size=${seedPageSize}`);
  rememberSeedFavorites(payload.seeds || []);
  if (append && assetSeedPages.has(assetId)) {
    const previous = assetSeedPages.get(assetId);
    const previousRecommendation = previous.recommended_seed_uid
      ? {
          recommended_seed: previous.recommended_seed,
          recommended_seed_uid: previous.recommended_seed_uid,
          recommended_seed_next_action: previous.recommended_seed_next_action,
        }
      : {};
    assetSeedPages.set(assetId, {
      ...payload,
      ...previousRecommendation,
      seeds: [...(previous.seeds || []), ...(payload.seeds || [])],
    });
  } else {
    assetSeedPages.set(assetId, payload);
  }
  if (selectedAssetDetail?.card?.asset_id === assetId) {
    renderPassport(selectedAssetDetail.card, selectedAssetDetail.asset);
    renderSelectedHero(selectedAssetDetail.card, selectedAssetDetail.flow_steps || []);
  }
  return payload;
}

async function showMoreSeeds(assetId) {
  const current = assetSeedPages.get(assetId) || { page: 0, seeds: [] };
  try {
    await loadSeedPage(assetId, Number(current.page || 0) + 1, { append: true });
  } catch (error) {
    writeJson({ error: String(error), endpoint: "seeds", asset_id: assetId });
    addMission("seed 清單展開失敗", String(error));
  }
}

async function runCrawlerAssetListingById(assetId, options = {}) {
  // Explicit seed enumeration. This is the crawler/listing action and the only
  // place this frontend asks the backend to refresh local seed candidates.
  const asset = assets.find((item) => item.asset_id === assetId);
  const request = options.request || defaultSeedEnumerationRequest;
  addMission(options.auto ? "自動枚舉 seed" : "重新枚舉 seed", asset?.display_name || assetId);
  try {
    const payload = await postJson(`/api/crawler-assets/${encodeURIComponent(assetId)}/list-datasets`, request);
    writeJson(payload);
    const result = payload.listing_result || {};
    rememberCrawlerAssetListing(assetId, result);
    if (result.blocked && payload.next_action === "edit_local_credentials_before_live_download") {
      addMission("需要登入才能枚舉 seed", asset?.display_name || assetId);
      openCredentialEditorById(assetId);
      return;
    }
    addMission(
      "seed 枚舉完成",
      displayTextOrFallback("檢查 seed 枚舉結果", seedEnumerationDetail(result), payload.next_action_label, payload.next_action),
    );
    loadRecentEvents({ quiet: true });
    await loadAssets({ autoEnumerateSelected: false });
    await selectAsset(assetId, { autoEnumerate: false });
    await loadSeedPage(assetId, 1);
  } catch (error) {
    writeJson({ error: String(error), endpoint: "list_datasets", asset_id: assetId });
    addMission("seed 枚舉失敗", String(error));
  }
}

function renderReviewWorkspace() {
  if (!reviewSummary) return;
  if (!latestAdapterReview?.item_count) {
    reviewSummary.innerHTML = `
      <div class="empty-state wide">
        <strong>尚無匯入審核結果</strong>
        <p>建立下載計畫後，如果後端判斷需要 adapter 或 content parser review，摘要會出現在這裡。</p>
      </div>
    `;
    return;
  }
  const outcomes = latestAdapterReview.outcomes || [];
  const buckets = latestAdapterReview.content_review_buckets || [];
  const parsers = latestAdapterReview.content_parsers || [];
  const lanes = latestAdapterReview.content_pipeline_lanes || [];
  reviewSummary.innerHTML = `
    <section class="review-card">
      <span class="eyebrow">Adapter Review</span>
      <strong>${escapeHtml(String(latestAdapterReview.item_count))} 筆需要審核</strong>
      <div class="context-chip-row">
        ${outcomes.map((outcome) => `<span class="context-chip">${escapeHtml(reviewOutcomeLabel(outcome))} ${escapeHtml(String(outcome.count || 0))}</span>`).join("")}
      </div>
    </section>
    <section class="review-card">
      <span class="eyebrow">Content Parser</span>
      <strong>${escapeHtml(contentReviewText(buckets))}</strong>
      <div class="context-chip-row">
        ${buckets.map((bucket) => `<span class="context-chip warning">${escapeHtml(contentReviewBucketLabel(bucket))} ${escapeHtml(String(bucket.count || 0))}</span>`).join("") || '<span class="context-chip">無內容格式待辦</span>'}
      </div>
    </section>
    <section class="review-card">
      <span class="eyebrow">Parser Registry</span>
      <strong>${escapeHtml(String(parsers.length))} 種 parser 線索</strong>
      <div class="context-chip-row">
        ${parsers.slice(0, 8).map((parser) => `<span class="context-chip">${escapeHtml(parser.parser_id || parser.source_format || "parser")}</span>`).join("") || '<span class="context-chip">等待後端提供 parser 線索</span>'}
      </div>
    </section>
    <section class="review-card">
      <span class="eyebrow">Import Lane</span>
      <strong>${escapeHtml(String(lanes.length))} 種匯入路徑</strong>
      <div class="context-chip-row">
        ${lanes.map((lane) => `<span class="context-chip ${toneClass(lane.display_tone)}">${escapeHtml(contentPipelineLaneLabel(lane))} ${escapeHtml(String(lane.count || 0))}</span>`).join("") || '<span class="context-chip">等待後端提供匯入路徑</span>'}
      </div>
    </section>
  `;
}

async function loadRecentEvents(options = {}) {
  if (!eventList) return;
  eventList.innerHTML = `
    <div class="empty-state wide">
      <strong>讀取事件中</strong>
      <p>正在讀取 structured event 摘要。</p>
    </div>
  `;
  try {
    const payload = await getJson("/api/events/recent?limit=40");
    recentEvents = payload.events || [];
    renderEventWorkspace();
    if (!options.quiet) {
      addMission("事件紀錄已更新", `${recentEvents.length} 筆 structured event`);
    }
  } catch (error) {
    eventList.innerHTML = `
      <div class="empty-state wide">
        <strong>事件讀取失敗</strong>
        <p>${escapeHtml(String(error))}</p>
      </div>
    `;
  }
}

function renderEventWorkspace() {
  if (!eventList) return;
  if (!recentEvents.length) {
    eventList.innerHTML = `
      <div class="empty-state wide">
        <strong>尚無事件紀錄</strong>
        <p>建立下載計畫或執行 smoke 後，後端 structured event 摘要會出現在這裡。</p>
      </div>
    `;
    return;
  }
  eventList.innerHTML = recentEvents.map((event) => `
    <article class="event-row ${toneClass(event.level)}">
      <div class="event-row-head">
        <div>
          <span class="eyebrow">${escapeHtml(event.component || "rrkal")}</span>
          <strong>${escapeHtml(event.event || "event")}</strong>
        </div>
        <time>${escapeHtml(event.timestamp || "")}</time>
      </div>
      <p>${escapeHtml(event.message || "")}</p>
      ${contextChipsHtml(event.context_summary || {})}
    </article>
  `).join("");
}

function contextChipsHtml(context) {
  const priority = [
    "asset_id",
    "run_record",
    "candidate_count",
    "direct_download_count",
    "review_required_count",
    "warning_count",
    "error_count",
    "duplicate_count",
    "next_action",
    "user_next_action",
    "content_review",
  ];
  const entries = Object.entries(context)
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .sort(([leftKey], [rightKey]) => {
      const left = priority.indexOf(leftKey);
      const right = priority.indexOf(rightKey);
      if (left === -1 && right === -1) return 0;
      if (left === -1) return 1;
      if (right === -1) return -1;
      return left - right;
    })
    .slice(0, 12);
  if (!entries.length) return "";
  return `
    <div class="context-chip-row">
      ${entries.map(([key, value]) => {
        if (typeof value === "object") {
          const label = eventObjectContextLabel(key, value);
          return `<span class="context-chip">${escapeHtml(key)}: ${escapeHtml(label)}</span>`;
        }
        return `<span class="context-chip">${escapeHtml(key)}: ${escapeHtml(String(value))}</span>`;
      }).join("")}
    </div>
  `;
}

function filteredAssets() {
  const needle = assetFilter.value.trim().toLowerCase();
  const health = healthFilter.value;
  return assets.filter((asset) => {
    if (selectedSourceType !== "all" && asset.source_type !== selectedSourceType) return false;
    if (health !== "all" && (asset.health?.status_code || "unknown") !== health) return false;
    if (!needle) return true;
    const haystack = [
      asset.display_name,
      asset.provider_id,
      asset.source_type,
      asset.source_surface,
      asset.endpoint_url,
      asset.health?.status_code,
      asset.next_action_label,
      asset.next_action,
    ].join(" ").toLowerCase();
    return haystack.includes(needle);
  });
}

function assetSlotHtml(asset) {
  const status = asset.health?.status_code || "unknown";
  const trust = boundedPercent(asset.trust_score);
  const initials = assetInitials(asset);
  const capabilityAddress = capabilityAddressLabel(asset);
  return `
    <span class="slot-corner top-left"></span>
    <span class="slot-corner bottom-right"></span>
    <div class="slot-topline">
      <span class="surface-pill">${escapeHtml(surfaceLabel(asset.source_surface))}</span>
      ${statePill(status)}
      ${capabilityAddressBadgeHtml(asset)}
      ${credentialBadgeHtml(asset)}
    </div>
    ${planBadgeHtml(asset)}
    <div class="slot-emblem"><span>${escapeHtml(initials)}</span></div>
    <div class="slot-copy">
      <strong>${escapeHtml(asset.display_name)}</strong>
      <span>${escapeHtml(asset.provider_id)}</span>
    </div>
    <div class="slot-stat-grid">
      <div><span>信任</span><strong>${escapeHtml(String(trust))}</strong></div>
      <div><span>位址</span><strong>${escapeHtml(capabilityAddress || shortPattern(asset.source_type))}</strong></div>
    </div>
    <div class="trust-meter" title="trust score ${trust}">
      <i style="width: ${trust}%"></i>
    </div>
  `;
}

async function selectAsset(assetId, options = {}) {
  // Select -> detail -> passport/form render. The detail endpoint carries the
  // form/display contracts; JS should not infer source-type-specific forms.
  selectedAssetId = assetId;
  renderAssetGrid();
  try {
    const detail = await getJson(`/api/crawler-assets/${encodeURIComponent(assetId)}`);
    selectedAssetDetail = detail;
    renderPassport(detail.card, detail.asset);
    renderSelectedHero(detail.card, detail.flow_steps || []);
    renderBoundsForm(detail.bound_form);
    writeJson(detail.bound_form);
    if (options.autoEnumerate !== false && shouldAutoEnumerateSeeds(detail.card)) {
      autoEnumeratedAssetIds.add(assetId);
      runCrawlerAssetListingById(assetId, { auto: true });
    }
    addMission("載入資產護照", detail.card.display_name);
  } catch (error) {
    selectedAssetDetail = null;
    writeJson({ error: String(error), asset_id: assetId });
  }
}

function shouldAutoEnumerateSeeds(card = {}) {
  // Auto enumeration is a first-use UX helper, not a crawler policy. Credential
  // guards and archive/enable state still live in backend payloads.
  if (!card.asset_id || autoEnumeratedAssetIds.has(card.asset_id)) return false;
  if (card.archived || card.enabled === false) return false;
  if (credentialBlocksLivePlan(card.credentials || {})) return false;
  return true;
}

function renderPassport(card, asset) {
  const capabilityProfile = card.capability_profile || asset.capability_profile || {};
  const capabilityAddress = capabilityAddressLabel(card);
  const capabilitySummary = capabilityProfileSummary(capabilityProfile);
  const capabilities = (card.capabilities || []).map((capability) => `
    <div class="capability-row">
      <strong>${escapeHtml(capabilityLabel(capability))}</strong>
      <span>${escapeHtml(capabilityStatusText(capability))}</span>
    </div>
  `).join("");

  passport.innerHTML = `
    <div class="passport-title">
      <div>
        <span class="eyebrow">資產護照</span>
        <h2>${escapeHtml(card.display_name)}</h2>
      </div>
      ${statePill(card.health?.status_code || "unknown", card.health?.status_label)}
    </div>

    <div class="passport-identity">
      <div class="passport-emblem">${escapeHtml(assetInitials(card))}</div>
      <div>
        <strong>${escapeHtml(card.provider_id)}</strong>
        <span>${escapeHtml(card.source_type)}</span>
      </div>
    </div>

    <dl class="passport-facts">
      <div><dt>來源表面</dt><dd>${escapeHtml(surfaceLabel(card.source_surface))}</dd></div>
      <div><dt>成熟度</dt><dd>${escapeHtml(card.maturity || "unknown")}</dd></div>
      <div><dt>風險層級</dt><dd>${escapeHtml(asset.risk_tier || "unknown")}</dd></div>
      <div><dt>能力位址</dt><dd>${escapeHtml(capabilityAddress || "未分類")}</dd></div>
      <div><dt>能力膠囊</dt><dd>${escapeHtml(capabilitySummary || "unknown")}</dd></div>
      <div><dt>Seed 範式</dt><dd>${escapeHtml(displayTextOrFallback("Seed 範式待確認", capabilityProfile.seed_scope_label, capabilityProfile.seed_scope))}</dd></div>
      <div><dt>Seed</dt><dd>${escapeHtml(card.seed_summary || "")}</dd></div>
      <div><dt>Endpoint</dt><dd>${escapeHtml(card.endpoint_url || "")}</dd></div>
      <div><dt>下一步</dt><dd>${escapeHtml(displayTextOrFallback("檢查界域或審核結果", card.next_action_label, card.next_action))}</dd></div>
    </dl>

    ${planOutcomePanelHtml(card)}
    ${planPassportPanelHtml(card)}
    ${seedListPanelHtml(card)}
    ${credentialPanelHtml(card.credentials, card.asset_id)}

    <div class="trust-radar">
      <div><span>Trust</span><strong>${escapeHtml(String(boundedPercent(card.trust_score)))}</strong></div>
      <div><span>Bounds</span><strong>${escapeHtml(String((card.boundary_modes || []).length || 0))}</strong></div>
      <div><span>Caps</span><strong>${escapeHtml(String((card.capabilities || []).length))}</strong></div>
    </div>

    <section class="capability-list">
      <h3>能力槽</h3>
      ${capabilities || '<p class="muted">尚未宣告能力。</p>'}
    </section>

    <div class="passport-actions">
      <button type="button" class="primary-button" onclick="runCrawlerAssetListingById('${escapeAttr(card.asset_id)}')">重新枚舉 seed</button>
      <button type="button" class="secondary-button" onclick="openCredentialEditorById('${escapeAttr(card.asset_id)}')">登入設定</button>
      <button type="button" class="secondary-button" onclick="prepareOpenCommandById('${escapeAttr(card.asset_id)}')">準備開啟 IDE</button>
      <button type="button" class="secondary-button" onclick="createRepairMission('${escapeAttr(card.asset_id)}')">AI 診斷任務</button>
    </div>
  `;
}

function credentialBadgeHtml(asset) {
  const credentials = asset.credentials || {};
  const profile = credentialDisplayProfile(credentials);
  const label = credentials.display_badge_label || profile.badge_label || credentials.display_label || "";
  if (!label || credentials.status === "public_no_credentials") {
    return "";
  }
  const tone = toneClass(credentials.display_tone);
  const title = displayTextOrFallback(label, profile.next_action_label, credentials.next_action_label, credentials.next_action);
  return `<span class="credential-badge ${tone}" title="${escapeAttr(title)}">${escapeHtml(label)}</span>`;
}

function capabilityAddressLabel(asset) {
  const profile = asset?.capability_profile || {};
  const binary = String(profile.capability_binary || "").trim();
  if (binary) return binary;
  const bits = profile.capability_bits;
  return Number.isInteger(bits) ? bits.toString(2).padStart(4, "0") : "";
}

function capabilityProfileSummary(profile = {}) {
  return [
    profile.source_family,
    profile.transport,
    profile.auth_mode,
    profile.result_shape,
    profile.seed_scope_label || profile.seed_scope,
  ].filter(Boolean).join(" / ");
}

function capabilityAddressBadgeHtml(asset) {
  const address = capabilityAddressLabel(asset);
  if (!address) return "";
  const title = capabilityProfileSummary(asset.capability_profile || {}) || `capability ${address}`;
  return `<span class="capability-address-badge" title="${escapeAttr(title)}">能力 ${escapeHtml(address)}</span>`;
}

function credentialPanelHtml(credentials = {}, assetId = "") {
  const fields = credentials.fields || [];
  const profile = credentialDisplayProfile(credentials);
  const tone = toneClass(credentials.display_tone);
  const panelLabel = profile.label || credentials.display_label || "登入狀態";
  const panelSummary = credentials.display_summary_zh_TW || profile.summary_zh_TW || credentials.safety_note_zh_TW || "登入資訊只留在這台電腦，不會寫進事件紀錄。";
  const entryLink = credentials.credential_entry_url
    ? `<a class="credential-entry-link" href="${escapeAttr(credentials.credential_entry_url)}" target="_blank" rel="noreferrer">${escapeHtml(credentials.credential_entry_label || "開啟官方登入 / 申請 API Key")}</a>`
    : "";
  const docsLink = credentials.docs_url
    ? `<a href="${escapeAttr(credentials.docs_url)}" target="_blank" rel="noreferrer">官方文件</a>`
    : "";
  const signupLink = credentials.signup_url
    ? `<a href="${escapeAttr(credentials.signup_url)}" target="_blank" rel="noreferrer">登入 / 申請金鑰</a>`
    : "";
  const fieldRows = fields.length
    ? fields.map((field) => `
        <div class="credential-field-row ${field.configured ? "configured" : "missing"}">
          <span>${escapeHtml(field.label || "登入資訊")}</span>
          <strong>${escapeHtml(field.configured ? field.value_preview || "已設定" : "尚未設定")}</strong>
          <small>${escapeHtml(field.env_var || "")}</small>
        </div>
      `).join("")
    : '<p class="muted">這個來源沒有可編輯的本機登入欄位；若仍需要登入，請先補 crawler credential profile。</p>';
  return `
    <section class="credential-panel ${tone}">
      <div class="credential-panel-head">
        <div>
          <span class="eyebrow">登入設定</span>
          <strong>${escapeHtml(panelLabel)}</strong>
        </div>
        <button type="button" class="secondary-button small" onclick="openCredentialEditorById('${escapeAttr(assetId)}')">編輯</button>
      </div>
      <p>${escapeHtml(panelSummary)}</p>
      <div class="credential-links">
        ${entryLink}
        ${docsLink}
        ${signupLink}
        <span>${escapeHtml(credentials.env_file_exists ? "這台電腦已有登入設定" : "尚未記住帳號")}</span>
      </div>
      <div class="credential-field-list">${fieldRows}</div>
    </section>
  `;
}

function credentialDisplayProfile(credentials = {}) {
  return credentials.display_profile && typeof credentials.display_profile === "object"
    ? credentials.display_profile
    : {};
}

function credentialBlocksLivePlan(credentials = {}) {
  return ["missing_credentials", "partial_credentials", "credential_profile_required"].includes(credentials.status || "");
}

function credentialGuardBanner(credentials = {}, assetId = "") {
  if (!credentialBlocksLivePlan(credentials)) return null;
  const profile = credentialDisplayProfile(credentials);
  const label = profile.label || credentials.display_label || "需要登入 / API Key";
  const summary = credentials.display_summary_zh_TW || profile.summary_zh_TW || credentials.safety_note_zh_TW || "這個來源需要先完成登入設定；像登入 Email 一樣，先到官方入口取得金鑰，再回到這裡貼上。";
  const panel = document.createElement("section");
  panel.className = `credential-guard-banner ${toneClass(credentials.display_tone)}`;
  panel.innerHTML = `
    <div>
      <strong>${escapeHtml(label)}</strong>
      <p>${escapeHtml(summary)}</p>
    </div>
    <div class="credential-guard-actions">
      ${credentials.credential_entry_url ? `<a class="secondary-button small" href="${escapeAttr(credentials.credential_entry_url)}" target="_blank" rel="noreferrer">${escapeHtml(credentials.credential_entry_label || "開啟官方登入 / 申請 API Key")}</a>` : ""}
      <button type="button" class="primary-button small">登入設定</button>
    </div>
  `;
  panel.querySelector("button").addEventListener("click", () => openCredentialEditorById(assetId));
  return panel;
}

async function openCredentialEditorById(assetId) {
  // Credentials are local-machine setup. The frontend only renders editable
  // fields returned by the backend credential profile.
  try {
    const status = await getJson(`/api/crawler-assets/${encodeURIComponent(assetId)}/credentials`);
    showCredentialEditor(assetId, status);
  } catch (error) {
    writeJson({ error: String(error), endpoint: "credentials", asset_id: assetId });
    addMission("登入設定讀取失敗", String(error));
  }
}

function showCredentialEditor(assetId, status) {
  closeCredentialEditor();
  const overlay = document.createElement("div");
  overlay.className = "credential-modal-backdrop";
  overlay.dataset.credentialEditor = "active";
  overlay.innerHTML = `
    <section class="credential-modal" role="dialog" aria-modal="true" aria-label="登入設定">
      <div class="credential-modal-head">
        <div>
          <span class="eyebrow">Login / API Key</span>
          <h2>${escapeHtml(status.provider_name || status.provider_id || assetId)}</h2>
          <p>${escapeHtml(status.safety_note_zh_TW || "開官方入口取得金鑰後貼回這裡；登入資訊只留在這台電腦。")}</p>
        </div>
        <button type="button" class="ghost-button small" data-credential-close>關閉</button>
      </div>
      ${credentialLoginStepsHtml(status)}
      <div class="credential-links">
        ${status.credential_entry_url ? `<a class="credential-entry-link" href="${escapeAttr(status.credential_entry_url)}" target="_blank" rel="noreferrer">${escapeHtml(status.credential_entry_label || "開啟官方登入 / 申請 API Key")}</a>` : ""}
        ${status.docs_url ? `<a href="${escapeAttr(status.docs_url)}" target="_blank" rel="noreferrer">官方文件</a>` : ""}
        ${status.signup_url ? `<a href="${escapeAttr(status.signup_url)}" target="_blank" rel="noreferrer">登入 / 申請金鑰</a>` : ""}
        <span>${escapeHtml(status.env_file_exists ? "這台電腦已有登入設定" : "尚未記住帳號")}</span>
      </div>
      <form class="credential-edit-form" data-credential-form>
        ${credentialEditorFieldsHtml(status.fields || [])}
        <label class="credential-remember-row">
          <input type="checkbox" data-remember-local ${status.remember_local_default === false ? "" : "checked"} />
          <span>
            <strong>記住我的帳號</strong>
            <small>下次開啟仍可使用；取消勾選時，只在目前 Web Preview 進程暫時使用。</small>
          </span>
        </label>
      </form>
      <div class="credential-modal-actions">
        <button type="button" class="secondary-button" data-credential-close>取消</button>
        <button type="button" class="primary-button" data-credential-save>完成登入設定</button>
      </div>
    </section>
  `;
  document.body.appendChild(overlay);
  overlay.querySelectorAll("[data-credential-close]").forEach((button) => {
    button.addEventListener("click", closeCredentialEditor);
  });
  overlay.querySelector("[data-credential-save]").addEventListener("click", () => saveCredentialEditor(assetId));
}

function credentialLoginStepsHtml(status) {
  const entryLabel = status.credential_entry_label || "開啟官方登入 / 申請 API Key";
  return `
    <ol class="credential-login-steps">
      <li><strong>開官方入口</strong><span>${escapeHtml(entryLabel)}，用官方流程登入或申請金鑰。</span></li>
      <li><strong>取得金鑰</strong><span>複製官方提供的 API Key、Token、帳號或密碼。</span></li>
      <li><strong>回到 RRKAL 儲存</strong><span>貼上後按「完成登入設定」，再重新建立下載計畫。</span></li>
    </ol>
  `;
}

function credentialEditorFieldsHtml(fields) {
  if (!fields.length) {
    return `
      <div class="empty-state">
        <strong>尚未定義登入欄位</strong>
        <p>這個來源標示需要登入，但目前沒有可編輯的帳號或 API Key 欄位；請先補 crawler credential profile。</p>
      </div>
    `;
  }
  return fields.map((field) => `
    <label class="credential-edit-field">
      <span>
        <strong>${escapeHtml(field.label || "登入資訊")}</strong>
        <small>${escapeHtml(field.configured ? `已設定：${field.value_preview}` : "尚未設定")}</small>
        <small>${escapeHtml(field.env_var || "")}</small>
      </span>
      <input
        class="credential-input"
        type="password"
        autocomplete="off"
        data-env-var="${escapeAttr(field.env_var)}"
        placeholder="${escapeAttr(field.configured ? "留空代表不變；輸入新值才會更新" : "貼上官方提供的 API Key / Token / 密碼")}"
      />
      <label class="credential-clear-row">
        <input type="checkbox" data-clear-env-var="${escapeAttr(field.env_var)}" />
        <span>清除這個登入資訊</span>
      </label>
    </label>
  `).join("");
}

async function saveCredentialEditor(assetId) {
  const overlay = document.querySelector("[data-credential-editor='active']");
  if (!overlay) return;
  const values = {};
  const clear = [];
  overlay.querySelectorAll("[data-env-var]").forEach((input) => {
    const envVar = input.dataset.envVar;
    if (envVar && input.value) {
      values[envVar] = input.value;
    }
  });
  overlay.querySelectorAll("[data-clear-env-var]").forEach((input) => {
    if (input.checked && input.dataset.clearEnvVar) {
      clear.push(input.dataset.clearEnvVar);
    }
  });
  const rememberLocal = Boolean(overlay.querySelector("[data-remember-local]")?.checked);
  try {
    const status = await postJson(`/api/crawler-assets/${encodeURIComponent(assetId)}/credentials`, {
      values,
      clear,
      remember_local: rememberLocal,
    });
    writeJson(status);
    addMission("登入設定已更新", `${assetId} / ${displayTextOrFallback("登入狀態待確認", status.display_label, status.status)}`);
    closeCredentialEditor();
    await loadAssets();
    if (assetId) {
      await selectAsset(assetId);
    }
  } catch (error) {
    writeJson({ error: String(error), endpoint: "save_credentials", asset_id: assetId });
    addMission("登入設定儲存失敗", String(error));
  }
}

function closeCredentialEditor() {
  document.querySelectorAll("[data-credential-editor='active']").forEach((node) => node.remove());
}

function renderBoundsForm(spec) {
  // Dynamic bounds form renderer. Field groups, labels, presets, and warning
  // status come from the backend form contract.
  boundsForm.innerHTML = "";
  setContentReviewBadge(null);
  const fields = spec.fields || [];
  const credentials = selectedAssetDetail?.card?.credentials || {};
  configureBuildPlanButton(credentials);
  if (!fields.length) {
    formState.textContent = "不需界域";
    formState.className = "state-pill warning";
    payloadPreviewButton.disabled = true;
    buildPlanButton.disabled = !selectedAssetId;
    boundsForm.innerHTML = `
      <div class="empty-state">
        <strong>這個爬蟲資產沒有動態界域表單</strong>
        <p>後端沒有提供 bounds schema。它可能是固定索引來源，或仍需要能力設定。</p>
      </div>
    `;
    const guard = credentialGuardBanner(credentials, selectedAssetId);
    if (guard) boundsForm.prepend(guard);
    return;
  }

  formState.textContent = spec.display_label || "可輸入";
  formState.className = "state-pill success";
  payloadPreviewButton.disabled = !selectedAssetId;
  buildPlanButton.disabled = !selectedAssetId;
  const guard = credentialGuardBanner(credentials, selectedAssetId);
  if (guard) {
    formState.textContent = credentials.display_label || "需要登入 / API Key";
    formState.className = `state-pill ${toneClass(credentials.display_tone)}`;
    boundsForm.appendChild(guard);
  }
  const presetPanel = boundPresetPanel(spec);
  if (presetPanel) {
    boundsForm.appendChild(presetPanel);
  }
  for (const group of groupedBoundFields(spec, fields)) {
    const section = document.createElement("section");
    section.className = "bounds-group";
    section.dataset.group = group.group;

    const heading = document.createElement("div");
    heading.className = "bounds-group-head";
    const title = document.createElement("strong");
    title.textContent = group.label;
    const count = document.createElement("span");
    count.textContent = `${group.fields.length} 欄位`;
    heading.append(title, count);
    section.appendChild(heading);

    if (group.help) {
      const help = document.createElement("p");
      help.className = "bounds-group-help";
      help.textContent = group.help;
      section.appendChild(help);
    }

    const fieldGrid = document.createElement("div");
    fieldGrid.className = "bounds-group-fields";
    for (const field of group.fields) {
      fieldGrid.appendChild(boundFieldElement(field));
    }
    section.appendChild(fieldGrid);
    boundsForm.appendChild(section);
  }
  applyRecommendedValuesSilently(spec);
}

function configureBuildPlanButton(credentials = {}) {
  const blocked = credentialBlocksLivePlan(credentials);
  buildPlanButton.dataset.action = blocked ? "credentials" : "build-plan";
  buildPlanButton.textContent = blocked ? "先設定登入 / API Key" : "建立下載計畫";
  buildPlanButton.title = blocked
    ? "此來源需要登入設定；按下會開啟登入設定，不會直接送出遠端請求。"
    : "用目前界域建立後端下載計畫。";
}

function handleBuildPlanClick() {
  if (!selectedAssetId) return;
  const credentials = selectedAssetDetail?.card?.credentials || {};
  if (buildPlanButton.dataset.action === "credentials" || credentialBlocksLivePlan(credentials)) {
    addMission("先設定登入 / API Key", selectedAssetId);
    openCredentialEditorById(selectedAssetId);
    return;
  }
  submitBounds(true);
}

function applyRecommendedValuesSilently(spec) {
  const values = spec.recommended_values || {};
  let appliedCount = 0;
  for (const [key, value] of Object.entries(values)) {
    const element = boundsForm.elements.namedItem(key);
    if (!element || element.value) continue;
    element.value = String(value);
    appliedCount += 1;
  }
  if (!appliedCount) return;
  const note = document.createElement("div");
  note.className = "bounds-autofill-note";
  note.textContent = `已自動套用 ${appliedCount} 個推薦值；仍可手動修改或改用常用區域。`;
  boundsForm.prepend(note);
}

function boundPresetPanel(spec) {
  const recommendedValues = spec.recommended_values || {};
  const presets = spec.presets || [];
  const hasRecommended = Object.keys(recommendedValues).length > 0;
  if (!hasRecommended && !presets.length && !spec.guidance_zh_TW) {
    return null;
  }

  const panel = document.createElement("section");
  panel.className = "bounds-preset-panel";

  const head = document.createElement("div");
  head.className = "bounds-preset-head";
  const title = document.createElement("strong");
  title.textContent = "快速界域";
  const help = document.createElement("span");
  help.textContent = spec.guidance_zh_TW || "先套用推薦值，再預覽 payload。";
  head.append(title, help);
  panel.appendChild(head);

  const buttons = document.createElement("div");
  buttons.className = "bounds-preset-actions";
  if (hasRecommended) {
    const button = presetButton("套用推薦設定", "success");
    button.addEventListener("click", () => applyBoundPreset("recommended", "套用推薦設定", recommendedValues));
    buttons.appendChild(button);
  }
  for (const preset of presets) {
    const label = preset.label_zh_TW || preset.label_en || preset.preset_id;
    const button = presetButton(label, preset.tone || "neutral", preset.description_zh_TW || preset.description_en || "");
    button.addEventListener("click", () => applyBoundPreset(preset.preset_id, label, preset.values || {}));
    buttons.appendChild(button);
  }
  panel.appendChild(buttons);
  return panel;
}

function presetButton(label, tone, title = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `preset-button ${toneClass(tone)}`;
  button.textContent = label;
  button.title = title;
  return button;
}

function applyBoundPreset(presetId, label, values) {
  const applied = {};
  for (const [key, value] of Object.entries(values || {})) {
    const element = boundsForm.elements.namedItem(key);
    if (!element) continue;
    element.value = String(value);
    applied[key] = value;
  }
  addMission("套用界域 preset", `${label} / ${Object.keys(applied).length} 欄位`);
  writeJson({
    asset_id: selectedAssetId,
    applied_bound_preset: presetId,
    applied_label: label,
    values: applied,
    next_action: "preview_payload_before_building_plan",
  });
}

function groupedBoundFields(spec, fields) {
  const displayByGroup = new Map(
    (spec.group_display || []).map((item) => [
      item.group,
      {
        label: item.display_label || item.group,
        help: item.display_help || "",
      },
    ]),
  );
  const orderedGroups = [];
  const seen = new Set();
  for (const group of spec.groups || []) {
    if (!seen.has(group)) {
      orderedGroups.push(group);
      seen.add(group);
    }
  }
  for (const field of fields) {
    const group = field.group || "OtherBounds";
    if (!seen.has(group)) {
      orderedGroups.push(group);
      seen.add(group);
    }
  }
  return orderedGroups
    .map((group) => {
      const groupFields = fields.filter((field) => (field.group || "OtherBounds") === group);
      const display = displayByGroup.get(group) || { label: group, help: "" };
      return {
        group,
        label: display.label,
        help: display.help,
        fields: groupFields,
      };
    })
    .filter((group) => group.fields.length);
}

function boundFieldElement(field) {
  const wrapper = document.createElement("div");
  wrapper.className = "form-field";
  const label = document.createElement("label");
  label.htmlFor = field.field_id;
  label.textContent = fieldLabel(field);
  wrapper.appendChild(label);
  wrapper.appendChild(inputForField(field));
  const help = document.createElement("p");
  help.textContent = fieldHelp(field);
  wrapper.appendChild(help);
  return wrapper;
}

function inputForField(field) {
  if ((field.options || []).length) {
    const select = document.createElement("select");
    select.id = field.field_id;
    select.name = field.field_id;
    select.dataset.control = field.control || "select";
    select.appendChild(new Option("", ""));
    for (const option of field.options) {
      select.appendChild(new Option(option, option));
    }
    if (field.default !== undefined && field.default !== null && field.default !== "") {
      select.value = String(field.default);
    }
    return select;
  }
  const input = document.createElement("input");
  input.id = field.field_id;
  input.name = field.field_id;
  input.dataset.control = field.control || "text";
  input.value = field.default ?? "";
  if (field.control === "number" || field.control === "integer") {
    input.type = "number";
    input.step = field.control === "integer" ? "1" : "any";
  } else if (field.control === "datetime") {
    input.type = "date";
  } else {
    input.type = "text";
  }
  return input;
}

async function submitBounds(execute) {
  // execute=false previews the normalized payload; execute=true builds the
  // backend plan and records display-safe plan outcome/passport payloads.
  if (!selectedAssetId) return;
  if (execute && credentialBlocksLivePlan(selectedAssetDetail?.card?.credentials || {})) {
    handleBuildPlanClick();
    return;
  }
  const values = {};
  for (const element of boundsForm.elements) {
    if (element.name) {
      values[element.name] = element.value;
    }
  }
  const url = `/api/crawler-assets/${encodeURIComponent(selectedAssetId)}/plan-preview?execute=${execute ? "true" : "false"}`;
  try {
    const payload = await postJson(url, values);
    writeJson(payload);
    if (payload.plan_outcome) {
      rememberAssetPlanOutcome(selectedAssetId, payload.plan_outcome);
      rememberAssetPlanPassport(selectedAssetId, payload.plan_passport);
      formState.textContent = displayTextOrFallback("檢查下載計畫結果", payload.plan_outcome.display_label, payload.next_action_label, payload.next_action);
      formState.className = `state-pill ${toneClass(payload.plan_outcome.display_tone)}`;
      setContentReviewBadge(payload.plan_outcome.content_review);
      addMission(
        payload.plan_outcome.display_label || "下載計畫結果",
        displayTextOrFallback("檢查下載計畫結果", payload.plan_outcome.summary, payload.next_action_label, payload.next_action),
      );
      renderAssetGrid();
      refreshSelectedAssetOutcomeViews();
    } else {
      setContentReviewBadge(null);
      addMission(
        execute ? "建立下載計畫" : "產生界域 payload",
        `${selectedAssetId} / ${displayTextOrFallback("檢查下載計畫結果", payload.next_action_label, payload.next_action)}`,
      );
    }
    if (payload.adapter_review) {
      latestAdapterReview = payload.adapter_review;
      renderReviewWorkspace();
    }
    if (payload.adapter_review?.item_count) {
      addMission("Adapter 待辦", `${payload.adapter_review.item_count} 筆 / ${adapterReviewOutcomeText(payload.adapter_review.outcomes || [])}`);
      if (payload.adapter_review.content_review_buckets?.length) {
        addMission("內容格式待辦", contentReviewText(payload.adapter_review.content_review_buckets || []));
      }
      if (payload.adapter_review.content_pipeline_lanes?.length) {
        addMission("匯入路徑", contentPipelineLaneText(payload.adapter_review.content_pipeline_lanes || []));
      }
    }
    renderDownloaderWorkspace();
    if (execute) {
      loadRecentEvents({ quiet: true });
    }
  } catch (error) {
    writeJson({ error: String(error), asset_id: selectedAssetId });
  }
}

function rememberAssetPlanOutcome(assetId, planOutcome) {
  if (!assetId || !planOutcome) return;
  assetPlanOutcomes.set(assetId, planOutcome);
  const asset = assets.find((item) => item.asset_id === assetId);
  if (asset) {
    asset.latest_plan_outcome = planOutcome;
  }
  if (selectedAssetDetail?.card?.asset_id === assetId) {
    selectedAssetDetail.card.latest_plan_outcome = planOutcome;
  }
}

function rememberAssetPlanPassport(assetId, planPassport) {
  if (!assetId || !planPassport) return;
  assetPlanPassports.set(assetId, planPassport);
  const asset = assets.find((item) => item.asset_id === assetId);
  if (asset) {
    asset.latest_plan_passport = planPassport;
  }
  if (selectedAssetDetail?.card?.asset_id === assetId) {
    selectedAssetDetail.card.latest_plan_passport = planPassport;
  }
}

function refreshSelectedAssetOutcomeViews() {
  if (!selectedAssetDetail) return;
  renderPassport(selectedAssetDetail.card, selectedAssetDetail.asset);
  renderSelectedHero(selectedAssetDetail.card, selectedAssetDetail.flow_steps || []);
}

function seedListPanelHtml(card) {
  const listing = latestListingForAsset(card) || {};
  const seedPage = assetSeedPages.get(card.asset_id) || {};
  const seeds = seedPage.seeds || [];
  const total = Number(seedPage.total || listing.candidate_count || 0);
  const shown = seeds.length;
  const enumeration = listing.seed_enumeration || {};
  const status = enumeration.label
    || (listing.blocked ? "需要登入或啟用後才能枚舉" : `已枚舉 ${Number(listing.candidate_count || total || 0)} 筆 seed`);
  const help = enumeration.help
    || (shown ? `目前顯示 ${shown}/${total || shown} 筆` : "枚舉後會先顯示前 50 筆；按「顯示更多」展開更多。");
  const limitBadge = enumeration.limited_by_max_results
    ? `<span class="seed-limit-badge">本機上限 ${Number(enumeration.max_results || 0)} 筆</span>`
    : "";
  const rows = seeds.map(seedRowHtml).join("");
  const recommendedPanel = seedRecommendedPanelHtml(card, seedPage);
  const moreButton = seedPage.has_more
    ? `<button type="button" class="secondary-button small" onclick="showMoreSeeds('${escapeAttr(card.asset_id)}')">顯示更多 seed（再 50 筆）</button>`
    : "";
  return `
    <section class="seed-list-panel">
      <div class="seed-list-head">
        <div>
          <span class="eyebrow">Seed List</span>
          <strong>${escapeHtml(status)}${limitBadge}</strong>
          <small>${escapeHtml(help)}${shown ? ` · ${escapeHtml(`目前顯示 ${shown}/${total || shown} 筆`)}` : ""}</small>
        </div>
        <button type="button" class="ghost-button small" onclick="runCrawlerAssetListingById('${escapeAttr(card.asset_id)}')">重新枚舉</button>
      </div>
      ${recommendedPanel}
      <div class="seed-list-viewport">
        ${rows || '<div class="empty-state"><strong>尚未顯示 seed</strong><p>選取入口後會自動枚舉；若來源需要登入，請先完成登入設定。</p></div>'}
      </div>
      <div class="seed-list-actions">${moreButton}</div>
    </section>
  `;
}

function seedRecommendedPanelHtml(card, seedPage) {
  // Backend chooses the default seed. Web only surfaces that choice so users do
  // not have to inspect dozens of rows before running the first real download.
  const recommended = seedPage.recommended_seed || {};
  const recommendedUid = seedPage.recommended_seed_uid || recommended.dataset_uid || "";
  if (!recommendedUid) return "";
  const title = recommended.title || recommended.dataset_id || recommendedUid;
  const label = recommended.content_display_label || "後端推薦 seed";
  return `
    <div class="seed-recommended-panel">
      <div>
        <span class="eyebrow">推薦 seed</span>
        <strong>${escapeHtml(title)}</strong>
        <small>${escapeHtml(label)} · 由後端推薦，適合第一次測試下載</small>
      </div>
      <div class="seed-row-actions">
        <button type="button" class="secondary-button small" onclick="runSeedSchemaProbeById('${escapeAttr(card.asset_id)}', '${escapeAttr(recommendedUid)}')">探測欄位</button>
        <button type="button" class="primary-button small" onclick="runCrawlerSeedDownloadImportById('${escapeAttr(card.asset_id)}', '${escapeAttr(recommendedUid)}')">下載推薦 seed</button>
      </div>
    </div>
  `;
}

function seedRowHtml(seed) {
  const uid = seed.favorite_key || seed.dataset_uid || seed.dataset_id || seed.title || "";
  const downloadUid = seed.dataset_uid || uid;
  const favored = Boolean(seed.favorite) || favoriteSeedUids.has(uid);
  const title = seed.title || seed.dataset_id || uid || "未命名 seed";
  const meta = [seed.native_format, seed.data_type || seed.data_family, seed.version].filter(Boolean).join(" / ");
  const importBadge = seedImportBadgeHtml(seed);
  return `
    <article class="seed-row ${favored ? "favorite" : ""}">
      <button type="button" class="seed-favorite-button" onclick="toggleSeedFavorite('${escapeAttr(uid)}')" title="收藏 seed">${favored ? "★" : "☆"}</button>
      <div>
        <strong>${escapeHtml(title)}</strong>
        <span>${escapeHtml(meta || "metadata pending")}${importBadge}</span>
      </div>
      <small>${escapeHtml(seed.dataset_id || uid)}</small>
      <div class="seed-row-actions">
        <button type="button" class="secondary-button small" onclick="runSeedSchemaProbeById('${escapeAttr(selectedAssetId || "")}', '${escapeAttr(downloadUid)}')">探測欄位</button>
        <button type="button" class="secondary-button small" onclick="runCrawlerSeedDownloadImportById('${escapeAttr(selectedAssetId || "")}', '${escapeAttr(downloadUid)}')">下載此 seed</button>
      </div>
    </article>
  `;
}

function findVisibleSeed(assetId, datasetUid) {
  const page = assetSeedPages.get(assetId) || {};
  const seeds = Array.isArray(page.seeds) ? page.seeds : [];
  return seeds.find((seed) => seedMatchesDatasetUid(seed, datasetUid)) || {};
}

function seedMatchesDatasetUid(seed, datasetUid) {
  const expected = String(datasetUid || "");
  return [
    seed.dataset_uid,
    seed.favorite_key,
    seed.dataset_id,
    seed.title,
  ].some((value) => String(value || "") === expected);
}

function schemaProbeEntryForSeed(seed = {}) {
  const apiUrl = String(seed.api_url || "").trim();
  if (apiUrl) return { api_url: apiUrl };
  const downloadUrl = String(seed.download_url || seed.content_url || seed.landing_url || "").trim();
  return downloadUrl ? { download_url: downloadUrl } : {};
}

function seedImportBadgeHtml(seed) {
  const profile = seed.content_import_profile || {};
  const label = seed.content_display_label || profile.display_label || "";
  if (!label) return "";
  const tone = toneClass(seed.content_display_tone || profile.display_tone);
  const title = [
    seed.content_pipeline_lane_label || profile.pipeline_lane_label || seed.content_display_label || profile.display_label,
    seed.content_next_action_label || profile.next_action_label,
  ].filter(Boolean).join(" / ");
  return ` <span class="context-chip ${tone}" title="${escapeAttr(title || label)}">${escapeHtml(label)}</span>`;
}

async function toggleSeedFavorite(seedUid) {
  const assetId = selectedAssetDetail?.card?.asset_id || selectedAssetId;
  if (!seedUid || !assetId) return;
  const nextFavorite = !favoriteSeedUids.has(seedUid);
  try {
    const result = await postJson(`/api/crawler-assets/${encodeURIComponent(assetId)}/seed-favorites`, {
      dataset_uid: seedUid,
      favorite: nextFavorite,
    });
    setSeedFavoriteState(assetId, seedUid, Boolean(result.favorite));
    addMission("seed 收藏已更新", `${Number(result.favorite_seed_count || 0)} 筆收藏`);
    if (selectedAssetDetail) {
      renderPassport(selectedAssetDetail.card, selectedAssetDetail.asset);
    }
  } catch (error) {
    writeJson({ error: String(error), endpoint: "seed_favorites", asset_id: assetId, dataset_uid: seedUid });
    addMission("seed 收藏失敗", String(error));
  }
}

function rememberSeedFavorites(seeds) {
  for (const seed of seeds) {
    const uid = seed.favorite_key || seed.dataset_uid || seed.dataset_id || seed.title || "";
    if (!uid) continue;
    if (seed.favorite) {
      favoriteSeedUids.add(uid);
    } else {
      favoriteSeedUids.delete(uid);
    }
  }
}

function setSeedFavoriteState(assetId, seedUid, favorite) {
  if (favorite) {
    favoriteSeedUids.add(seedUid);
  } else {
    favoriteSeedUids.delete(seedUid);
  }
  const seedPage = assetSeedPages.get(assetId);
  if (!seedPage || !Array.isArray(seedPage.seeds)) return;
  assetSeedPages.set(assetId, {
    ...seedPage,
    seeds: seedPage.seeds.map((seed) => {
      const uid = seed.favorite_key || seed.dataset_uid || seed.dataset_id || seed.title || "";
      return uid === seedUid ? { ...seed, favorite } : seed;
    }),
  });
}

function rememberCrawlerAssetListing(assetId, listing) {
  if (!assetId || !listing) return;
  assetListingOutcomes.set(assetId, listing);
  const asset = assets.find((item) => item.asset_id === assetId);
  if (asset) {
    asset.latest_listing = listing;
  }
  if (selectedAssetDetail?.card?.asset_id === assetId) {
    selectedAssetDetail.card.latest_listing = listing;
  }
}

function latestListingForAsset(asset) {
  if (!asset) return null;
  return assetListingOutcomes.get(asset.asset_id) || asset.latest_listing || null;
}

function seedEnumerationDetail(result = {}) {
  const enumeration = result.seed_enumeration || {};
  const parts = [
    enumeration.label || `已枚舉 ${Number(result.candidate_count || 0)} 筆`,
    `寫入清單 ${Number(result.upserted_count || 0)} 筆`,
    enumeration.limited_by_max_results ? "已達本機枚舉上限" : "",
    result.warning_count ? `警告 ${result.warning_count}` : "",
    result.error_count ? `錯誤 ${result.error_count}` : "",
  ].filter(Boolean);
  return parts.join(" / ");
}

function prepareOpenCommand(asset) {
  const command = `code --goto ${asset.provider_id}/${asset.source_type}/${asset.asset_id}:1`;
  addMission("準備開啟 IDE", command);
  writeJson({
    intent: "open_ide",
    note: "Web Preview 只能展示命令意圖；實際開啟 IDE 屬於 Tk/Qt 或本機 agent bridge。",
    asset_id: asset.asset_id,
    prepared_command: command,
  });
}

function prepareOpenCommandById(assetId) {
  const asset = assets.find((item) => item.asset_id === assetId);
  if (asset) prepareOpenCommand(asset);
}

function createRepairMission(assetId) {
  const asset = assets.find((item) => item.asset_id === assetId);
  if (!asset) return;
  addMission("AI 診斷任務已建立", `${asset.display_name}：收集 logs / sample payload / schema drift`);
  writeJson({
    intent: "ai_repair_mission",
    asset_id: asset.asset_id,
    stages: ["collect_evidence", "classify_failure", "draft_patch", "run_smoke", "await_review"],
    execution: "preview_only",
  });
}

function addMission(title, detail) {
  missions = [{
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    title,
    detail,
    time: new Date().toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  }, ...missions].slice(0, 7);
  renderMissionQueue();
}

function renderSelectedHero(card, flowSteps = []) {
  const status = card.health?.status_code || "unknown";
  const trust = boundedPercent(card.trust_score);
  selectedHero.innerHTML = `
    <div class="hero-copy">
      <span class="eyebrow">Selected Crawler Asset</span>
      <h2>${escapeHtml(card.display_name)}</h2>
      <p>${escapeHtml(card.seed_summary || card.endpoint_url || "等待後端提供來源摘要。")}</p>
      <div class="hero-meta">
        <span>${escapeHtml(card.provider_id || "provider unknown")}</span>
        <span>${escapeHtml(shortPattern(card.source_type))}</span>
        ${statePill(status, card.health?.status_label)}
      </div>
      ${planOutcomeHeroHtml(card)}
      <div class="hero-actions">
        <button type="button" class="secondary-button" onclick="runCrawlerAssetListingById('${escapeAttr(card.asset_id)}')">重新枚舉 seed</button>
        <button type="button" class="primary-button" onclick="document.querySelector('#payloadPreviewButton')?.click()">預覽界域 payload</button>
        <button type="button" class="secondary-button" onclick="document.querySelector('#buildPlanButton')?.click()">建立下載計畫</button>
      </div>
    </div>
    <div class="hero-emblem" aria-hidden="true">
      <span>${escapeHtml(assetInitials(card))}</span>
      <small>${escapeHtml(surfaceLabel(card.source_surface))}</small>
    </div>
    <div class="hero-health">
      ${heroMetric("Trust", trust)}
      ${heroMetric("Bounds", (card.boundary_modes || []).length || 0)}
      ${heroMetric("Caps", (card.capabilities || []).length)}
      <div class="hero-next-action">
        <span>下一步</span>
        <strong>${escapeHtml(displayTextOrFallback("檢查界域或審核結果", card.next_action_label, card.next_action))}</strong>
      </div>
    </div>
    ${renderFlowSteps(flowSteps)}
  `;
}

function planOutcomePanelHtml(asset) {
  const outcome = latestPlanOutcomeForAsset(asset);
  if (!outcome) return "";
  const label = planOutcomeLabel(outcome, null, "計畫結果");
  const summary = outcome.summary || outcome.next_action_label || "最近一次計畫結果可供檢視。";
  const tone = toneClass(outcome.display_tone);
  const contentReview = outcome.content_review?.has_review
    ? `<span class="plan-outcome-review ${toneClass(outcome.content_review.display_tone)}">${escapeHtml(outcome.content_review.display_label || "內容待辦")}</span>`
    : "";
  return `
    <section class="plan-outcome-panel ${tone}">
      <div>
        <span class="eyebrow">Plan Outcome</span>
        <strong>${escapeHtml(label)}</strong>
        <p>${escapeHtml(summary)}</p>
      </div>
      <div class="plan-outcome-metrics">
        ${heroMetric("Direct", outcome.direct_download_count || 0)}
        ${heroMetric("Review", outcome.review_required_count || 0)}
      </div>
      ${contentReview}
    </section>
  `;
}

function planPassportPanelHtml(asset) {
  const passport = latestPlanPassportForAsset(asset);
  if (!hasPlanPassport(passport)) return "";
  const isStale = Boolean(passport.stale);
  const tone = toneClass(isStale ? "warning" : passport.display_tone || "neutral");
  const resolvedLabel = passport.has_resolved_plan ? "Resolved plan 已建立" : "Resolved plan 待建立";
  const staleLabel = isStale
    ? stalePassportLabel(passport)
    : "profile 已同步";
  const nextAction = isStale
    ? stalePassportNextAction(passport)
    : displayTextOrFallback("等待下一步", passport.next_action_label, passport.next_action);
  const contentReviewLabel = passport.content_review_count
    ? `內容待辦 ${passport.content_review_count}`
    : "內容待辦 0";
  const snapshotLabel = passport.candidate_snapshot_changed ? "候選快照已變更" : "候選快照未標記變更";
  const gateLabel = [
    passport.blocked_credential_count ? `憑證阻擋 ${passport.blocked_credential_count}` : "",
    passport.missing_provider_count ? `缺 Provider ${passport.missing_provider_count}` : "",
  ].filter(Boolean).join(" / ");
  return `
    <section class="plan-passport-panel ${tone}">
      <div>
        <span class="eyebrow">Plan Passport</span>
        <strong>${escapeHtml(planPassportLabel(passport))}</strong>
        <p>${escapeHtml(resolvedLabel)} · ${escapeHtml(nextAction || "等待下一步")}</p>
      </div>
      <div class="plan-outcome-metrics">
        ${heroMetric("Candidates", passport.candidate_count || 0)}
        ${heroMetric("Direct", passport.direct_download_count || 0)}
        ${heroMetric("Review", passport.review_required_count || 0)}
        ${heroMetric("Adapter", passport.adapter_review_count || 0)}
      </div>
      <div class="plan-passport-foot">
        <span>${escapeHtml(staleLabel)}</span>
        <span>${escapeHtml(snapshotLabel)}</span>
        <span>${escapeHtml(contentReviewLabel)}</span>
        <span>${escapeHtml(gateLabel || "憑證 / Provider OK")}</span>
      </div>
    </section>
  `;
}

function planOutcomeHeroHtml(asset) {
  const outcome = latestPlanOutcomeForAsset(asset);
  if (!outcome) return "";
  const label = planOutcomeLabel(outcome, null, "計畫結果");
  const tone = toneClass(outcome.display_tone);
  return `
    <div class="hero-plan-outcome ${tone}" title="${escapeAttr(outcome.summary || outcome.next_action_label || label)}">
      <span>最近計畫</span>
      <strong>${escapeHtml(label)}</strong>
    </div>
  `;
}

function planBadgeHtml(asset) {
  const outcome = latestPlanOutcomeForAsset(asset);
  if (!outcome) return "";
  const label = planOutcomeLabel(outcome, null, "計畫結果");
  const tone = toneClass(outcome.display_tone);
  const contentReview = outcome.content_review?.has_review
    ? `<span class="plan-badge review">${escapeHtml(outcome.content_review.display_label || "內容待辦")}</span>`
    : "";
  return `
    <div class="plan-badge-row" title="${escapeAttr(outcome.summary || outcome.next_action_label || label)}">
      <span class="plan-badge ${tone}">${escapeHtml(label)}</span>
      ${contentReview}
    </div>
  `;
}

function latestPlanOutcomeForAsset(asset) {
  const sessionOutcome = assetPlanOutcomes.get(asset.asset_id);
  if (hasPlanOutcomeBadge(sessionOutcome)) return sessionOutcome;
  if (hasPlanOutcomeBadge(asset.latest_plan_outcome)) return asset.latest_plan_outcome;
  return null;
}

function latestPlanPassportForAsset(asset) {
  const sessionPassport = assetPlanPassports.get(asset.asset_id);
  if (hasPlanPassport(sessionPassport)) return sessionPassport;
  if (hasPlanPassport(asset.latest_plan_passport)) return asset.latest_plan_passport;
  return null;
}

function hasPlanOutcomeBadge(outcome) {
  return Boolean(outcome?.outcome_bucket || outcome?.short_label || outcome?.display_label);
}

function hasPlanPassport(passport) {
  return Boolean(passport?.asset_id || passport?.outcome_bucket || passport?.has_resolved_plan);
}

function heroMetric(label, value) {
  return `
    <div class="hero-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </div>
  `;
}

function renderFlowSteps(flowSteps) {
  if (!flowSteps.length) {
    return "";
  }
  return `
    <div class="flow-strip" aria-label="後端流程狀態">
      ${flowSteps.map((step) => `
        <div class="flow-step ${flowStatusClass(step.status)}">
          <span>${escapeHtml(step.label || step.step_id)}</span>
          <strong>${escapeHtml(step.summary || "")}</strong>
          <small>${escapeHtml(step.evidence || "")}</small>
        </div>
      `).join("")}
    </div>
  `;
}

function flowStatusClass(status) {
  if (["complete", "ready", "bounded", "selectable"].includes(status)) return "complete";
  if (["warning", "neutral"].includes(status)) return "warning";
  return "review";
}

function toneClass(tone) {
  if (["success", "complete", "ready"].includes(tone)) return "success";
  if (["warning", "review"].includes(tone)) return "warning";
  if (["danger", "blocked"].includes(tone)) return "danger";
  return "neutral";
}

function planOutcomeLabel(outcome, passport = null, fallback = "計畫結果") {
  const label = String(outcome?.short_label || outcome?.display_label || passport?.short_label || "").trim();
  return label || fallback;
}

function planPassportLabel(passport, fallback = "計畫護照") {
  const label = String(passport?.short_label || passport?.display_label || "").trim();
  return label || fallback;
}

function reviewOutcomeLabel(outcome, fallback = "待辦分類") {
  const label = String(outcome?.display_label || outcome?.short_label || "").trim();
  return label || fallback;
}

function stalePassportLabel(passport) {
  const label = String(passport?.stale_label || "").trim();
  if (label) return label;
  if (stalePassportNextAction(passport)) return "計畫需重建，請依下一步處理";
  return "計畫需重建";
}

function stalePassportNextAction(passport) {
  if (!passport?.stale && !passport?.stale_next_action_label && !passport?.stale_next_action) {
    return "";
  }
  return displayTextOrFallback("計畫需重建", passport?.stale_next_action_label, passport?.stale_next_action);
}

function displayTextOrFallback(fallback, ...candidates) {
  for (const candidate of candidates) {
    const text = String(candidate || "").trim();
    if (text && !looksLikeBackendToken(text)) return text;
  }
  return fallback;
}

function looksLikeBackendToken(text) {
  if (!/^[a-z][a-z0-9_]*$/.test(text)) return false;
  if (text.includes("_")) return true;
  return ["review", "plan", "unknown", "blocked", "planned", "ready"].includes(text);
}

function adapterReviewOutcomeText(outcomes) {
  if (!outcomes.length) return "無待辦分類";
  return outcomes.map((outcome) => `${reviewOutcomeLabel(outcome)} ${outcome.count}`).join(" / ");
}

function eventObjectContextLabel(key, value) {
  if (key === "run_record") {
    return displayTextOrFallback(
      "執行紀錄",
      value.display_label,
      value.stage_label,
      value.status_label,
      value.stage,
      value.status,
    );
  }
  return displayTextOrFallback(
    "事件內容",
    value.display_label,
    value.short_label,
    value.review_label,
    value.review_bucket,
    value.pipeline_lane,
  );
}

function contentReviewBucketLabel(bucket) {
  return displayTextOrFallback("內容格式待辦", bucket.display_label, bucket.review_bucket);
}

function contentPipelineLaneLabel(lane) {
  return displayTextOrFallback("匯入路徑待辦", lane.display_label, lane.pipeline_lane);
}

function contentReviewText(buckets) {
  if (!buckets.length) return "尚無內容格式待辦";
  return buckets.map((bucket) => `${contentReviewBucketLabel(bucket)} ${bucket.count}`).join(" / ");
}

function contentPipelineLaneText(lanes) {
  if (!lanes.length) return "尚無匯入路徑分類";
  return lanes.map((lane) => `${contentPipelineLaneLabel(lane)} ${lane.count}`).join(" / ");
}

function setContentReviewBadge(contentReview) {
  if (!contentReviewBadge) return;
  const hasReview = Boolean(contentReview?.has_review);
  contentReviewBadge.hidden = !hasReview;
  if (!hasReview) {
    contentReviewBadge.textContent = "";
    contentReviewBadge.className = "content-review-badge neutral";
    contentReviewBadge.removeAttribute("title");
    return;
  }

  const label = contentReview.display_label || "內容格式待辦";
  contentReviewBadge.textContent = label;
  contentReviewBadge.className = `content-review-badge ${toneClass(contentReview.display_tone)}`;
  const bucketSummary = contentReviewText(contentReview.buckets || []);
  contentReviewBadge.title = bucketSummary === "尚無內容格式待辦" ? label : bucketSummary;
}

function renderMissionQueue() {
  missionCount.textContent = String(missions.length);
  missionQueue.innerHTML = missions.length ? missions.map((mission) => `
    <div class="mission-row">
      <span class="mission-dot"></span>
      <div>
        <strong>${escapeHtml(mission.title)}</strong>
        <span>${escapeHtml(mission.detail)}</span>
      </div>
      <time>${escapeHtml(mission.time)}</time>
    </div>
  `).join("") : `
    <div class="empty-state">
      <strong>尚無互動紀錄</strong>
      <p>選擇爬蟲資產、輸入界域或建立 plan 後，這裡會留下可回放的操作線索。</p>
    </div>
  `;
}

function setServerState(text, state, title = "") {
  serverState.textContent = text;
  serverState.className = `server-state ${state}`;
  if (title) {
    serverState.title = title;
  } else {
    serverState.removeAttribute("title");
  }
}

function statePill(status, label = "") {
  return `<span class="state-pill ${statusClass(status)}">${escapeHtml(label || statusLabel(status))}</span>`;
}

function statusLabel(status) {
  const labels = {
    healthy: "可用",
    needs_bounds: "需界域",
    blocked: "阻擋",
    missing_handler: "缺 handler",
    review_needed: "待審核",
    disabled: "停用",
    archived: "封存",
    failed: "失敗",
    unknown: "未知",
  };
  return labels[status] || "未知";
}

function statusClass(status) {
  if (["healthy", "ready", "bounded"].includes(status)) return "success";
  if (["needs_bounds", "review_needed", "disabled", "archived"].includes(status)) return "warning";
  if (["missing_handler", "blocked", "failed"].includes(status)) return "danger";
  return "neutral";
}

function capabilityStatusText(capability) {
  const parts = [capability.status_label || "需檢查能力狀態"];
  if (capability.next_action_label) parts.push(capability.next_action_label);
  return parts.join(" / ");
}

function capabilityLabel(capability) {
  if (capability.display_label) return capability.display_label;
  const labels = {
    fetch_metadata: "抓取元資料",
    list_datasets: "擷取資料清單",
    build_download_plan: "建立下載計畫",
  };
  return labels[capability.capability_id] || capability.label || capability.capability_id;
}

function fieldLabel(field) {
  if (field.display_label) return field.display_label;
  const labels = {
    collection: "資料集合",
    time_field: "時間欄位",
    start_date: "開始日期",
    end_date: "結束日期",
    bbox_west: "西界經度",
    bbox_south: "南界緯度",
    bbox_east: "東界經度",
    bbox_north: "北界緯度",
    limit: "筆數上限",
    max_results: "結果上限",
    max_pages: "頁數上限",
    search_terms: "搜尋關鍵字",
    format: "輸出格式",
    credential_profile: "憑證設定檔",
  };
  return labels[field.field_id] || field.label_zh_TW || field.label_en || field.field_id;
}

function fieldHelp(field) {
  if (field.display_help) return field.display_help;
  const help = {
    collection: "選擇或輸入資料集合；不同範式可能稱為 collection、package、dataset。",
    time_field: "資料集若有時間序列，請輸入對應時間欄位名稱。",
    start_date: "界定要下載的開始時間。",
    end_date: "界定要下載的結束時間。",
    bbox_west: "界定空間範圍的最小經度。",
    bbox_south: "界定空間範圍的最小緯度。",
    bbox_east: "界定空間範圍的最大經度。",
    bbox_north: "界定空間範圍的最大緯度。",
    limit: "限制候選或下載計畫大小，適合展示與安全試跑。",
    max_results: "限制 crawler 回傳的候選數。",
    max_pages: "限制 crawler 探索頁數，避免無界抓取。",
    search_terms: "用逗號分隔多個關鍵字。",
    format: "指定偏好的資料格式；未知時保留空白交給 adapter review。",
    credential_profile: "需要帳號或 API key 的來源，應由爬蟲資產設定檔管理。",
  };
  return help[field.field_id] || field.help_zh_TW || field.help_en || "";
}

function assetInitials(asset) {
  const text = asset.display_name || asset.provider_id || asset.asset_id || "RR";
  const parts = text.split(/[\s_-]+/).filter(Boolean);
  if (!parts.length) return "RR";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function shortPattern(value) {
  const parts = String(value || "unknown").split("_").filter(Boolean);
  return parts.slice(0, 2).join(" ");
}

function surfaceLabel(value) {
  const labels = {
    api: "API",
    catalog: "目錄",
    file_index: "檔案索引",
    map_service: "地圖服務",
    clearnet: "公開網路",
    authenticated: "需認證",
    archive: "檔案索引",
    internal: "內部",
  };
  return labels[String(value || "").toLowerCase()] || value || "unknown";
}

function countBy(items, keyFn) {
  const counts = {};
  for (const item of items) {
    const key = keyFn(item);
    counts[key] = (counts[key] || 0) + 1;
  }
  return counts;
}

function boundedPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

function selectedSourceTypeStillExists() {
  return selectedSourceType === "all" || assets.some((asset) => asset.source_type === selectedSourceType);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json();
}

function writeJson(payload) {
  resultJson.textContent = JSON.stringify(payload, null, 2);
}

async function copyJson() {
  try {
    await navigator.clipboard.writeText(resultJson.textContent);
    addMission("JSON 已複製", "Backend Inspector");
  } catch {
    addMission("JSON 複製失敗", "瀏覽器不允許 clipboard API");
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}
