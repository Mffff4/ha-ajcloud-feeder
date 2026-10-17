<div align="center">

# 🐾 AJCloud Smart Pet Feeder for Home Assistant

### Fully reverse-engineered Home Assistant integration for AJCloud-powered smart pet feeders & cameras

[![HACS Custom Badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge&logo=home-assistant)](https://hacs.xyz/)
[![Validate Integration](https://img.shields.io/github/actions/workflow/status/Mffff4/ha-ajcloud-feeder/validate.yaml?branch=main&style=for-the-badge&logo=github)](https://github.com/Mffff4/ha-ajcloud-feeder/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python)](https://www.python.org/)

**Control portions, feed on schedule, monitor real-time video stream, and automate pet feeding directly from Home Assistant — zero cloud app lock-in.**

[Features](#-features) • [Installation via HACS](#-installation-via-hacs) • [Reverse Engineering Insights](#-reverse-engineering-insights) • [Lovelace UI](#-lovelace-ui-card) • [Automations](#-automation-examples)

</div>

---

## 🌟 Overview

Many modern Wi-Fi smart pet feeders (such as **lion3**, **CGP-UPKG1**, and white-label feeders running **AJCloud / Wansview** IoT firmware) lack an official open API or Home Assistant integration. 

This custom component was created by reverse-engineering the native Android client (`net.ajcloud.universal`) and embedded device communication stack:
- **Zero-Friction Setup:** Config Flow authentication with username & password in the Home Assistant UI.
- **Unified Device Architecture:** Controls, sensors, camera stream, and diagnostics are presented on **a single device card**.
- **Dual Communication Capability:** Cloud gateway command dispatch + direct local RTSP video streaming over LAN.

---

## 🎯 Features

| Entity | Type | Description |
| :--- | :--- | :--- |
| **Выдать корм (Feed)** | `button` | Instantly dispenses food with real-time hardware execution feedback. |
| **Размер порции (Portion Size)** | `number` | Slider (1–10 portions) specifying amount for the next feeding action. |
| **Камера (Camera)** | `camera` | Live low-latency video stream (`rtsp://<IP>:554/live/ch0`) + high-res snapshot view. |
| **Локальный RTSP поток** | `switch` | Remote toggle to enable/disable the camera's on-device RTSP server. |
| **Перезагрузка (Reboot)** | `button` | Diagnostic entity to trigger device soft reboot. |
| **Статус подключения** | `sensor` | Real-time online/offline reachability monitor. |
| **Последнее кормление** | `sensor` | Timestamp (`timestamp` class) of the most recent feeding event. |
| **Выдано сегодня** | `sensor` | Daily portion counter (`total_increasing` class, resets at midnight). |
| **Уровень сигнала Wi-Fi** | `sensor` | Hardware RSSI signal percentage (`signal_strength` class). |
| **Версия прошивки** | `sensor` | Device firmware version (e.g. `14.00007.01.28`). |
| **IP-адрес в сети** | `sensor` | Local LAN IPv4 address (e.g. `192.168.2.84`). |

---

## 🔬 Reverse Engineering Insights

<details>
<summary><b>Click to expand protocol and security architecture details</b></summary>

### 1. Challenge-Response Authentication
Authentication uses a two-phase Curve25519 handshake against the regional User Account Center (`https://uac-<region>.ajcloud.net/api`):
1. **Challenge Request (`/v3/outer-challenge`):** Returns server public key (`serverPubKey`), client secret (`clientSecretKey`), and client public key (`clientPubKey`).
2. **NaCl Box Encryption:** The raw password string is encrypted using Curve25519 ECDH key exchange + XSalsa20-Poly1305 authenticated encryption (`nacl.public.Box` / `TweetNaClFast`) with a 24-byte random nonce.
3. **Session Tokens:** Successful login returns an `accessToken` and a unique `signToken`.

### 2. Mandatory Request Signing (`X-UAC-Signature`)
All authenticated operations require the header `X-UAC-Signature` computed via HMAC-SHA256:
```text
CanonicalRequest = "POST\n" + RequestPath + "\n" + SHA256(RawBody) + "\n"
StringToSign     = "HMAC-SHA256\n" + MillisecondTimestamp + "\n" + SHA256(CanonicalRequest)
Signature        = Base64UrlSafe(HMAC_SHA256(signToken, StringToSign))
Header           = "UAC1-HMAC-SHA256;" + MillisecondTimestamp + ";" + Signature
```

### 3. Food Dispensing Command
Commands are delivered to the device gateway (`https://cam-gw-<node>.ajcloud.net/api/v1/feed-manual-ctrl`):
```json
{
  "meta": {
    "appName": "ajcloud",
    "appVersion": "2.0.26092014",
    "appVendorCode": "AJC",
    "accessToken": "<TOKEN>",
    "token": "<TOKEN>",
    "deviceId": "<DEVICE_ID>"
  },
  "data": {
    "feedQuantity": 2,
    "feedUnit": "piece"
  }
}
```

</details>

---

## 📦 Installation via HACS

### Step 1: Add Custom Repository
1. Open **Home Assistant** → **HACS** → **Integrations**.
2. Click the three dots `⋮` in the top-right corner and select **Custom repositories**.
3. Fill in:
   - **Repository:** `https://github.com/Mffff4/ha-ajcloud-feeder`
   - **Type:** `Integration`
4. Click **Add**.

### Step 2: Install and Restart
1. Find **AJCloud Smart Pet Feeder** in HACS and click **Download**.
2. Restart Home Assistant: **Settings** → **System** → **Restart**.

### Step 3: Add the Integration
1. Go to **Settings** → **Devices & services** → **Add Integration**.
2. Search for **AJCloud Smart Pet Feeder**.
3. Enter your **Email** and **Password** from the mobile AJCloud app.
4. Your feeder will be discovered and created with all entities ready to use!

---

## 🎨 Lovelace UI Card

A pre-configured, beautiful vertical card designed for [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) (with standard card fallback available in `examples/lovelace_card.yaml`):

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-template-card
    primary: Умная кормушка lion3
    secondary: >-
      Статус: {{ states('sensor.umnaya_kormushka_lion3_status_podkliucheniia') }} | 
      Сегодня: {{ states('sensor.umnaya_kormushka_lion3_vydano_segodnia') }} порц.
    icon: mdi:paw
    icon_color: amber

  - type: picture-entity
    entity: camera.umnaya_kormushka_lion3_kamera
    name: Камера
    camera_view: live
    show_name: false
    show_state: false

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-number-card
        entity: number.umnaya_kormushka_lion3_razmer_portsii
        name: Размер порции
        icon: mdi:bowl-mix
        icon_color: deep-orange

      - type: custom:mushroom-template-card
        primary: Покормить
        secondary: Выдать корм
        icon: mdi:food-drumstick
        icon_color: green
        tap_action:
          action: call-service
          service: button.press
          target:
            entity_id: button.umnaya_kormushka_lion3_vydat_korm

  - type: horizontal-stack
    cards:
      - type: custom:mushroom-entity-card
        entity: sensor.umnaya_kormushka_lion3_poslednee_kormlenie
        name: Покормлен
        icon: mdi:clock-check-outline
        icon_color: blue

      - type: custom:mushroom-entity-card
        entity: sensor.umnaya_kormushka_lion3_uroven_signala_wi_fi
        name: Wi-Fi
        icon: mdi:wifi
        icon_color: cyan

      - type: custom:mushroom-entity-card
        entity: switch.umnaya_kormushka_lion3_lokalnyi_rtsp_videopotok
        name: RTSP
        icon: mdi:video-wireless
```

---

## ⏰ Automation Examples

### Scheduled Feeding (Morning & Evening)
```yaml
alias: "Автокормление: 2 порции утром"
trigger:
  - platform: time
    at: "08:00:00"
action:
  - service: ajcloud_feeder.feed_portions
    data:
      feeder_id: "AJCDCTMKOEUR3YKS"
      portions: 2
```

### Feed via Physical Zigbee / Aqara Wireless Button
```yaml
alias: "Кнопка на кухне: насыпать 1 порцию"
trigger:
  - platform: device
    domain: mqtt
    device_id: <BUTTON_DEVICE_ID>
    type: action
    subtype: single
action:
  - service: button.press
    target:
      entity_id: button.umnaya_kormushka_lion3_vydat_korm
```

---

## 🛠️ Standalone CLI Tool

You can test operations directly from terminal without Home Assistant:
```bash
# Test connection and fetch status
python3 examples/test_client.py -u "your_email@example.com" -p 'your_password'

# Dispense 2 portions right now
python3 examples/test_client.py -u "your_email@example.com" -p 'your_password' --feed --portions 2

# Enable local RTSP video stream on port 554
python3 examples/test_client.py -u "your_email@example.com" -p 'your_password' --enable-rtsp
```

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.

<div align="center">
<sub>Crafted with passion, assembly-level reverse engineering, and care for our furry friends.</sub>
</div>
