"""AJCloud API Client for Home Assistant."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from urllib.parse import urlparse
import aiohttp

try:
    from .const import DEFAULT_APP_NAME, DEFAULT_VENDOR_CODE, PORTAL_URL
    from .crypto import encrypt_password_challenge
except ImportError:
    from const import DEFAULT_APP_NAME, DEFAULT_VENDOR_CODE, PORTAL_URL
    from crypto import encrypt_password_challenge

_LOGGER = logging.getLogger(__name__)

APP_VERSION = "2.0.26092014"


class AJCloudAuthError(Exception):
    """Authentication failed."""


class AJCloudApiError(Exception):
    """Generic API error."""


class AJCloudApiClient:
    """API client for AJCloud."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self._session = session
        self.uac_url: str = ""
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.sign_token: str | None = None
        self.uid: str | None = None
        self.country_code: str = "RU"
        self.continent_code: str = "CEU"
        self.devices: dict[str, dict[str, Any]] = {}
        self.gateways: dict[str, str] = {}
        self.agent_token = "{892658b0-eb88-49e2-a758-cae8d8b80215}"

    def _meta(self, device_id: str | None = None) -> dict[str, Any]:
        """Construct standard meta dictionary matching official Android app."""
        meta: dict[str, Any] = {
            "locale": "ru",
            "localtz": 180,
            "appName": DEFAULT_APP_NAME,
            "appVersion": APP_VERSION,
            "appVendorCode": DEFAULT_VENDOR_CODE,
            "agentName": "Samsung Galaxy",
            "appCountryCode": self.country_code,
            "appContinentCode": self.continent_code,
        }
        if self.access_token:
            meta["accessToken"] = self.access_token
            meta["token"] = self.access_token
        if device_id:
            meta["deviceId"] = device_id
        return meta

    def _build_signed_headers(self, full_url: str, body_str: str) -> dict[str, str]:
        """Generate mandatory X-UAC-Signature HMAC-SHA256 headers."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if not self.access_token or not self.sign_token:
            return headers

        path = urlparse(full_url).path
        ts = str(int(time.time() * 1000) + 1000)
        body_sha256 = hashlib.sha256(body_str.encode("utf-8")).hexdigest()
        canonical = f"POST\n{path}\n{body_sha256}\n"
        canonical_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        string_to_sign = f"HMAC-SHA256\n{ts}\n{canonical_sha256}"

        h = hmac.new(self.sign_token.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256)
        sig_b64url = base64.urlsafe_b64encode(h.digest()).decode("utf-8").rstrip("=")
        uac_sig = f"UAC1-HMAC-SHA256;{ts};{sig_b64url}"

        headers["Authorization"] = f"Bearer {self.access_token}"
        headers["X-UAC-Signature"] = uac_sig
        return headers

    async def async_resolve_node(self, username: str) -> str:
        """Query account node URL for username."""
        payload = {
            "meta": {
                "appName": DEFAULT_APP_NAME,
                "appVendorCode": DEFAULT_VENDOR_CODE,
            },
            "data": {
                "username": username,
                "accountType": "email",
            },
        }
        async with self._session.post(PORTAL_URL, json=payload, timeout=15) as resp:
            data = await resp.json()
            if data.get("code") != 0:
                raise AJCloudApiError(f"Node query failed: {data.get('message')}")
            res = data.get("result", {})
            self.uac_url = res.get("uacNodeUrl", "https://uac-eu.ajcloud.net/api")
            self.country_code = res.get("crCode", "RU")
            self.continent_code = res.get("ctCode", "CEU")
            return self.uac_url

    async def async_login(self, username: str, password: str) -> bool:
        """Perform two-phase outer-challenge + signin."""
        if not self.uac_url:
            await self.async_resolve_node(username)

        # 1. Outer challenge
        challenge_url = f"{self.uac_url}/v3/outer-challenge"
        challenge_payload = {
            "meta": self._meta(),
            "data": {
                "origin": "mobile phone",
                "osName": "android",
                "agentName": "Samsung Galaxy",
                "agentToken": self.agent_token,
                "username": username,
                "action": "signin",
                "appVendorCode": DEFAULT_VENDOR_CODE,
            },
        }
        async with self._session.post(challenge_url, json=challenge_payload, timeout=15) as resp:
            res = await resp.json()
            if res.get("code") != 0 or not res.get("result"):
                raise AJCloudAuthError(f"Challenge failed: {res.get('message', 'Unknown error')}")
            c_result = res["result"]
            server_pub = c_result["serverPubKey"]
            client_sec = c_result["clientSecretKey"]

        # 2. Encrypt password with NaCl Box
        enc_pwd, nonce_b64 = encrypt_password_challenge(password, client_sec, server_pub)

        # 3. Sign in
        signin_url = f"{self.uac_url}/v1/signin"
        signin_payload = {
            "meta": self._meta(),
            "data": {
                "origin": "mobile phone",
                "osName": "android",
                "agentName": "Samsung Galaxy",
                "modelName": "Samsung Galaxy",
                "agentToken": self.agent_token,
                "appVendorCode": DEFAULT_VENDOR_CODE,
                "grantType": "password",
                "scope": "all",
                "username": username,
                "password": enc_pwd,
                "nonce": nonce_b64,
            },
        }
        async with self._session.post(signin_url, json=signin_payload, timeout=15) as resp:
            s_res = await resp.json()
            if s_res.get("code") != 0 or not s_res.get("result"):
                raise AJCloudAuthError(f"Signin failed: {s_res.get('message', 'Invalid credentials')}")
            s_data = s_res["result"]
            self.access_token = s_data.get("accessToken")
            self.refresh_token = s_data.get("refreshToken")
            self.sign_token = s_data.get("signToken")
            self.uid = s_data.get("uid")
            ident = s_data.get("ident", {})
            if ident.get("region"):
                self.country_code = ident["region"]
            if ident.get("continent"):
                self.continent_code = ident["continent"]

        _LOGGER.info("Successfully authenticated with AJCloud (UID: %s)", self.uid)
        return True

    async def async_fetch_devices(self) -> list[dict[str, Any]]:
        """Fetch bound devices and their gateway URLs."""
        if not self.access_token:
            raise AJCloudAuthError("Not authenticated")

        list_url = f"{self.uac_url}/v3/device-list"
        body_obj = {
            "meta": self._meta(),
            "data": {},
        }
        body_str = json.dumps(body_obj, separators=(",", ":"))
        headers = self._build_signed_headers(list_url, body_str)

        async with self._session.post(list_url, data=body_str, headers=headers, timeout=15) as resp:
            res = await resp.json()
            if res.get("code") != 0:
                raise AJCloudApiError(f"Device list failed: {res.get('message')}")
            result_data = res.get("result", {})
            devices_raw = result_data.get("conDevices", [])
            dev_generals = result_data.get("devGenerals", [])

            # Extract individual appGatewayUrl from devGenerals context
            for gen in dev_generals:
                did = gen.get("deviceId")
                ctx_str = gen.get("context", "")
                if did and ctx_str:
                    try:
                        ctx = json.loads(ctx_str)
                        cfg = ctx.get("config", {})
                        gw = cfg.get("appGatewayUrl")
                        if gw:
                            self.gateways[did] = gw
                    except Exception:
                        pass

        self.devices = {d["deviceId"]: d for d in devices_raw if "deviceId" in d}
        return list(self.devices.values())

    async def async_feed(self, device_id: str, portions: int = 1, outlet: int = 0) -> bool:
        """Send feed command to device."""
        if not self.access_token:
            raise AJCloudAuthError("Not authenticated")

        gw = self.gateways.get(device_id, "https://cam-gw-us.ajcloud.net/api")
        url = f"{gw.rstrip('/')}/v1/feed-manual-ctrl"

        data_payload: dict[str, Any] = {
            "feedQuantity": portions,
            "feedUnit": "piece",
        }
        if outlet > 0:
            data_payload["outlets"] = [outlet]
            data_payload["feedQuantities"] = [portions]

        body_obj = {
            "meta": self._meta(device_id=device_id),
            "data": data_payload,
        }
        body_str = json.dumps(body_obj, separators=(",", ":"))
        headers = self._build_signed_headers(url, body_str)

        async with self._session.post(url, data=body_str, headers=headers, timeout=15) as resp:
            res = await resp.json()
            if res.get("code") != 0:
                raise AJCloudApiError(f"Feed command failed: {res.get('message', res)}")
            _LOGGER.info("Feed command succeeded for %s: %s portion(s)", device_id, portions)
            return True

    async def async_enable_rtsp(self, device_id: str, enable: bool = True, port: int = 554, verify: int = 0) -> bool:
        """Enable or disable local RTSP stream on the device."""
        if not self.access_token:
            raise AJCloudAuthError("Not authenticated")

        gw = self.gateways.get(device_id, "https://cam-gw-us.ajcloud.net/api")
        url = f"{gw.rstrip('/')}/v1/rtsp-config"

        body_obj = {
            "meta": self._meta(device_id=device_id),
            "data": {
                "deviceId": device_id,
                "enable": "1" if enable else "0",
                "port": str(port),
                "verify": str(verify),
            },
        }
        body_str = json.dumps(body_obj, separators=(",", ":"))
        headers = self._build_signed_headers(url, body_str)

        async with self._session.post(url, data=body_str, headers=headers, timeout=15) as resp:
            res = await resp.json()
            return res.get("code") == 0

    async def async_get_device_status(self, device_id: str) -> dict[str, Any]:
        """Fetch real-time device telemetry and status."""
        if not self.access_token:
            raise AJCloudAuthError("Not authenticated")

        gw = self.gateways.get(device_id, "https://cam-gw-us.ajcloud.net/api")
        url = f"{gw.rstrip('/')}/v1/fetch-infos"

        body_obj = {
            "meta": self._meta(device_id=device_id),
            "data": {
                "devices": [{"deviceId": device_id, "deviceType": 1}],
            },
        }
        body_str = json.dumps(body_obj, separators=(",", ":"))
        headers = self._build_signed_headers(url, body_str)

        async with self._session.post(url, data=body_str, headers=headers, timeout=15) as resp:
            res = await resp.json()
            if res.get("code") != 0:
                return {}
            infos = res.get("result", {}).get("infos", [])
            if infos:
                return infos[0].get("info", {})
            return {}
