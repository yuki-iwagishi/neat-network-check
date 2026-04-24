# Neat Network Connectivity Checker

A browser-based network diagnostic tool for verifying that firewalls and network policies meet the requirements for **Neat devices** running Zoom Rooms, Microsoft Teams Rooms, Google Meet, and BYOD mode.

No external packages required — runs entirely on Python's standard library.

**Language / 言語 / 언어 / 語言:**
[English](README.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

---

## Requirements

- Python 3.8 or later
- macOS or Windows
- No third-party packages needed

---

## Usage

```bash
python3 neat_network_checker.py
```

The script starts a local web server on port **17432** and automatically opens your browser at `http://localhost:17432`.

> **Windows:** `python neat_network_checker.py`

---

## What It Checks

### 🖥 Neat Common (runs for all modes)
Checks connectivity to core Neat infrastructure required by every device regardless of conferencing platform.

| Check | Target | Protocol |
|---|---|---|
| Connectivity (HTTP) | connectivitycheck.neat.no | TCP 80 |
| Connectivity (HTTPS) | connectivitycheck.neat.no | TCP 443 |
| Authentication | id.neat.no | HTTPS 443 |
| OTA Updates | ota.neat.no | HTTPS 443 |
| Pulse Platform | pulse.neat.no | HTTPS 443 |
| Pulse API | api.pulse.neat.no | HTTPS 443 |
| Support Portal | support.neat.no | HTTPS 443 |
| NTP | time.neat.no | UDP 123 |

### 🔵 Zoom Rooms
Based on [KB0060548](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) and [KB0065712](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712).

Domains: `zoom.us`, `zoom.com`, `zoomgov.com`
TCP ports: 80, 443, 8801, 8802
UDP ports: 3478, 3479 (to zoom.us), 8801–8803 (to Zoom IP ranges)

### 🟣 Microsoft Teams Rooms
Based on [Microsoft 365 URL & IP Ranges](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams).

Domains: `teams.microsoft.com`, `skype.com`, `lync.com`, `microsoftonline.com`, `graph.microsoft.com`, `office365.com`, `microsoft.com`, `office.com`, `sfbassets.com`
UDP ports: 3478–3481 (to worldaz.relay.teams.microsoft.com → 52.112.0.0/14)

### 🟢 Google Meet
Based on [Prepare Your Network for Meet](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams).

Domains: `meet.google.com`, `accounts.google.com`, `apis.google.com`, `googleapis.com`, `gstatic.com`, `googleusercontent.com`
UDP ports: 3478, 19302, 19309 (to workspace.turns.goog and meet.turns.goog)

### 💻 BYOD
BYOD mode only requires the Neat Common checks above.

---

## Optional Checks

### Custom NTP Server
Tests UDP 123 connectivity to a user-specified NTP server in addition to `time.neat.no`.

### mDNS Check
Sends a PTR query to `224.0.0.251:5353` for `_neat._tcp.local` to verify multicast connectivity and local Neat device discovery.
> Requires admin privileges (macOS: `sudo`, Windows: Run as Administrator).

### Proxy & SSL Inspection
- Detects HTTP/HTTPS proxy configuration from system settings and environment variables.
- Checks for TLS MITM (SSL inspection) by examining the certificate issuer of `zoom.us` against known public CAs.

### Bandwidth Test
Downloads and uploads 20 MB via `speed.cloudflare.com` and measures throughput.

Full-HD thresholds per platform:
| Platform | Upload | Download |
|---|---|---|
| Zoom Rooms 1080p | ≥ 3.8 Mbps | ≥ 3.0 Mbps |
| Google Meet 1080p | ≥ 3.6 Mbps | ≥ 3.6 Mbps |
| Teams Live Events | ≥ 10 Mbps (recommended) | ≥ 10 Mbps |

> **Note:** This test uses HTTP (TCP). Actual video/audio traffic uses UDP (RTP/SRTP). Results serve as a TCP reference — QoS policies may cause TCP and UDP throughput to differ.

---

## Result Status

| Status | Meaning |
|---|---|
| ✅ PASS | Connectivity confirmed |
| ⚠️ WARN | Reachable but with caveats (e.g. UDP port sent, no ICMP block detected) |
| ❌ FAIL | Connection failed or blocked |

### UDP STUN / Media Ports
UDP media ports (e.g. 8801–8810 for Zoom, 3478–3481 for Teams) **do not respond to STUN probes** — this is normal behaviour. A `WARN` result with "No ICMP block detected → port is likely OPEN" means the port is probably reachable. A `FAIL` with "ICMP Port Unreachable" means the firewall is actively blocking it.

---

## Export

Results can be exported as:
- **HTML report** — formatted table with colour-coded status
- **CSV** — for spreadsheet analysis or ticket logging

---

## UI Languages

The browser UI supports: English, 日本語, 한국어, 繁體中文, 简体中文

---

## Reference Documentation

| Platform | Link |
|---|---|
| Neat | [Network & Firewall Requirements](https://support.neat.no/article/network-and-firewall-requirements-for-neat/) |
| Zoom | [Firewall Rules](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712) · [Network Requirements](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) · [Bandwidth](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748) |
| Teams | [M365 URLs & IP Ranges](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams) · [Media Bit Rate Policy](https://learn.microsoft.com/en-us/microsoftteams/meeting-policies-audio-and-video#media-bit-rate-kbps) |
| Google Meet | [Prepare Your Network](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams) |

---

## Disclaimer

This tool is provided as-is for network diagnostic purposes. Results reflect conditions at the time of the test. Consult your network administrator and the official vendor documentation for authoritative requirements.
