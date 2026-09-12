# Restore W1b WIP from checkpoint

**Patch baseline (product):** `eedbd66d6a0b00ec9a186e4298fbdf9ae90e3d69` on `codex/stage-a`.

Restore is allowed on a **clean descendant HEAD** of that baseline when none of the
22 tracked product files in `w1b_tracked.patch` were modified on the target branch since
`eedbd66`. If any overlap exists — **STOP**; do not force, 3-way merge, or reset.

```powershell
cd "C:\Cursor Projects\demo-bot-local"
$cp = "docs/artifacts/w1b_wip_checkpoint_2026-07-24"

# 1. Verify artifact checksums (canonical: checksums.sha256)
Get-Content "$cp/checksums.sha256"
$patchHash = (Get-FileHash "$cp/w1b_tracked.patch" -Algorithm SHA256).Hash
# Must match TRACKED_PATCH= in checksums.sha256

# 2. Confirm target tree is clean
git status --porcelain

# 3. Dry-run patch (mandatory; abort if fail)
git apply --check "$cp/w1b_tracked.patch"

# 4. Apply tracked changes
git apply "$cp/w1b_tracked.patch"

# 5. Restore untracked files
Copy-Item "$cp/untracked/clients/demo/target_response/family_price_groups.yaml" `
  "clients/demo/target_response/family_price_groups.yaml"
Copy-Item "$cp/untracked/contracts/target_family_price_group_followup.py" `
  "contracts/target_family_price_group_followup.py"
Copy-Item "$cp/untracked/contracts/target_family_price_groups.py" `
  "contracts/target_family_price_groups.py"
Copy-Item "$cp/untracked/tests/test_w1b_family_price_group_drilldown_offline.py" `
  "tests/test_w1b_family_price_group_drilldown_offline.py"
Copy-Item "$cp/untracked/tests/test_w1b_family_price_situation_menu_offline.py" `
  "tests/test_w1b_family_price_situation_menu_offline.py"

# 6. Re-verify untracked file hashes against checksums.sha256
```

Owner approval required before restore.
