#!/usr/bin/env python3
"""Standalone CLI test tool for AJCloud Smart Pet Feeder API."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import aiohttp

# Import local client modules
from api import AJCloudApiClient, AJCloudAuthError, AJCloudApiError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ajcloud_test")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test AJCloud Pet Feeder API directly.")
    parser.add_argument("--username", "-u", required=True, help="AJCloud account email")
    parser.add_argument("--password", "-p", required=True, help="AJCloud account password")
    parser.add_argument("--feed", action="store_true", help="Trigger feeding immediately")
    parser.add_argument("--enable-rtsp", action="store_true", help="Enable RTSP stream on port 554")
    parser.add_argument("--portions", type=int, default=1, help="Portion count (default: 1)")
    parser.add_argument("--device-id", "-d", default=None, help="Device ID (optional, defaults to first feeder found)")

    args = parser.parse_args()

    async with aiohttp.ClientSession() as session:
        client = AJCloudApiClient(session)

        logger.info("Resolving region node for %s...", args.username)
        node_url = await client.async_resolve_node(args.username)
        logger.info("Node URL: %s", node_url)

        logger.info("Authenticating via Curve25519 + XSalsa20 challenge...")
        try:
            await client.async_login(args.username, args.password)
        except AJCloudAuthError as e:
            logger.error("Authentication failed: %s", e)
            sys.exit(1)

        logger.info("Fetching devices...")
        devices = await client.async_fetch_devices()
        logger.info("Found %d device(s):", len(devices))
        for dev in devices:
            did = dev.get("deviceId")
            name = dev.get("aliasName") or "Unnamed"
            status = dev.get("conStatus")
            gw = client.gateways.get(did, "default")
            logger.info("  - [%s] %s (status: %s, gateway: %s)", did, name, status, gw)

        if not devices:
            logger.warning("No devices found.")
            return

        target_did = args.device_id or devices[0].get("deviceId")

        logger.info("Querying status for device %s...", target_did)
        status_info = await client.async_get_device_status(target_did)
        if status_info:
            base = status_info.get("base", {})
            logger.info("Device Model: %s, Firmware: %s, Online: %s", base.get("prodName"), base.get("fwVersion"), base.get("onlineStatus"))

        if args.enable_rtsp:
            logger.info("Enabling RTSP stream for %s...", target_did)
            ok = await client.async_enable_rtsp(target_did, enable=True, port=554, verify=0)
            logger.info("RTSP enable result: %s (Stream URL: rtsp://192.168.2.84:554/live/ch0)", ok)

        if args.feed:
            logger.info("Sending feed command: %d portion(s) to %s...", args.portions, target_did)
            success = await client.async_feed(target_did, portions=args.portions)
            if success:
                logger.info("SUCCESS! Food dispensed.")
            else:
                logger.error("Feed command failed.")


if __name__ == "__main__":
    asyncio.run(main())
