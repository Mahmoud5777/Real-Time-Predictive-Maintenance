# Lot4 Patch 3.1 — Fix Compose service dependency merge

1. Extract this patch folder into the repository root (the folder containing `Lot4_LAN_Integration`).
2. Run from repository root:
   `./lot4_patch31/scripts/Install-Lot4-Patch31.ps1`
3. Run the existing validation:
   `./lot4v3/scripts/Validate-Lot4-V3.ps1`

Only the Lot4 central overlay is replaced. MP2 base compose and source code are unchanged. Validation is config-only; no containers start.
