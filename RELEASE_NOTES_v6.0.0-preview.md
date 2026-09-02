# R20 Quantum Trader v6.0.0-preview

> **Preview release · 2026-09-02**
>
> This release advances the native R20 Gateway control plane while preserving the execution-layer safety boundary. It is a preview: validate channel behavior in your own deployment before treating it as production-ready.

## Highlights

### Native Gateway preview

- Durable Gateway event queue, independent delivery worker, scheduler ownership, plugin registry, and audit-oriented control plane remain R20-native.
- No runtime dependency is introduced on QwenPaw or OpenClaw for trading, scheduling, backup, or notifications.
- The web monitoring terminal remains read-only; no new HTTP trade trigger is exposed.

### WeChat iLink delivery semantics corrected

- `sendmessage` now returns **Tencent iLink accepted** with a traceable `client_id`; it no longer claims that a recipient's WeChat client received or read the message.
- Admin diagnostics explicitly state that iLink exposes no end-device/read receipt.
- `ret=-14` is reported as Bot Token expiry.
- `ret/errcode=-2` with `unknown error` is handled as stale Context Token. The operator must message the iLink Bot again to refresh the session.
- The watcher only refreshes the stored Context Token from `message_type=1` user messages, never from the Bot's own echoed `message_type=2` traffic.
- Watcher timestamps are now emitted explicitly in Beijing time (UTC+8).

## Upgrade notes

1. Do **not** interpret `HTTP 200` or `ret=0` as proof of WeChat handset delivery.
2. If WeChat sends stop arriving, message the iLink Bot directly, wait for the watcher to record the new UTC+8 session refresh timestamp, then use one confirmation-protected test send.
3. Keep QQ, Telegram, enterprise WeChat, or a managed webhook enabled as a redundant route for critical risk alerts. Personal WeChat iLink Context Tokens are session-bound and are not a durable push entitlement.
4. No trading controls were relaxed or changed in this preview.

## Verification

- Unit coverage includes iLink stale-token rejection, accepted-vs-client-delivery labeling, and prevention of Bot-echo Context Token overwrite.
- Full test-suite results and production process restart validation should be completed by each deployment operator before promotion beyond preview.

## Known protocol boundary

Tencent iLink's `sendmessage` API acknowledges request acceptance, but this protocol does not provide an authoritative receipt that the recipient's WeChat client displayed or read the message. R20 therefore reports the strongest state that the upstream API can actually prove.
