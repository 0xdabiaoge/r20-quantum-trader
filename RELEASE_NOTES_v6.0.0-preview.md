# R20 Quantum Trader v6.0.0-preview

> **Preview release · 2026-09-02**
>
> This release advances the native R20 Gateway control plane while preserving the execution-layer safety boundary. It is a preview: validate channel behavior in your own deployment before treating it as production-ready.

## Highlights

### Native Gateway preview

- Durable Gateway event queue, independent delivery worker, scheduler ownership, plugin registry, and audit-oriented control plane remain R20-native.
- No runtime dependency is introduced on QwenPaw or OpenClaw for trading, scheduling, backup, or notifications.
- The web monitoring terminal remains read-only; no new HTTP trade trigger is exposed.

### Notification channel simplification

- R20 now exposes four notification channels: QQ official Bot, enterprise WeChat, Telegram and generic Webhook.
- The personal WeChat connector, QR binding routes, session watcher, plugin entry and admin configuration panel have been removed.
- Critical alerts should use at least two independent channels.
- Historical delivery rows for retired channels remain in the local audit database; R20 does not create new deliveries for them.

## Upgrade notes

1. Remove legacy personal WeChat notification values from deployment environment overrides; the bundled cleanup migration also deletes locally stored credentials.
2. Configure at least two of QQ, Telegram, enterprise WeChat and a managed Webhook for critical risk alerts.
3. Existing audit records for removed channels are retained but cannot be replayed.
4. No trading controls were relaxed or changed in this preview.

## Verification

- Unit coverage verifies that removed channels cannot be enabled, diagnosed, tested or selected for new Gateway deliveries.
- Full test-suite results and production process restart validation should be completed by each deployment operator before promotion beyond preview.

## Notification boundary

A channel is only suitable for critical trading alerts when its success state is operationally meaningful. R20 exposes only the notification integrations it can support as explicit operational channels.
