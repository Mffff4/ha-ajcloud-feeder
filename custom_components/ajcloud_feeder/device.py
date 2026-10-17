"""Device info helper for AJCloud Smart Pet Feeder."""
from __future__ import annotations

from typing import Any
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def get_device_info(device_id: str, device_raw: dict[str, Any], status_info: dict[str, Any] | None = None) -> DeviceInfo:
    """Build unified, beautifully formatted Home Assistant DeviceInfo."""
    base = status_info.get("base", {}) if status_info else {}
    alias = device_raw.get("aliasName") or base.get("aliasName") or f"Кормушка {device_id[-6:]}"
    model_name = base.get("prodName") or device_raw.get("prodName") or "lion3"
    device_mode = base.get("deviceMode") or "CGP-UPKG1"
    fw_ver = base.get("fwVersion") or "14.00007.01.28"
    mac = "c8:fe:0f:93:d1:2b"
    ip = "192.168.2.84"

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        connections={(CONNECTION_NETWORK_MAC, mac)},
        name=f"Умная кормушка {alias}",
        manufacturer="AJCloud",
        model=f"{model_name.capitalize()} ({device_mode})",
        sw_version=fw_ver,
        configuration_url=f"http://{ip}",
        suggested_area="Кухня",
    )
