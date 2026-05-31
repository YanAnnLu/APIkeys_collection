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

function providerDisplayText(asset) {
  // Provider labels are not yet guaranteed in older payloads, so keep provider_id
  // as the stable display fallback instead of hiding useful provenance.
  const text = String(asset?.provider_name || asset?.provider_label || asset?.provider_id || "").trim();
  return text || "Provider 待確認";
}
