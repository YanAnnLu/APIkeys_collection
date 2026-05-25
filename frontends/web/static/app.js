let assets = [];
let selectedAssetId = "";
let selectedSourceType = "all";
let missions = [];

const assetGrid = document.querySelector("#assetGrid");
const assetFilter = document.querySelector("#assetFilter");
const healthFilter = document.querySelector("#healthFilter");
const sourceTypeFilters = document.querySelector("#sourceTypeFilters");
const sourceTypeCount = document.querySelector("#sourceTypeCount");
const passport = document.querySelector("#passport");
const boundsForm = document.querySelector("#boundsForm");
const formState = document.querySelector("#formState");
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

refreshButton.addEventListener("click", loadAssets);
assetFilter.addEventListener("input", renderAssetGrid);
healthFilter.addEventListener("change", renderAssetGrid);
payloadPreviewButton.addEventListener("click", () => submitBounds(false));
buildPlanButton.addEventListener("click", () => submitBounds(true));
copyJsonButton.addEventListener("click", copyJson);

loadAssets();
renderMissionQueue();

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
    addMission("Web Preview 已連線", `讀取 ${assets.length} 個 crawler asset`);
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
  setServerState(`${health.surface || "web_preview"}`, "success");
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
    renderPassport(detail.card, detail.asset);
    renderSelectedHero(detail.card, detail.flow_steps || []);
    renderBoundsForm(detail.bound_form);
    writeJson(detail.bound_form);
    addMission("載入資產護照", detail.card.display_name);
  } catch (error) {
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
  for (const field of fields) {
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
    boundsForm.appendChild(wrapper);
  }
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
    addMission(execute ? "建立下載計畫" : "產生界域 payload", `${selectedAssetId} / ${payload.next_action || "review"}`);
  } catch (error) {
    writeJson({ error: String(error), asset_id: selectedAssetId });
  }
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

function setServerState(text, state) {
  serverState.textContent = text;
  serverState.className = `server-state ${state}`;
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
