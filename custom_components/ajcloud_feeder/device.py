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

    alias = device_raw.get("aliasName") or base.get("aliasName") or f"Feeder {device_id[-6:]}"
    model_name = base.get("prodName") or device_raw.get("prodName") or "Pet Feeder"
    device_mode = base.get("deviceMode") or device_raw.get("deviceMode")
    fw_ver = base.get("fwVersion") or status.get("fwVersion") or None

    mac = net.get("wlanMac") or net.get("ethMac") or device_raw.get("mac")
    ip = net.get("localIp")

    connections = set()
    if mac:
        connections.add((CONNECTION_NETWORK_MAC, mac.lower()))

    config_url = f"http://{ip}" if ip else None
    full_model = f"{model_name.capitalize()} ({device_mode})" if device_mode else model_name.capitalize()

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        connections=connections,
        name=f"Умная кормушка {alias}",
        manufacturer="AJCloud",
        model=full_model,
        sw_version=fw_ver,
        configuration_url=config_url,
        suggested_area="Кухня",
    )
