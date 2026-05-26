let assets = [];
let selectedAssetId = "";
let selectedAssetDetail = null;
let selectedSourceType = "all";
let activeWorkspace = "assets";
let latestAdapterReview = null;
let recentEvents = [];
let missions = [];
const assetPlanOutcomes = new Map();
const assetPlanPassports = new Map();

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
const downloaderRefreshButton = document.querySelector("#downloaderRefreshButton");
const downloaderQueue = document.querySelector("#downloaderQueue");
const reviewReturnButton = document.querySelector("#reviewReturnButton");
const reviewSummary = document.querySelector("#reviewSummary");
const eventRefreshButton = document.querySelector("#eventRefreshButton");
const eventList = document.querySelector("#eventList");

refreshButton.addEventListener("click", loadAssets);
assetFilter.addEventListener("input", renderAssetGrid);
healthFilter.addEventListener("change", renderAssetGrid);
payloadPreviewButton.addEventListener("click", () => submitBounds(false));
buildPlanButton.addEventListener("click", () => submitBounds(true));
copyJsonButton.addEventListener("click", copyJson);
workspaceButtons.forEach((button) => button.addEventListener("click", () => showWorkspace(button.dataset.workspace)));
downloaderRefreshButton.addEventListener("click", renderDownloaderWorkspace);
reviewReturnButton.addEventListener("click", () => showWorkspace("assets"));
eventRefreshButton.addEventListener("click", () => loadRecentEvents());

loadAssets();
renderMissionQueue();
showWorkspace(activeWorkspace);

async function loadAssets() {
  setServerState("讀取中", "neutral");
  try {
    const health = await getJson("/api/health");
    const payload = await getJson("/api/crawler-assets");
    assets = payload.assets || [];
    selectedSourceType = selectedSourceTypeStillExists() ? selectedSourceType : "all";
    renderOverview(health);
    renderHealthFilter();
    renderSourceTypeFilters();
    renderAssetGrid();
    renderDownloaderWorkspace();
    renderReviewWorkspace();
    addMission("Web Preview 已連線", `讀取 ${assets.length} 個 crawler asset / ${serverRuntimeLabel(health)}`);
    if (!selectedAssetId && assets.length) {
      await selectAsset(assets[0].asset_id);
    } else if (selectedAssetId) {
      await selectAsset(selectedAssetId);
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
  } else if (activeWorkspace === "events") {
    loadRecentEvents({ quiet: true });
  }
}

function renderDownloaderWorkspace() {
  if (!downloaderQueue) return;
  const queueAssets = assets.filter((asset) => (
    hasPlanOutcomeBadge(latestPlanOutcomeForAsset(asset)) || hasPlanPassport(latestPlanPassportForAsset(asset))
  ));
  if (!queueAssets.length) {
    downloaderQueue.innerHTML = `
      <div class="empty-state wide">
        <strong>尚無下載計畫結果</strong>
        <p>先在爬蟲資產分頁輸入界域並建立下載計畫；這裡會顯示後端回傳的 plan outcome / passport。</p>
      </div>
    `;
    return;
  }
  downloaderQueue.innerHTML = queueAssets.map((asset) => downloaderRowHtml(asset)).join("");
}

function downloaderRowHtml(asset) {
  const outcome = latestPlanOutcomeForAsset(asset) || {};
  const passport = latestPlanPassportForAsset(asset) || {};
  const tone = toneClass(outcome.display_tone || passport.display_tone);
  const label = planOutcomeLabel(outcome, passport, "計畫結果");
  const nextAction = outcome.next_action_label || passport.next_action || asset.next_action || "等待後端下一步";
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
        <button type="button" class="secondary-button" onclick="focusAssetFromWorkspace('${escapeAttr(asset.asset_id)}')">檢視資產</button>
      </div>
    </article>
  `;
}

async function focusAssetFromWorkspace(assetId) {
  await selectAsset(assetId);
  showWorkspace("assets");
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
        ${buckets.map((bucket) => `<span class="context-chip warning">${escapeHtml(bucket.display_label || bucket.review_bucket)} ${escapeHtml(String(bucket.count || 0))}</span>`).join("") || '<span class="context-chip">無內容格式待辦</span>'}
      </div>
    </section>
    <section class="review-card">
      <span class="eyebrow">Parser Registry</span>
      <strong>${escapeHtml(String(parsers.length))} 種 parser 線索</strong>
      <div class="context-chip-row">
        ${parsers.slice(0, 8).map((parser) => `<span class="context-chip">${escapeHtml(parser.parser_id || parser.source_format || "parser")}</span>`).join("") || '<span class="context-chip">等待後端提供 parser 線索</span>'}
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
          const label = key === "run_record"
            ? [value.stage, value.status].filter(Boolean).join(" / ")
            : value.display_label || value.review_bucket || JSON.stringify(value);
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
      asset.next_action,
    ].join(" ").toLowerCase();
    return haystack.includes(needle);
  });
}

function assetSlotHtml(asset) {
  const status = asset.health?.status_code || "unknown";
  const trust = boundedPercent(asset.trust_score);
  const initials = assetInitials(asset);
  return `
    <span class="slot-corner top-left"></span>
    <span class="slot-corner bottom-right"></span>
    <div class="slot-topline">
      <span class="surface-pill">${escapeHtml(surfaceLabel(asset.source_surface))}</span>
      ${statePill(status)}
    </div>
    ${planBadgeHtml(asset)}
    <div class="slot-emblem"><span>${escapeHtml(initials)}</span></div>
    <div class="slot-copy">
      <strong>${escapeHtml(asset.display_name)}</strong>
      <span>${escapeHtml(asset.provider_id)}</span>
    </div>
    <div class="slot-stat-grid">
      <div><span>信任</span><strong>${escapeHtml(String(trust))}</strong></div>
      <div><span>範式</span><strong>${escapeHtml(shortPattern(asset.source_type))}</strong></div>
    </div>
    <div class="trust-meter" title="trust score ${trust}">
      <i style="width: ${trust}%"></i>
    </div>
  `;
}

async function selectAsset(assetId) {
  selectedAssetId = assetId;
  renderAssetGrid();
  try {
    const detail = await getJson(`/api/crawler-assets/${encodeURIComponent(assetId)}`);
    selectedAssetDetail = detail;
    renderPassport(detail.card, detail.asset);
    renderSelectedHero(detail.card, detail.flow_steps || []);
    renderBoundsForm(detail.bound_form);
    writeJson(detail.bound_form);
    addMission("載入資產護照", detail.card.display_name);
  } catch (error) {
    selectedAssetDetail = null;
    writeJson({ error: String(error), asset_id: assetId });
  }
}

function renderPassport(card, asset) {
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
      ${statePill(card.health?.status_code || "unknown")}
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
      <div><dt>Seed</dt><dd>${escapeHtml(card.seed_summary || "")}</dd></div>
      <div><dt>Endpoint</dt><dd>${escapeHtml(card.endpoint_url || "")}</dd></div>
      <div><dt>下一步</dt><dd>${escapeHtml(card.next_action || "檢查界域或審核結果")}</dd></div>
    </dl>

    ${planOutcomePanelHtml(card)}
    ${planPassportPanelHtml(card)}

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
      <button type="button" class="secondary-button" onclick="prepareOpenCommandById('${escapeAttr(card.asset_id)}')">準備開啟 IDE</button>
      <button type="button" class="secondary-button" onclick="createRepairMission('${escapeAttr(card.asset_id)}')">AI 診斷任務</button>
    </div>
  `;
}

function renderBoundsForm(spec) {
  boundsForm.innerHTML = "";
  setContentReviewBadge(null);
  const fields = spec.fields || [];
  if (!fields.length) {
    formState.textContent = "不需界域";
    formState.className = "state-pill warning";
    payloadPreviewButton.disabled = true;
    buildPlanButton.disabled = true;
    boundsForm.innerHTML = `
      <div class="empty-state">
        <strong>這個爬蟲資產沒有動態界域表單</strong>
        <p>後端沒有提供 bounds schema。它可能是固定索引來源，或仍需要能力設定。</p>
      </div>
    `;
    return;
  }

  formState.textContent = spec.status || "可輸入";
  formState.className = "state-pill success";
  payloadPreviewButton.disabled = !selectedAssetId;
  buildPlanButton.disabled = !selectedAssetId;
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
  if (!selectedAssetId) return;
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
      formState.textContent = payload.plan_outcome.display_label || payload.next_action || "review";
      formState.className = `state-pill ${toneClass(payload.plan_outcome.display_tone)}`;
      setContentReviewBadge(payload.plan_outcome.content_review);
      addMission(payload.plan_outcome.display_label || "下載計畫結果", payload.plan_outcome.summary || payload.next_action || "review");
      renderAssetGrid();
      refreshSelectedAssetOutcomeViews();
    } else {
      setContentReviewBadge(null);
      addMission(execute ? "建立下載計畫" : "產生界域 payload", `${selectedAssetId} / ${payload.next_action || "review"}`);
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
        ${statePill(status)}
      </div>
      ${planOutcomeHeroHtml(card)}
      <div class="hero-actions">
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
        <strong>${escapeHtml(card.next_action || "檢查界域或審核結果")}</strong>
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
  const nextAction = isStale ? stalePassportNextAction(passport) : passport.next_action;
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
  const nextAction = String(passport?.stale_next_action || "").trim();
  if (nextAction) return nextAction;

  // stale_reason 是 agent/debug 用的內部代碼；Web UI 缺 display label 時仍退到中性操作提示。
  return passport?.stale ? "refresh_or_rebuild_plan_passport" : "";
}

function adapterReviewOutcomeText(outcomes) {
  if (!outcomes.length) return "無待辦分類";
  return outcomes.map((outcome) => `${reviewOutcomeLabel(outcome)} ${outcome.count}`).join(" / ");
}

function contentReviewText(buckets) {
  if (!buckets.length) return "尚無內容格式待辦";
  return buckets.map((bucket) => `${bucket.display_label || bucket.review_bucket} ${bucket.count}`).join(" / ");
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

function statePill(status) {
  return `<span class="state-pill ${statusClass(status)}">${escapeHtml(statusLabel(status))}</span>`;
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
  return labels[status] || status || "未知";
}

function statusClass(status) {
  if (["healthy", "ready", "bounded"].includes(status)) return "success";
  if (["needs_bounds", "review_needed", "disabled", "archived"].includes(status)) return "warning";
  if (["missing_handler", "blocked", "failed"].includes(status)) return "danger";
  return "neutral";
}

function capabilityStatusText(capability) {
  const parts = [capability.status];
  if (capability.next_action) parts.push(capability.next_action);
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
