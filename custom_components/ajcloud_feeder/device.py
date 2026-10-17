"""Device info helper for AJCloud Smart Pet Feeder."""
from __future__ import annotations

from typing import Any
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def get_device_info(device_id: str, device_raw: dict[str, Any], status_info: dict[str, Any] | None = None) -> DeviceInfo:
    """Build unified, dynamically updated Home Assistant DeviceInfo."""
    status = status_info or {}
    base = status.get("base", {})
    net = status.get("networkConfig", {})

    alias = device_raw.get("aliasName") or base.get("aliasName") or f"Кормушка {device_id[-6:]}"
    model_name = base.get("prodName") or device_raw.get("prodName") or "lion3"
    device_mode = base.get("deviceMode") or "CGP-UPKG1"
    fw_ver = base.get("fwVersion") or status.get("fwVersion") or "14.00007.01.28"

    mac = net.get("wlanMac") or net.get("ethMac") or device_raw.get("mac")
    ip = net.get("localIp")

    connections = set()
    if mac:
        connections.add((CONNECTION_NETWORK_MAC, mac.lower()))

    config_url = f"http://{ip}" if ip else None

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        connections=connections,
        name=f"Умная кормушка {alias}",
        manufacturer="AJCloud",
        model=f"{model_name.capitalize()} ({device_mode})",
        sw_version=fw_ver,
        configuration_url=config_url,
        suggested_area="Кухня",
    )
