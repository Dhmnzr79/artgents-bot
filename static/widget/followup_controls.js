/**
 * Pure helpers for merging widget follow-up controls (W1).
 * @param {Array<{ref?: string, label?: string}>} followups
 * @param {Array<{ref?: string, label?: string}>} quickReplies
 * @returns {Array<{label: string, ref: string}>}
 */
export function mergeFollowupControls(followups, quickReplies) {
  const items = [];
  const seen = new Set();
  for (const source of [followups || [], quickReplies || []]) {
    for (const item of source) {
      if (!item || !item.ref) continue;
      const ref = String(item.ref).trim();
      if (!ref || seen.has(ref)) continue;
      seen.add(ref);
      const label = String(item.label || item.ref || "").trim();
      items.push({ label: label || ref, ref });
    }
  }
  return items;
}
