/*
 * Web display-contract helpers.
 *
 * Keep this file UI-neutral: it turns backend ids/status payload fragments into
 * human-readable labels, but it must not decide crawler, download, import, or
 * credential policy. app.js owns interaction wiring; backend services own truth.
 */

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

function eventObjectContextLabel(key, value) {
  if (key === "run_record") {
    return displayTextOrFallback(
      "執行紀錄",
      value.display_label,
      value.stage_label,
      value.status_label,
    );
  }
  return displayTextOrFallback(
    "事件內容",
    value.display_label,
    value.short_label,
    value.review_label,
  );
}

function eventContextKeyLabel(key) {
  const labels = {
    asset_id: "資產 ID",
    run_record: "執行紀錄",
    candidate_count: "候選數",
    direct_download_count: "直接下載數",
    review_required_count: "需審核數",
    warning_count: "警示數",
    error_count: "錯誤數",
    duplicate_count: "重複數",
    next_action: "下一步",
    user_next_action: "使用者下一步",
    content_review: "內容審核",
  };
  return labels[key] || "事件欄位";
}

function eventContextScalarLabel(key, value) {
  if (key === "next_action" || key === "user_next_action") {
    return displayTextOrFallback("下一步待確認", value);
  }
  if (key === "content_review") {
    return displayTextOrFallback("內容審核待確認", value);
  }
  return String(value);
}

function contentReviewBucketLabel(bucket) {
  return displayTextOrFallback("內容格式待辦", bucket.display_label);
}

function contentPipelineLaneLabel(lane) {
  return displayTextOrFallback("匯入路徑待辦", lane.display_label);
}

function parserDisplayText(parser) {
  return displayTextOrFallback("Parser 線索待確認", parser.display_label, parser.label);
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

function assetDisplayText(asset = {}, fallback = "爬蟲資產待確認") {
  return displayTextOrFallback(
    fallback,
    asset.display_name,
    asset.name,
    asset.title,
    asset.source_type_label,
    asset.capability_profile?.source_type_label,
  );
}

function seedDisplayText(seed = {}, fallback = "seed 待確認") {
  return displayTextOrFallback(
    fallback,
    seed.title,
    seed.display_name,
    seed.dataset_name,
    seed.name,
    seed.content_display_label,
    seed.content_import_profile?.display_label,
  );
}

function flowStepLabel(step) {
  return displayTextOrFallback("流程步驟待確認", step.label);
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
  return displayTextOrFallback("計畫需重建", passport?.stale_next_action_label);
}

function adapterReviewOutcomeText(outcomes) {
  if (!outcomes.length) return "無待辦分類";
  return outcomes.map((outcome) => `${reviewOutcomeLabel(outcome)} ${outcome.count}`).join(" / ");
}

function contentReviewText(buckets) {
  if (!buckets.length) return "尚無內容格式待辦";
  return buckets.map((bucket) => `${contentReviewBucketLabel(bucket)} ${bucket.count}`).join(" / ");
}

function contentPipelineLaneText(lanes) {
  if (!lanes.length) return "尚無匯入路徑分類";
  return lanes.map((lane) => `${contentPipelineLaneLabel(lane)} ${lane.count}`).join(" / ");
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
  const labels = {
    fetch_metadata: "抓取元資料",
    list_datasets: "擷取資料清單",
    build_download_plan: "建立下載計畫",
  };
  return displayTextOrFallback(
    "能力待確認",
    capability.display_label,
    labels[capability.capability_id],
    capability.label,
  );
}

function fieldLabel(field) {
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
  return displayTextOrFallback(
    "欄位待確認",
    field.display_label,
    labels[field.field_id],
    field.label_zh_TW,
    field.label_en,
  );
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

function sourceTypeDisplayText(assetOrType = {}) {
  const profile = typeof assetOrType === "string" ? {} : (assetOrType.capability_profile || {});
  return displayTextOrFallback(
    "來源範式待確認",
    typeof assetOrType === "string" ? "" : assetOrType.source_type_label,
    profile.source_type_label,
  );
}

function surfaceLabel(asset) {
  return displayTextOrFallback("入口類型待確認", asset?.source_surface_label);
}

function providerDisplayText(asset) {
  // Provider labels are not yet guaranteed in older payloads, so keep provider_id
  // as the stable display fallback instead of hiding useful provenance.
  const text = String(asset?.provider_name || asset?.provider_label || asset?.provider_id || "").trim();
  return text || "Provider 待確認";
}
