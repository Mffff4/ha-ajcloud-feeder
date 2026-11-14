#!/usr/bin/env python3
"""Offline check of the X-UAC-Signature string format (no network)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components" / "ajcloud_feeder"))

from api import AJCloudApiClient  # noqa: E402

SIGN_TOKEN = "Cwp36HmUPfXxLBQoNFSwieW5lAStaNND0IermYzCl6c="
BODY = '{"meta":{"a":1},"data":{}}'

client = AJCloudApiClient(session=None)  # type: ignore[arg-type]
client.access_token = "AT"
client.sign_token = SIGN_TOKEN
headers = client._build_signed_headers("https://uac-eu.ajcloud.net/api/v3/device-list", BODY)

algo, ts, sig = headers["X-UAC-Signature"].split(";")
assert algo == "UAC1-HMAC-SHA256"
assert headers["Authorization"] == "Bearer AT"

sha = lambda t: hashlib.sha256(t.encode()).hexdigest()  # noqa: E731
inner = sha(f"POST\n/api/v3/device-list\n{sha(BODY)}\n")
expected = base64.urlsafe_b64encode(
    hmac.new(SIGN_TOKEN.encode(), f"HMAC-SHA256\n{ts}\n{inner}".encode(), hashlib.sha256).digest()
).decode().rstrip("=")
assert sig == expected, (sig, expected)
print("signature format OK")
