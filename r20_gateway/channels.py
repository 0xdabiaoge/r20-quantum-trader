"""Notification channel adapter backed by existing R20-native connectors."""
from __future__ import annotations
from dataclasses import dataclass

from r20_backend.notifications import send_channel


@dataclass(frozen=True)
class DeliveryResult:
    success: bool
    detail: str
    status: str = "delivered"


class NotificationChannelAdapter:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id

    def send(self, message: str) -> DeliveryResult:
        ok, detail = send_channel(self.channel_id, message)
        status = "accepted" if ok and self.channel_id == "wechat_ilink" else "delivered"
        return DeliveryResult(ok, detail, status)
