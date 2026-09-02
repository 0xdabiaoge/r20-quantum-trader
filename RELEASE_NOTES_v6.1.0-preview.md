# R20 Quantum Trader v6.1.0-preview

> **Preview release · 2026-09-02**
>
> v6.1.0 Preview focuses on making the standalone trading path operationally complete: reliable order protection, balanced decision participation, independent OKX onboarding, and visible administrator feedback.

## Highlights

### Trading execution hardening

- Fixed modular prompt assembly so live balance, positions, six-instrument market data, and the complete JSON decision contract reach the model in the correct order.
- Added exchange-confirmed close handling, hard-stop enforcement for losing positions, stale-order Fail-Closed behavior, and strict order-ID validation.
- Added full-position cloud OCO verification. Missing protection is repaired and re-verified; if protection cannot be proven, R20 exits the position safely instead of allowing an unprotected position.
- Corrected OKX CLI cancel syntax and blocked new trading cycles when open-order state cannot be verified.

### Balanced participation without weakening P0

- Corrected a permanent-WAIT failure mode where soft signal conflicts were treated as hard vetoes. In the observed incident, 50 rounds produced 300/300 WAIT decisions.
- P0 safety boundaries remain mandatory. Soft P2/P3 disagreement now reduces position size instead of automatically suppressing every valid trend candidate.
- ADX handling is tiered: below 18 rejects entries; 18–22 permits smaller positions only when 4H and 1H agree; 22 and above is a normal trend candidate.
- Trend deceleration is no longer a permanent veto by itself. Structure, velocity, tail risk, entry geometry, and real R:R must be evaluated together.
- Runtime safety modules are live-locked so stale editable profiles cannot freeze obsolete thresholds.

### Standalone OKX onboarding

- Added `deploy/install.sh` to install Python dependencies and the official OKX CLI.
- Added a secret-free preflight command: `python scripts/r20_okx_setup.py`.
- Added administrator diagnostics for Node.js, npm, OKX CLI path/version, OAuth site/scopes, selected DEMO/LIVE environment, credential source, and authenticated read probes.
- Added a superadmin-only one-click OKX CLI installer with explicit `INSTALL OKX CLI` confirmation, audit logging, installation feedback, and upgrade/restart guidance.
- R20 does not execute QwenPaw Skills. New deployments must configure their own environment-specific API Key or complete CLI OAuth as the same Linux user that runs the backend and Gateway.

### Administrator UI/UX

- Added global request activity, button loading/disabled states, duplicate-submit prevention, sticky success/error feedback, and unhandled-request reporting.
- Confirmation dialogs remain open while protected actions execute and close only after success.
- Isolated module loading failures with `Promise.allSettled`, improved mobile dialog behavior, added accessible dialog semantics, and fixed several silent or misdirected controls.
- Synchronized the administrator prompt editor with the exact live trading rules.

## Upgrade notes

1. Run `./deploy/install.sh` or ensure `@okx_ai/okx-trade-cli@^1.4.4` is installed and visible in the service PATH.
2. Run `python scripts/r20_okx_setup.py`. Keep the Gateway stopped unless the selected environment reports `READY`.
3. Never copy another installation's `~/.okx/`. OAuth authorization is local to the Linux service identity and HOME.
4. Start with OKX DEMO and verify order placement, cancellation, close confirmation, and cloud OCO coverage before enabling LIVE.
5. Review custom prompt profiles. Safety-critical base modules are now live-locked to the running version.
6. Change any temporary or migrated administrator password before exposing the control plane publicly.

## Verification

- 110 automated tests pass.
- Python compilation, administrator JavaScript syntax, shell installer syntax, and Git diff checks pass.
- Backend and Gateway health must still be verified by each deployment operator after upgrade.

## Safety boundary

The public monitoring terminal remains read-only. All protected actions stay inside the authenticated administrator control plane, and trading remains Fail-Closed whenever positions, orders, credentials, market data, or cloud protection cannot be verified.
