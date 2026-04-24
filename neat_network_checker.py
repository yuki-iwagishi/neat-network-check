#!/usr/bin/env python3
"""
Neat Network Connectivity Checker
-----------------------------------
Starts a tiny local web server and opens your browser automatically.
No external packages required — works on macOS and Windows with Python 3.8+

Usage:  python neat_network_checker.py
"""

import http.server
import socketserver
import threading
import webbrowser
import json
import socket
import struct
import time
import os
import ssl
import urllib.request
import urllib.error
import urllib.parse
import csv
import io
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional

PORT = 17432  # local-only, unlikely to be in use

# ─────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────

@dataclass
class CheckItem:
    name: str
    category: str
    check_type: str   # 'https' | 'tcp' | 'udp_ntp' | 'udp_stun' | 'proxy' | 'ssl_inspect'
    target: str
    port: int
    description: str = ""

@dataclass
class CheckResult:
    name: str
    category: str
    check_type: str
    target: str
    port: int
    status: str       # 'pass' | 'fail' | 'warn'
    message: str
    latency_ms: Optional[float] = None

# ─────────────────────────────────────────────────────────────
# CHECK DEFINITIONS
# ─────────────────────────────────────────────────────────────

NEAT_COMMON: List[CheckItem] = [
    CheckItem("Neat Connectivity (HTTP)",   "Neat Common", "tcp",     "connectivitycheck.neat.no",  80,  "HTTP connectivity check (TCP 80)"),
    CheckItem("Neat Connectivity (HTTPS)",  "Neat Common", "https",   "connectivitycheck.neat.no", 443,  "HTTPS connectivity check (TCP 443)"),
    CheckItem("Neat ID (Auth)",             "Neat Common", "https",   "id.neat.no",                443, "Neat device authentication service"),
    CheckItem("Neat OTA Updates",           "Neat Common", "https",   "ota.neat.no",               443, "Firmware / OTA update server"),
    CheckItem("Neat Pulse Platform",        "Neat Common", "https",   "pulse.neat.no",             443, "Neat Pulse management platform"),
    CheckItem("Neat Pulse API",             "Neat Common", "https",   "api.pulse.neat.no",         443, "Neat Pulse management API"),
]

ZOOM: List[CheckItem] = [
    # ── Domains (KB0060548: *.zoom.us / *.zoom.com / *.zoomgov.com / *.cloudfront.net) ──
    CheckItem("zoom.us (HTTPS)",          "Zoom Rooms", "https",    "zoom.us",               443, "*.zoom.us — primary domain (TCP 443)"),
    CheckItem("zoom.us (HTTP)",           "Zoom Rooms", "tcp",      "zoom.us",                80, "*.zoom.us — HTTP (TCP 80)"),
    CheckItem("zoom.com",                 "Zoom Rooms", "https",    "zoom.com",              443, "*.zoom.com (TCP 443)"),
    CheckItem("zoomgov.com",              "Zoom Rooms", "https",    "zoomgov.com",           443, "*.zoomgov.com — US Government (TCP 443)"),
    # ── TCP media ports ──────────────────────────────────────
    CheckItem("Zoom TCP 8801",            "Zoom Rooms", "tcp",      "zoom.us",              8801, "Zoom media / control (TCP 8801)"),
    CheckItem("Zoom TCP 8802",            "Zoom Rooms", "tcp",      "zoom.us",              8802, "Zoom media / control (TCP 8802)"),
    # ── UDP media (KB0060548: UDP 3478,3479 to *.zoom.us; 8801-8810 to IP ranges) ──
    # Zoom does not publish named STUN hostnames — send to *.zoom.us endpoints
    CheckItem("Zoom UDP 3478",            "Zoom Rooms", "udp_stun", "zoom.us",              3478, "UDP 3478 → *.zoom.us (STUN / media)"),
    CheckItem("Zoom UDP 3479",            "Zoom Rooms", "udp_stun", "zoom.us",              3479, "UDP 3479 → *.zoom.us (media)"),
    # Zoom IP ranges from Zoom.txt — representative subnets, UDP 8801-8810
    CheckItem("Zoom UDP 8801 (IP range)", "Zoom Rooms", "udp_stun", "3.7.35.1",            8801, "UDP 8801 → 3.7.35.0/25 (Zoom IP range)"),
    CheckItem("Zoom UDP 8802 (IP range)", "Zoom Rooms", "udp_stun", "3.21.137.129",        8802, "UDP 8802 → 3.21.137.128/25 (Zoom IP range)"),
    CheckItem("Zoom UDP 8803 (IP range)", "Zoom Rooms", "udp_stun", "3.22.11.1",           8803, "UDP 8803 → 3.22.11.0/24 (Zoom IP range)"),
]

TEAMS: List[CheckItem] = [
    # ── Endpoint Set 11: Optimize (signaling + media) ────────
    CheckItem("*.teams.microsoft.com",    "Teams Rooms", "https",   "teams.microsoft.com",              443, "Teams core signaling (TCP 443)"),
    CheckItem("*.skype.com",              "Teams Rooms", "https",   "api.skype.com",                    443, "Teams/Skype backend (TCP 443)"),
    CheckItem("*.lync.com",               "Teams Rooms", "https",   "lync.com",                         443, "Legacy Teams signaling (TCP 443)"),
    # ── Endpoint Set 12: Allow (auth + M365 services) ────────
    CheckItem("login.microsoftonline.com","Teams Rooms", "https",   "login.microsoftonline.com",        443, "Entra ID / OAuth (TCP 443)"),
    CheckItem("graph.microsoft.com",      "Teams Rooms", "https",   "graph.microsoft.com",              443, "Microsoft Graph API (TCP 443)"),
    CheckItem("*.office365.com",          "Teams Rooms", "https",   "outlook.office365.com",            443, "Microsoft 365 services (TCP 443)"),
    CheckItem("*.microsoft.com",          "Teams Rooms", "https",   "www.microsoft.com",                443, "Microsoft CDN / services (TCP 443)"),
    CheckItem("*.office.com",             "Teams Rooms", "https",   "www.office.com",                   443, "Office platform (TCP 443)"),
    # ── UDP media — worldaz.relay.teams.microsoft.com → 52.112.0.0/14 ──
    CheckItem("Teams UDP 3478 (STUN)",    "Teams Rooms", "udp_stun","worldaz.relay.teams.microsoft.com",3478, "UDP 3478 → 52.112.0.0/14 (STUN/media)"),
    CheckItem("Teams UDP 3479 (audio)",   "Teams Rooms", "udp_stun","worldaz.relay.teams.microsoft.com",3479, "UDP 3479 → 52.112.0.0/14 (audio)"),
    CheckItem("Teams UDP 3480 (video)",   "Teams Rooms", "udp_stun","worldaz.relay.teams.microsoft.com",3480, "UDP 3480 → 52.112.0.0/14 (video)"),
    CheckItem("Teams UDP 3481 (share)",   "Teams Rooms", "udp_stun","worldaz.relay.teams.microsoft.com",3481, "UDP 3481 → 52.112.0.0/14 (screen share)"),
]

MEET: List[CheckItem] = [
    # ── Domains (knowledge.workspace.google.com) ─────────────
    CheckItem("meet.google.com",          "Google Meet", "https",   "meet.google.com",             443, "Google Meet primary (TCP 443)"),
    CheckItem("accounts.google.com",      "Google Meet", "https",   "accounts.google.com",         443, "Google authentication (TCP 443)"),
    CheckItem("apis.google.com",          "Google Meet", "https",   "apis.google.com",             443, "Google APIs (TCP 443)"),
    CheckItem("hangouts.googleapis.com",  "Google Meet", "https",   "hangouts.googleapis.com",     443, "Meet signaling (TCP 443)"),
    CheckItem("meetings.googleapis.com",  "Google Meet", "https",   "meetings.googleapis.com",     443, "Meet API (TCP 443)"),
    CheckItem("www.gstatic.com",          "Google Meet", "https",   "www.gstatic.com",             443, "Google static content (TCP 443)"),
    CheckItem("*.googleusercontent.com",  "Google Meet", "https",   "lh3.googleusercontent.com",   443, "Google user content CDN (TCP 443)"),
    # ── UDP media ─────────────────────────────────────────────
    # workspace.turns.goog → 74.125.250.0/24 (Workspace / enterprise accounts)
    CheckItem("Meet UDP 3478 (Workspace)","Google Meet", "udp_stun","workspace.turns.goog",        3478,  "UDP 3478 → 74.125.250.0/24 (Workspace)"),
    CheckItem("Meet UDP 19302 (Workspace)","Google Meet","udp_stun","workspace.turns.goog",        19302, "UDP 19302 → 74.125.250.0/24 (Workspace)"),
    CheckItem("Meet UDP 19309 (Workspace)","Google Meet","udp_stun","workspace.turns.goog",        19309, "UDP 19309 → 74.125.250.0/24 (Workspace)"),
    # meet.turns.goog → 142.250.82.0/24 (personal / non-Workspace accounts)
    CheckItem("Meet UDP 3478 (consumer)", "Google Meet", "udp_stun","meet.turns.goog",             3478,  "UDP 3478 → 142.250.82.0/24 (consumer)"),
    CheckItem("Meet UDP 19302 (consumer)","Google Meet", "udp_stun","meet.turns.goog",             19302, "UDP 19302 → 142.250.82.0/24 (consumer)"),
]

BYOD: List[CheckItem] = []  # BYOD requires only Neat Common checks

ALL_CHECKS = {"neat": NEAT_COMMON, "zoom": ZOOM, "teams": TEAMS, "meet": MEET, "byod": BYOD}

# ─────────────────────────────────────────────────────────────
# NETWORK CHECK FUNCTIONS
# ─────────────────────────────────────────────────────────────

TIMEOUT = 6

def check_https(target: str, port: int) -> Tuple[str, str, Optional[float]]:
    url = f"https://{target}/" if port == 443 else f"https://{target}:{port}/"
    start = time.time()
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers={"User-Agent": "NeatNetworkChecker/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            elapsed = (time.time() - start) * 1000
            return "pass", f"HTTP {resp.status}", elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        return ("pass", f"HTTP {e.code} (server reachable)", elapsed) if e.code < 500 \
               else ("warn", f"HTTP {e.code} (server error)", elapsed)
    except urllib.error.URLError as e:
        return "fail", f"URL error: {e.reason}", None
    except Exception as e:
        return "fail", str(e)[:120], None


def check_tcp(target: str, port: int) -> Tuple[str, str, Optional[float]]:
    start = time.time()
    try:
        ip = socket.gethostbyname(target)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        rc = sock.connect_ex((ip, port))
        elapsed = (time.time() - start) * 1000
        sock.close()
        if rc == 0:
            return "pass", f"TCP connected → {ip}:{port}", elapsed
        return "fail", f"TCP connect failed (errno {rc})", elapsed
    except socket.gaierror as e:
        return "fail", f"DNS lookup failed: {e}", None
    except socket.timeout:
        return "fail", "Connection timed out", None
    except Exception as e:
        return "fail", str(e)[:120], None


def check_udp_ntp(target: str, port: int = 123) -> Tuple[str, str, Optional[float]]:
    start = time.time()
    try:
        ip = socket.gethostbyname(target)
        pkt = bytearray(48)
        pkt[0] = 0x23   # LI=0, VN=4, Mode=3 (client)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(TIMEOUT)
        sock.sendto(bytes(pkt), (ip, port))
        data, _ = sock.recvfrom(1024)
        elapsed = (time.time() - start) * 1000
        sock.close()
        if len(data) >= 48:
            return "pass", f"NTP response from {ip} (stratum {data[1]})", elapsed
        return "warn", f"Short NTP reply ({len(data)} B) from {ip}", elapsed
    except socket.gaierror as e:
        return "fail", f"DNS lookup failed: {e}", None
    except socket.timeout:
        return "fail", "NTP request timed out — UDP 123 may be blocked", None
    except Exception as e:
        return "fail", str(e)[:120], None


def check_udp_stun(target: str, port: int) -> Tuple[str, str, Optional[float]]:
    """
    Send an RFC-5389 STUN Binding Request and interpret the response.

    Result interpretation:
      PASS  — STUN Binding Response received → port open and STUN server responding
      WARN  — Timeout with no ICMP error → UDP packet sent, no response received.
              Media ports (SRTP/RTP) are NOT required to respond to STUN probes;
              absence of ICMP Port Unreachable means the port is likely OPEN.
      FAIL  — ICMP Port Unreachable / ConnectionRefused → port is BLOCKED
            — DNS failure → hostname unresolvable
    """
    start = time.time()
    try:
        ip = socket.gethostbyname(target)
        magic  = 0x2112A442
        txn_id = os.urandom(12)
        pkt    = struct.pack(">HHI", 0x0001, 0x0000, magic) + txn_id

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(TIMEOUT)
        sock.sendto(pkt, (ip, port))
        try:
            data, _ = sock.recvfrom(1024)
            elapsed = (time.time() - start) * 1000
            sock.close()
            if len(data) >= 4:
                mt = struct.unpack(">H", data[:2])[0]
                if mt == 0x0101:
                    return "pass", f"STUN Binding Response from {ip}:{port}", elapsed
                if mt == 0x0111:
                    return "warn", f"STUN Error Response from {ip}:{port}", elapsed
                return "warn", f"Unexpected response type 0x{mt:04x} from {ip}:{port}", elapsed
            return "warn", f"Short response ({len(data)} B) from {ip}:{port}", elapsed

        except socket.timeout:
            elapsed = (time.time() - start) * 1000
            sock.close()
            # Timeout without ICMP = packet sent, no block detected
            return ("warn",
                    f"UDP packet sent to {ip}:{port} — no response (expected for media "
                    f"ports: SRTP/RTP does not reply to STUN probes). "
                    f"No ICMP block detected → port is likely OPEN.",
                    elapsed)

        except ConnectionRefusedError:
            # ICMP Port Unreachable received → port is actively blocked/closed
            elapsed = (time.time() - start) * 1000
            sock.close()
            return ("fail",
                    f"UDP {port} BLOCKED — ICMP Port Unreachable received from {ip}. "
                    f"Firewall is actively rejecting this port.",
                    elapsed)

    except socket.gaierror as e:
        return "fail", f"DNS lookup failed: {e}", None
    except Exception as e:
        return "fail", str(e)[:120], None


def check_proxy_settings() -> Tuple[str, str, Optional[float]]:
    """Detect proxy configuration from system settings and environment variables."""
    start = time.time()
    try:
        proxies   = urllib.request.getproxies()
        env_http  = os.environ.get("http_proxy",  "") or os.environ.get("HTTP_PROXY",  "")
        env_https = os.environ.get("https_proxy", "") or os.environ.get("HTTPS_PROXY", "")

        detected: dict = {}
        if proxies.get("https"): detected["System HTTPS proxy"] = proxies["https"]
        if proxies.get("http"):  detected["System HTTP proxy"]  = proxies["http"]
        if env_https:            detected["Env HTTPS_PROXY"]    = env_https
        if env_http:             detected["Env HTTP_PROXY"]     = env_http

        elapsed = (time.time() - start) * 1000

        if detected:
            lines = "; ".join(f"{k}: {v}" for k, v in detected.items())
            return ("warn",
                    f"Proxy detected — {lines}. "
                    f"UDP media traffic (STUN/RTP) typically bypasses HTTP proxies.",
                    elapsed)
        return "pass", "No proxy configured — direct connection to internet.", elapsed

    except Exception as e:
        return "fail", str(e)[:120], None


# Well-known public CA name fragments (case-insensitive)
_PUBLIC_CAS = [
    "digicert", "comodo", "globalsign", "let's encrypt", "letsencrypt",
    "sectigo", "geotrust", "entrust", "verisign", "amazon", "cloudflare",
    "baltimore", "google trust", "isrg", "quovadis", "godaddy", "usertrust",
    "cybertrust", "identrust", "comodoca", "zscaler public",
]

def check_ssl_inspection(target: str = "zoom.us", port: int = 443) -> Tuple[str, str, Optional[float]]:
    """
    Detect SSL inspection (TLS MITM) by examining the certificate issuer chain.
    If the cert is not issued by a recognized public CA, a corporate MITM proxy is likely.
    """
    start = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((target, port), timeout=TIMEOUT) as raw_sock:
            with ctx.wrap_socket(raw_sock, server_hostname=target) as ssock:
                cert    = ssock.getpeercert()
                elapsed = (time.time() - start) * 1000

                issuer: dict = {}
                for field in cert.get("issuer", []):
                    for k, v in field:
                        issuer[k] = v

                issuer_org = issuer.get("organizationName", "")
                issuer_cn  = issuer.get("commonName",       "")
                combined   = (issuer_org + " " + issuer_cn).lower()

                is_public = any(ca in combined for ca in _PUBLIC_CAS)

                if is_public:
                    return ("pass",
                            f"SSL inspection not detected — "
                            f"cert issued by public CA: {issuer_org or issuer_cn}",
                            elapsed)
                else:
                    return ("warn",
                            f"SSL inspection (TLS MITM) likely detected — "
                            f"unexpected issuer: {issuer_org or issuer_cn} ({issuer_cn}). "
                            f"Check if HTTPS decryption is enabled on your proxy/firewall.",
                            elapsed)

    except ssl.SSLCertVerificationError as e:
        elapsed = (time.time() - start) * 1000
        return ("fail",
                f"SSL certificate verification failed: {e}. "
                f"SSL inspection may be stripping/replacing the certificate.",
                elapsed)
    except socket.gaierror as e:
        return "fail", f"DNS lookup failed for {target}: {e}", None
    except Exception as e:
        return "fail", str(e)[:120], None


def check_bandwidth(direction: str = "download",
                    size_mb: int = 20) -> Tuple[str, str, Optional[float]]:
    """
    Measures download or upload throughput using Cloudflare's speed-test CDN.
    direction: "download" | "upload"
    Returns (status, message, elapsed_ms) where elapsed_ms is the total test duration.
    Thresholds for Full-HD video conferencing (strictest across Zoom/Teams/Meet):
      download ≥ 3.0 Mbps (pass), 1.5-3.0 Mbps (warn), < 1.5 Mbps (fail)
      upload   ≥ 3.8 Mbps (pass), 1.9-3.8 Mbps (warn), < 1.9 Mbps (fail)
    """
    size_bytes = size_mb * 1_000_000
    BW_TIMEOUT = 35

    try:
        if direction == "download":
            url = f"https://speed.cloudflare.com/__down?bytes={size_bytes}"
            req = urllib.request.Request(url, headers={"User-Agent": "NeatNetworkChecker/1.0"})
            t0  = time.time()
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=BW_TIMEOUT, context=ctx) as resp:
                received = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    received += len(chunk)
            elapsed_s = time.time() - t0
            mbps = (received * 8) / (elapsed_s * 1_000_000)
            elapsed_ms = elapsed_s * 1000
            label = "Download"
            pass_thr, warn_thr = 4.0, 2.0

        else:  # upload
            url     = "https://speed.cloudflare.com/__up"
            payload = b"\x00" * size_bytes
            req = urllib.request.Request(
                url, data=payload, method="POST",
                headers={
                    "User-Agent":     "NeatNetworkChecker/1.0",
                    "Content-Type":   "application/octet-stream",
                    "Content-Length": str(size_bytes),
                },
            )
            ctx = ssl.create_default_context()
            t0  = time.time()
            with urllib.request.urlopen(req, timeout=BW_TIMEOUT, context=ctx):
                pass
            elapsed_s  = time.time() - t0
            mbps       = (size_bytes * 8) / (elapsed_s * 1_000_000)
            elapsed_ms = elapsed_s * 1000
            label = "Upload"
            pass_thr, warn_thr = 3.8, 1.9

        # Platform Full-HD thresholds (per-participant, actual network requirements):
        #   Zoom 1080p:        3.8 Mbps up / 3.0 Mbps down  (KB0060748)
        #   Google Meet 1080p: 3.6 Mbps up / 3.6 Mbps down  (workspace.google.com)
        #   Teams Rooms 1080p: 4.0 Mbps up / 4.0 Mbps down  (learn.microsoft.com/microsoftteams/prepare-network)
        #   Note: Teams "Media Bit Rate" policy (10 Mbps) is an admin-configured cap,
        #         NOT the actual per-participant network bandwidth requirement.
        # NOTE: This test is HTTP/TCP. Actual video traffic is UDP (RTP/SRTP).
        #       QoS policies may cause TCP and UDP throughput to differ.
        note = ("Full-HD thresholds — Zoom 1080p: 3.8↑/3.0↓ Mbps; "
                "Google Meet 1080p: 3.6↑/3.6↓ Mbps; "
                "Teams Rooms 1080p: 4.0↑/4.0↓ Mbps. "
                "⚠ TCP reference only — actual media uses UDP (RTP/SRTP)")
        msg = (f"{label}: {mbps:.1f} Mbps  "
               f"({size_mb} MB transferred in {elapsed_s:.1f}s) — {note}")

        if mbps >= pass_thr:
            return ("pass", msg, elapsed_ms)
        elif mbps >= warn_thr:
            return ("warn",
                    f"{label}: {mbps:.1f} Mbps — below Full-HD threshold "
                    f"(≥{pass_thr} Mbps). HD video may degrade at peak load. — {note}",
                    elapsed_ms)
        else:
            return ("fail",
                    f"{label}: {mbps:.1f} Mbps — insufficient for Full-HD video "
                    f"(requires ≥{pass_thr} Mbps). — {note}",
                    elapsed_ms)

    except socket.timeout:
        return ("fail",
                f"Bandwidth {direction} test timed out after {BW_TIMEOUT}s — "
                "connection may be too slow or speed.cloudflare.com is unreachable.",
                None)
    except Exception as e:
        return ("fail", f"Bandwidth {direction} test error: {str(e)[:120]}", None)


def check_mdns(timeout: float = 3.0) -> Tuple[str, str, Optional[float]]:
    """mDNS (Multicast DNS) — RFC 6762. Queries _neat._tcp.local and _neat-oob._tcp.local."""
    MDNS_ADDR = "224.0.0.251"
    MDNS_PORT = 5353
    SERVICES  = ["_neat._tcp.local", "_neat-oob._tcp.local"]

    def build_ptr_query(service: str) -> bytes:
        hdr = b'\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
        q   = b''
        for label in service.rstrip('.').split('.'):
            enc = label.encode('ascii')
            q  += bytes([len(enc)]) + enc
        q += b'\x00\x00\x0c\x00\x01'
        return hdr + q

    start = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # type: ignore
        except AttributeError:
            pass
        sock.settimeout(timeout)
        mreq = struct.pack("4sL", socket.inet_aton(MDNS_ADDR), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.bind(('', MDNS_PORT))
        for svc in SERVICES:
            try:
                sock.sendto(build_ptr_query(svc), (MDNS_ADDR, MDNS_PORT))
            except Exception:
                pass
        responders: List[str] = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, addr = sock.recvfrom(4096)
                if data:
                    responders.append(addr[0])
            except socket.timeout:
                break
        sock.close()
        elapsed = (time.time() - start) * 1000
        if responders:
            unique = list(dict.fromkeys(responders))
            return ("pass",
                    f"mDNS response received — {len(unique)} host(s): {', '.join(unique[:5])}",
                    elapsed)
        return ("warn",
                f"No mDNS response within {timeout:.0f}s — "
                "multicast may be blocked or no Neat devices on this subnet.",
                elapsed)
    except PermissionError:
        return ("fail",
                "Cannot bind UDP 5353 — admin privileges required "
                "(macOS: run with sudo; Windows: Run as Administrator).",
                None)
    except OSError as e:
        if "Address already in use" in str(e):
            return ("fail",
                    "UDP 5353 already in use by another process (e.g. Bonjour/Avahi).",
                    None)
        return "fail", f"mDNS socket error: {e}", None
    except Exception as e:
        return "fail", str(e)[:120], None


def run_checks(modes: List[str], custom_ntp: str,
               run_proxy: bool = True, run_mdns: bool = False,
               mdns_timeout: float = 3.0,
               run_bandwidth: bool = False):
    """Generator: yields CheckResult one by one."""

    # ── Proxy & SSL inspection (always, at the top) ──────────
    if run_proxy:
        for name, fn, target, port, ctype in [
            ("Proxy Detection",  check_proxy_settings, "-", 0,   "proxy"),
            ("SSL Inspection",   lambda: check_ssl_inspection("zoom.us", 443),
                                                       "zoom.us", 443, "ssl_inspect"),
        ]:
            try:
                st, msg, lat = fn()
            except Exception as e:
                st, msg, lat = "fail", str(e)[:120], None
            yield CheckResult(name, "Security", ctype, target, port, st, msg, lat)

    # ── Bandwidth test (optional, before platform checks) ────
    if run_bandwidth:
        for direction, bw_label in [("download", "Bandwidth Download"),
                                     ("upload",   "Bandwidth Upload")]:
            try:
                st, msg, lat = check_bandwidth(direction)
            except Exception as e:
                st, msg, lat = "fail", str(e)[:120], None
            yield CheckResult(bw_label, "Bandwidth", f"bw_{direction}",
                              "speed.cloudflare.com", 443, st, msg, lat)

    # ── Platform checks ──────────────────────────────────────
    checks: List[CheckItem] = []
    for m in modes:
        checks.extend(ALL_CHECKS.get(m, []))
    ntp_target = custom_ntp or "time.neat.no"
    ntp_label  = f"NTP ({ntp_target})"
    checks.append(CheckItem(
        ntp_label, "Neat Common", "udp_ntp",
        ntp_target, 123, f"NTP server UDP 123 → {ntp_target}"
    ))

    for c in checks:
        try:
            if   c.check_type == "https":    st, msg, lat = check_https(c.target, c.port)
            elif c.check_type == "tcp":      st, msg, lat = check_tcp(c.target, c.port)
            elif c.check_type == "udp_ntp":  st, msg, lat = check_udp_ntp(c.target, c.port)
            elif c.check_type == "udp_stun": st, msg, lat = check_udp_stun(c.target, c.port)
            else:                            st, msg, lat = "warn", "Unknown check type", None
        except Exception as e:
            st, msg, lat = "fail", str(e)[:120], None
        yield CheckResult(c.name, c.category, c.check_type, c.target, c.port, st, msg, lat)

    # ── mDNS (optional, last) ─────────────────────────────────
    if run_mdns:
        try:
            st, msg, lat = check_mdns(timeout=mdns_timeout)
        except Exception as e:
            st, msg, lat = "fail", str(e)[:120], None
        yield CheckResult(
            "mDNS (_neat._tcp.local)", "mDNS", "udp_mdns",
            "224.0.0.251", 5353, st, msg, lat
        )


# ─────────────────────────────────────────────────────────────
# REPORT BUILDERS
# ─────────────────────────────────────────────────────────────

def build_html_report(results: List[CheckResult]) -> str:
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    warned = sum(1 for r in results if r.status == "warn")
    total  = len(results)
    row_bg = {"pass": "#e8f5e9", "fail": "#ffebee", "warn": "#fff8e1"}
    icons  = {"pass": "✅", "fail": "❌", "warn": "⚠️"}
    rows = ""
    for r in results:
        bg   = row_bg.get(r.status, "#fff")
        icon = icons.get(r.status, "")
        lat  = f"{r.latency_ms:.0f} ms" if r.latency_ms is not None else "—"
        port = str(r.port) if r.port > 0 else "—"
        rows += f"""
      <tr style="background:{bg}">
        <td>{r.category}</td><td>{r.name}</td>
        <td><code>{r.check_type.upper()}</code></td>
        <td><code>{r.target}</code></td>
        <td style="text-align:center">{port}</td>
        <td><strong>{icon} {r.status.upper()}</strong></td>
        <td>{r.message}</td>
        <td style="text-align:right">{lat}</td>
      </tr>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Neat Network Check — {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f0f2f5;color:#222}}
header{{background:#1a2035;color:#fff;padding:18px 28px}}
header h1{{font-size:22px;margin-bottom:4px}}
header p{{color:#90a4ae;font-size:12px}}
.summary{{display:flex;gap:12px;padding:12px 28px;background:#fff;border-bottom:1px solid #e0e0e0}}
.pill{{padding:5px 14px;border-radius:20px;font-weight:700;font-size:13px}}
.total{{background:#e3f2fd;color:#0d47a1}}.pass{{background:#e8f5e9;color:#1b5e20}}
.fail{{background:#ffebee;color:#b71c1c}}.warn{{background:#fff8e1;color:#e65100}}
main{{padding:20px 28px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;
       overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,.1)}}
thead tr{{background:#1a2035;color:#fff}}
th{{padding:10px 12px;text-align:left;font-size:12px;white-space:nowrap}}
td{{padding:7px 12px;border-bottom:1px solid #e0e0e0;font-size:12px}}
code{{background:#f5f5f5;border-radius:3px;padding:1px 4px;font-size:11px}}
footer{{text-align:center;color:#bbb;padding:14px;font-size:11px}}
</style>
</head>
<body>
<header>
  <h1>Neat Network Connectivity Check Report</h1>
  <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; Neat Network Checker v1.1</p>
</header>
<div class="summary">
  <span class="pill total">Total: {total}</span>
  <span class="pill pass">✅ Pass: {passed}</span>
  <span class="pill fail">❌ Fail: {failed}</span>
  <span class="pill warn">⚠️ Warn: {warned}</span>
</div>
<main>
<table>
  <thead><tr>
    <th>Category</th><th>Check Name</th><th>Type</th><th>Target</th>
    <th>Port</th><th>Status</th><th>Details</th><th>Latency</th>
  </tr></thead>
  <tbody>{rows}
  </tbody>
</table>
</main>
<footer>Based on <a href="https://support.neat.no/article/network-and-firewall-requirements-for-neat/"
style="color:#90a4ae">Neat Network &amp; Firewall Requirements</a></footer>
</body></html>"""

def build_csv_report(results: List[CheckResult]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Category", "Name", "Type", "Target", "Port", "Status", "Message", "Latency_ms"])
    for r in results:
        w.writerow([r.category, r.name, r.check_type, r.target,
                    r.port if r.port > 0 else "", r.status,
                    r.message, f"{r.latency_ms:.0f}" if r.latency_ms else ""])
    return out.getvalue()

# ─────────────────────────────────────────────────────────────
# HTML UI (with i18n)
# ─────────────────────────────────────────────────────────────

HTML_UI = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Neat Network Connectivity Checker</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
       background:#f0f2f5;color:#222;min-height:100vh}
  header{background:#1a2035;color:#fff;padding:12px 20px 0;
         display:flex;flex-direction:column}
  .header-top{display:flex;align-items:center;gap:14px;padding-bottom:10px}
  .logo{font-size:26px}
  .header-text h1{font-size:19px;font-weight:700}
  .header-text p{font-size:11px;color:#90a4ae;margin-top:2px}
  .lang-bar{display:flex;gap:5px;padding:6px 0 8px;border-top:1px solid rgba(255,255,255,.12);margin-top:2px}
  .lang-btn{padding:3px 10px;border-radius:4px;border:1px solid rgba(255,255,255,.25);
             background:transparent;color:#90a4ae;font-size:11px;cursor:pointer;transition:.15s}
  .lang-btn.active{background:#1565c0;color:#fff;border-color:#1565c0}
  .card{background:#fff;border-radius:10px;box-shadow:0 1px 6px rgba(0,0,0,.1);
        padding:14px 18px;margin:12px 18px 0}
  .card h2{font-size:12px;font-weight:700;color:#555;text-transform:uppercase;
           letter-spacing:.06em;margin-bottom:10px}
  /* ── Neat Common always-on row ── */
  .neat-always{display:flex;align-items:center;gap:12px;
               background:linear-gradient(90deg,#e8f5e9,#f1f8e9);
               border:2px solid #a5d6a7;border-radius:10px;
               padding:10px 14px;margin-bottom:14px}
  .neat-always-icon{font-size:20px;line-height:1}
  .neat-always-body{flex:1}
  .neat-always-title{font-size:13px;font-weight:700;color:#1b5e20}
  .neat-always-desc{font-size:11px;color:#388e3c;margin-top:2px;line-height:1.4}
  .badge-always{font-size:10px;font-weight:700;padding:3px 8px;border-radius:10px;
                background:#2e7d32;color:#fff;white-space:nowrap}
  /* ── Platform selection ── */
  .platform-label{font-size:11px;font-weight:700;color:#888;
                  text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
  .modes{display:flex;flex-wrap:wrap;gap:8px}
  .mode-btn{display:flex;align-items:center;gap:6px;padding:7px 13px;border-radius:8px;
             border:2px solid #e0e0e0;cursor:pointer;font-size:12px;font-weight:600;
             background:#fff;transition:.15s;user-select:none;color:#555}
  .mode-btn:hover{border-color:#90a4ae;background:#fafafa}
  .mode-btn.active{border-color:#1565c0;background:#e3f2fd;color:#0d47a1}
  .mode-btn input{display:none}
  .opt-row{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start}
  .opt-group{display:flex;flex-direction:column;gap:6px;flex:1;min-width:220px}
  .opt-group + .opt-group{border-left:2px solid #f0f0f0;padding-left:20px}
  .field-label{font-size:12px;font-weight:700;color:#444}
  input[type=text]{padding:6px 9px;border:1.5px solid #ddd;border-radius:7px;
    font-size:12px;outline:none;transition:.15s;width:100%;max-width:280px}
  input[type=text]:focus{border-color:#1565c0}
  input[type=number]{width:68px;padding:6px 9px;border:1.5px solid #ddd;border-radius:7px;
    font-size:12px;outline:none;transition:.15s}
  input[type=number]:focus{border-color:#1565c0}
  .hint{font-size:11px;color:#999;line-height:1.4}
  .toggle-wrap{display:flex;align-items:center;gap:7px;cursor:pointer;user-select:none}
  .toggle-wrap input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#1565c0}
  .toggle-label{font-size:12px;font-weight:700;color:#444}
  .tag{display:inline-block;font-size:10px;font-weight:700;padding:1px 6px;border-radius:10px;
       background:#fff3e0;color:#e65100;margin-left:4px;vertical-align:middle}
  .tag.security{background:#e8eaf6;color:#3949ab}
  .tag.bandwidth{background:#e0f7fa;color:#00695c}
  .ref-grid{display:flex;gap:16px;flex-wrap:wrap}
  .ref-group{flex:1;min-width:190px;border-left:3px solid #e0e0e0;padding-left:10px}
  .ref-group-title{font-size:12px;font-weight:700;color:#333;margin-bottom:5px}
  .ref-link{display:block;font-size:11px;color:#1565c0;text-decoration:none;
            line-height:1.7;word-break:break-word}
  .ref-link:hover{text-decoration:underline}
  tr.bandwidth td:first-child{border-left:3px solid #00acc1}
  tr.bandwidth{background:#f0fdfd}
  .timeout-row{display:flex;align-items:center;gap:7px;margin-top:4px}
  .controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  button{padding:8px 18px;border:none;border-radius:7px;font-size:12px;
         font-weight:700;cursor:pointer;transition:.15s}
  button:disabled{opacity:.42;cursor:not-allowed}
  #btnStart{background:#1565c0;color:#fff}
  #btnStart:hover:not(:disabled){background:#0d47a1}
  #btnStop{background:#c62828;color:#fff}
  #btnStop:hover:not(:disabled){background:#b71c1c}
  #btnExportHTML{background:#2e7d32;color:#fff}
  #btnExportHTML:hover:not(:disabled){background:#1b5e20}
  #btnExportCSV{background:#4527a0;color:#fff}
  #btnExportCSV:hover:not(:disabled){background:#311b92}
  .pb-wrap{flex:1;min-width:160px}
  progress{width:100%;height:7px;border-radius:4px;border:none;overflow:hidden}
  progress::-webkit-progress-bar{background:#e0e0e0;border-radius:4px}
  progress::-webkit-progress-value{background:#1565c0;border-radius:4px;transition:width .3s}
  progress::-moz-progress-bar{background:#1565c0;border-radius:4px}
  #statusText{font-size:11px;color:#777;margin-top:3px}
  .summary-bar{display:flex;gap:8px;flex-wrap:wrap}
  .pill{padding:4px 13px;border-radius:20px;font-size:12px;font-weight:700}
  .pill.total{background:#e3f2fd;color:#0d47a1}
  .pill.pass{background:#e8f5e9;color:#1b5e20}
  .pill.fail{background:#ffebee;color:#b71c1c}
  .pill.warn{background:#fff8e1;color:#e65100}
  .table-wrap{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:11px;min-width:720px}
  thead tr{background:#1a2035;color:#fff}
  th{padding:8px 10px;text-align:left;white-space:nowrap;font-size:10px;
     letter-spacing:.04em;cursor:pointer;user-select:none}
  th:hover{background:#263154}
  td{padding:6px 10px;border-bottom:1px solid #f0f0f0;vertical-align:top}
  tr.pass td:first-child{border-left:3px solid #43a047}
  tr.fail td:first-child{border-left:3px solid #e53935}
  tr.warn td:first-child{border-left:3px solid #fb8c00}
  tr.security td:first-child{border-left:3px solid #5c6bc0}
  tr.pass{background:#f9fffe}
  tr.fail{background:#fff8f8}
  tr.warn{background:#fffdf4}
  tr.security{background:#f5f5ff}
  .badge{display:inline-block;padding:2px 7px;border-radius:10px;
          font-size:10px;font-weight:700;white-space:nowrap}
  .badge.pass{background:#e8f5e9;color:#2e7d32}
  .badge.fail{background:#ffebee;color:#c62828}
  .badge.warn{background:#fff3e0;color:#e65100}
  code{background:#f5f5f5;border-radius:3px;padding:1px 4px;font-size:10px;font-family:monospace}
  .lat{text-align:right;color:#888;font-variant-numeric:tabular-nums;white-space:nowrap}
  .details-cell{max-width:340px;word-break:break-word;line-height:1.4}
  footer{text-align:center;color:#bbb;padding:14px;font-size:11px}
</style>
</head>
<body>

<header>
  <div class="header-top">
    <div class="logo">🔌</div>
    <div class="header-text">
      <h1 data-i18n="title">Neat Network Connectivity Checker</h1>
      <p data-i18n="subtitle">Validates firewall &amp; network requirements for Neat devices</p>
    </div>
  </div>
  <div class="lang-bar">
    <button class="lang-btn active" onclick="setLang('en')">EN</button>
    <button class="lang-btn" onclick="setLang('ja')">日本語</button>
    <button class="lang-btn" onclick="setLang('ko')">한국어</button>
    <button class="lang-btn" onclick="setLang('zh_tw')">繁中</button>
    <button class="lang-btn" onclick="setLang('zh_cn')">简中</button>
  </div>
</header>

<!-- Check Modes -->
<div class="card">
  <h2 data-i18n="section_modes">Check Modes</h2>

  <!-- Neat Common — always included -->
  <div class="neat-always">
    <div class="neat-always-icon">🖥</div>
    <div class="neat-always-body">
      <div class="neat-always-title">Neat Common</div>
      <div class="neat-always-desc" data-i18n="neat_always_desc">
        connectivitycheck · id · ota · pulse · api.pulse · NTP (time.neat.no)
      </div>
    </div>
    <span class="badge-always" data-i18n="neat_always_badge">Always included</span>
  </div>

  <!-- Platform selection -->
  <div class="platform-label" data-i18n="section_platform">Select platform to check (optional)</div>
  <div class="modes" id="modeGroup">
    <label class="mode-btn" title="" data-i18n-title="byod_title">
      <input type="checkbox" value="zoom"> 🔵 Zoom Rooms
    </label>
    <label class="mode-btn" title="" data-i18n-title="byod_title">
      <input type="checkbox" value="teams"> 🟣 Teams Rooms
    </label>
    <label class="mode-btn" title="" data-i18n-title="byod_title">
      <input type="checkbox" value="meet"> 🟢 Google Meet
    </label>
    <label class="mode-btn" title="" data-i18n-title="byod_title">
      <input type="checkbox" value="byod"> 💻 BYOD
    </label>
  </div>
  <p class="hint" style="margin-top:10px" data-i18n="direct_guest_hint">
    If your Neat device uses Direct Guest Join to connect to platforms other than its primary platform (e.g., a Zoom Rooms device joining a Teams or Google Meet meeting), also select and check those platforms above.
  </p>
</div>

<!-- Reference Documentation -->
<div class="card">
  <h2 data-i18n="section_refs">Reference Documentation</h2>
  <div class="ref-grid">
    <div class="ref-group">
      <div class="ref-group-title">🖥 Neat</div>
      <a class="ref-link" href="https://support.neat.no/article/network-and-firewall-requirements-for-neat/" target="_blank" data-i18n="ref_neat_fw">Network &amp; Firewall Requirements</a>
    </div>
    <div class="ref-group">
      <div class="ref-group-title">🔵 Zoom Rooms</div>
      <a class="ref-link" href="https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712" target="_blank" data-i18n="ref_zoom_fw">Network Firewall Rules for Zoom</a>
      <a class="ref-link" href="https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548" target="_blank" data-i18n="ref_zoom_net">Zoom Rooms Network Requirements</a>
      <a class="ref-link" href="https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748" target="_blank" data-i18n="ref_zoom_bw">Zoom Bandwidth Requirements</a>
    </div>
    <div class="ref-group">
      <div class="ref-group-title">🟣 Teams Rooms</div>
      <a class="ref-link" href="https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams" target="_blank" data-i18n="ref_teams_net">Microsoft 365 URLs &amp; IP Ranges (Teams)</a>
      <a class="ref-link" href="https://learn.microsoft.com/en-us/microsoftteams/meeting-policies-audio-and-video#media-bit-rate-kbps" target="_blank" data-i18n="ref_teams_bw">Teams Media Bit Rate Policy</a>
    </div>
    <div class="ref-group">
      <div class="ref-group-title">🟢 Google Meet</div>
      <a class="ref-link" href="https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams" target="_blank" data-i18n="ref_meet_net">Prepare Your Network for Meet</a>
    </div>
  </div>
</div>

<!-- Optional Checks -->
<div class="card">
  <h2 data-i18n="section_options">Optional Checks</h2>
  <div class="opt-row">

    <!-- NTP -->
    <div class="opt-group">
      <span class="field-label" data-i18n="ntp_label">NTP Server</span>
      <input type="text" id="ntpInput" value="time.neat.no">
      <span class="hint" data-i18n="ntp_hint">NTP server to check (UDP 123). Default: time.neat.no</span>
    </div>

    <!-- mDNS -->
    <div class="opt-group">
      <label class="toggle-wrap">
        <input type="checkbox" id="mdnsCheck">
        <span class="toggle-label" data-i18n="mdns_label">mDNS Check</span>
        <span class="tag" data-i18n="mdns_tag">Local Network</span>
      </label>
      <span class="hint" data-i18n="mdns_hint">Sends PTR query to 224.0.0.251:5353 to verify multicast connectivity and Neat device discovery.</span>
      <span class="hint" data-i18n="mdns_note">May require admin privileges (macOS: sudo, Windows: Run as Administrator).</span>
      <div class="timeout-row" id="mdnsOptions" style="display:none">
        <span class="field-label" data-i18n="mdns_timeout_label">Timeout:</span>
        <input type="number" id="mdnsTimeout" value="3" min="1" max="10">
        <span class="hint" data-i18n="mdns_timeout_unit">sec</span>
      </div>
    </div>

    <!-- Proxy / SSL Inspection -->
    <div class="opt-group">
      <label class="toggle-wrap">
        <input type="checkbox" id="proxyCheck" checked>
        <span class="toggle-label" data-i18n="proxy_label">Proxy &amp; SSL Inspection</span>
        <span class="tag security" data-i18n="proxy_tag">Security</span>
      </label>
      <span class="hint" data-i18n="proxy_hint">Detects proxy configuration and checks for TLS MITM (SSL inspection) by examining certificate issuers.</span>
    </div>

    <!-- Bandwidth Test -->
    <div class="opt-group">
      <label class="toggle-wrap">
        <input type="checkbox" id="bwCheck">
        <span class="toggle-label" data-i18n="bw_label">Bandwidth Test</span>
        <span class="tag bandwidth" data-i18n="bw_tag">Speed</span>
      </label>
      <span class="hint" data-i18n="bw_hint">Downloads and uploads 20 MB via Cloudflare to measure throughput. Validates Full-HD video requirements: Zoom 1080p 3.8↑/3.0↓ Mbps, Google Meet 1080p 3.6↑/3.6↓ Mbps, Teams Rooms 1080p 4.0↑/4.0↓ Mbps.</span>
      <span class="hint" data-i18n="bw_note">⚠️ This test uses HTTP (TCP). Actual video/audio traffic is UDP (RTP/SRTP). Results are a TCP reference — QoS policies may cause TCP and UDP throughput to differ.</span>
    </div>

  </div>
</div>

<!-- Controls -->
<div class="card">
  <div class="controls">
    <button id="btnStart" data-i18n="btn_start">▶ Start Check</button>
    <button id="btnStop" disabled data-i18n="btn_stop">⏹ Stop</button>
    <button id="btnExportHTML" disabled data-i18n="btn_export_html">📄 Export HTML</button>
    <button id="btnExportCSV" disabled data-i18n="btn_export_csv">📊 Export CSV</button>
    <div class="pb-wrap">
      <progress id="pb" value="0" max="100"></progress>
      <div id="statusText" data-i18n="status_ready">Ready</div>
    </div>
  </div>
</div>

<!-- Summary -->
<div class="card" id="summaryCard" style="display:none">
  <div class="summary-bar" id="summaryBar"></div>
</div>

<!-- Results -->
<div class="card">
  <h2 data-i18n="section_results">Results</h2>
  <div class="table-wrap">
    <table id="resultsTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)" data-i18n="col_category">Category ↕</th>
          <th onclick="sortTable(1)" data-i18n="col_name">Check Name ↕</th>
          <th onclick="sortTable(2)" data-i18n="col_type">Type</th>
          <th onclick="sortTable(3)" data-i18n="col_target">Target</th>
          <th onclick="sortTable(4)" data-i18n="col_port">Port ↕</th>
          <th onclick="sortTable(5)" data-i18n="col_status">Status ↕</th>
          <th data-i18n="col_details">Details</th>
          <th onclick="sortTable(7)" data-i18n="col_latency">Latency ↕</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>

<footer>
  <span data-i18n="footer_text">Based on</span>
  <a href="https://support.neat.no/article/network-and-firewall-requirements-for-neat/"
     target="_blank" style="color:#90a4ae"> Neat Network &amp; Firewall Requirements</a>
</footer>

<script>
// ═══════════════════════════════════════════════════
// i18n
// ═══════════════════════════════════════════════════
const LANGS = {
  en: {
    title:"Neat Network Connectivity Checker",
    subtitle:"Validates firewall & network requirements for Neat devices",
    section_modes:"Check Modes",
    neat_always_badge:"Always included",
    neat_always_desc:"connectivitycheck · id · ota · pulse · api.pulse · NTP (time.neat.no)",
    section_platform:"Select platform to check (optional)",
    direct_guest_hint:"If your Neat device uses Direct Guest Join to connect to platforms other than its primary platform (e.g., a Zoom Rooms device joining a Teams or Google Meet meeting), also select and check those platforms above.",
    section_options:"Optional Checks",
    ntp_label:"NTP Server",
    ntp_hint:"NTP server to check (UDP 123). Default: time.neat.no",
    mdns_label:"mDNS Check",
    mdns_tag:"Local Network",
    mdns_hint:"Sends PTR query to 224.0.0.251:5353 to verify multicast connectivity and Neat device discovery.",
    mdns_note:"May require admin privileges (macOS: sudo, Windows: Run as Administrator).",
    mdns_timeout_label:"Timeout:",
    mdns_timeout_unit:"sec",
    proxy_label:"Proxy & SSL Inspection",
    proxy_tag:"Security",
    proxy_hint:"Detects proxy configuration and checks for TLS MITM (SSL inspection) by examining certificate issuers.",
    bw_label:"Bandwidth Test",
    bw_tag:"Speed",
    bw_hint:"Downloads and uploads 20 MB via Cloudflare to measure throughput. Validates Full-HD: Zoom 1080p 3.8↑/3.0↓ Mbps, Google Meet 1080p 3.6↑/3.6↓ Mbps, Teams Rooms 1080p 4.0↑/4.0↓ Mbps.",
    bw_note:"⚠️ This test uses HTTP (TCP). Actual video/audio traffic is UDP (RTP/SRTP). Results are a TCP reference — QoS policies may cause TCP and UDP throughput to differ.",
    section_refs:"Reference Documentation",
    ref_neat_fw:"Network & Firewall Requirements",
    ref_zoom_fw:"Network Firewall Rules for Zoom",
    ref_zoom_net:"Zoom Rooms Network Requirements",
    ref_zoom_bw:"Zoom Bandwidth Requirements",
    ref_teams_net:"Microsoft 365 URLs & IP Ranges (Teams)",
    ref_teams_bw:"Teams Media Bit Rate Policy",
    ref_meet_net:"Prepare Your Network for Meet",
    btn_start:"▶ Start Check",
    btn_stop:"⏹ Stop",
    btn_export_html:"📄 Export HTML",
    btn_export_csv:"📊 Export CSV",
    status_ready:"Ready",
    col_category:"Category",
    col_name:"Check Name",
    col_type:"Type",
    col_target:"Target",
    col_port:"Port",
    col_status:"Status",
    col_details:"Details",
    col_latency:"Latency",
    section_results:"Results",
    alert_no_mode:"Please select at least one check mode.",
    footer_text:"Based on",
    sum_total:"Total",sum_pass:"Pass",sum_fail:"Fail",sum_warn:"Warn",
    byod_title:"BYOD mode is covered by Neat Common checks"
  },
  ja: {
    title:"Neat ネットワーク接続チェッカー",
    subtitle:"Neat デバイスのファイアウォール・ネットワーク要件を検証します",
    section_modes:"チェックモード",
    neat_always_badge:"常時実行",
    neat_always_desc:"connectivitycheck · id · ota · pulse · api.pulse · NTP (time.neat.no)",
    section_platform:"プラットフォームを選択（オプション）",
    direct_guest_hint:"ダイレクトゲスト参加を利用して、メインプラットフォーム以外の会議に接続する場合（例：Zoom Rooms デバイスが Teams や Google Meet の会議に参加する場合）は、該当するプラットフォームも上記で選択してチェックしてください。",
    section_options:"オプションチェック",
    ntp_label:"NTP サーバ",
    ntp_hint:"チェックする NTP サーバ（UDP 123）。デフォルト: time.neat.no",
    mdns_label:"mDNS チェック",
    mdns_tag:"ローカルネットワーク",
    mdns_hint:"224.0.0.251:5353 に PTR クエリを送信し、マルチキャスト疎通と Neat デバイス検出を確認します。",
    mdns_note:"管理者権限が必要な場合があります（macOS: sudo、Windows: 管理者として実行）。",
    mdns_timeout_label:"タイムアウト:",
    mdns_timeout_unit:"秒",
    proxy_label:"プロキシ & SSL インスペクション",
    proxy_tag:"セキュリティ",
    proxy_hint:"プロキシ設定を検出し、証明書発行者を確認して TLS MITM（SSL インスペクション）の有無をチェックします。",
    bw_label:"帯域幅テスト",
    bw_tag:"速度",
    bw_hint:"Cloudflare 経由で 20 MB の送受信を行い、スループットを測定します。Full HD 要件: Zoom 1080p 3.8↑/3.0↓ Mbps、Google Meet 1080p 3.6↑/3.6↓ Mbps、Teams Rooms 1080p 4.0↑/4.0↓ Mbps。",
    bw_note:"⚠️ このテストは HTTP (TCP) を使用します。実際の映像・音声通信は UDP (RTP/SRTP) です。QoS ポリシーによって TCP と UDP の帯域が異なる場合があります。",
    section_refs:"参照ドキュメント",
    ref_neat_fw:"ネットワーク & ファイアウォール要件",
    ref_zoom_fw:"Zoom ネットワークファイアウォールルール",
    ref_zoom_net:"Zoom Rooms ネットワーク要件",
    ref_zoom_bw:"Zoom 帯域幅要件",
    ref_teams_net:"Microsoft 365 URL & IP アドレス範囲 (Teams)",
    ref_teams_bw:"Teams メディアビットレートポリシー",
    ref_meet_net:"Meet のネットワーク準備",
    btn_start:"▶ チェック開始",
    btn_stop:"⏹ 停止",
    btn_export_html:"📄 HTML レポート出力",
    btn_export_csv:"📊 CSV 出力",
    status_ready:"準備完了",
    col_category:"カテゴリ",
    col_name:"チェック項目",
    col_type:"種別",
    col_target:"対象",
    col_port:"ポート",
    col_status:"状態",
    col_details:"詳細",
    col_latency:"応答時間",
    section_results:"チェック結果",
    alert_no_mode:"少なくとも1つのモードを選択してください。",
    footer_text:"基づく:",
    sum_total:"合計",sum_pass:"正常",sum_fail:"失敗",sum_warn:"警告",
    byod_title:"BYOD モードは Neat Common チェックで網羅されます"
  },
  ko: {
    title:"Neat 네트워크 연결 검사기",
    subtitle:"Neat 디바이스의 방화벽 및 네트워크 요구사항을 검증합니다",
    section_modes:"검사 모드",
    neat_always_badge:"항상 포함",
    neat_always_desc:"connectivitycheck · id · ota · pulse · api.pulse · NTP (time.neat.no)",
    section_platform:"플랫폼 선택 (선택 사항)",
    direct_guest_hint:"다이렉트 게스트 참가를 이용하여 기본 플랫폼 외 회의에 접속하는 경우(예: Zoom Rooms 디바이스가 Teams 또는 Google Meet 회의에 참가하는 경우), 해당 플랫폼도 위에서 선택하여 검사하세요.",
    section_options:"선택 검사",
    ntp_label:"NTP 서버",
    ntp_hint:"검사할 NTP 서버 (UDP 123). 기본값: time.neat.no",
    mdns_label:"mDNS 검사",
    mdns_tag:"로컬 네트워크",
    mdns_hint:"224.0.0.251:5353으로 PTR 쿼리를 전송하여 멀티캐스트 연결 및 Neat 디바이스 검색을 확인합니다.",
    mdns_note:"관리자 권한이 필요할 수 있습니다 (macOS: sudo, Windows: 관리자 권한으로 실행).",
    mdns_timeout_label:"타임아웃:",
    mdns_timeout_unit:"초",
    proxy_label:"프록시 & SSL 검사",
    proxy_tag:"보안",
    proxy_hint:"프록시 설정을 감지하고 인증서 발급자를 확인하여 TLS MITM(SSL 검사) 여부를 확인합니다.",
    bw_label:"대역폭 테스트",
    bw_tag:"속도",
    bw_hint:"Cloudflare를 통해 20 MB를 송수신하여 처리량을 측정합니다. Full HD 요건: Zoom 1080p 3.8↑/3.0↓ Mbps, Google Meet 1080p 3.6↑/3.6↓ Mbps, Teams Rooms 1080p 4.0↑/4.0↓ Mbps.",
    bw_note:"⚠️ 이 테스트는 HTTP(TCP)를 사용합니다. 실제 영상·음성 트래픽은 UDP(RTP/SRTP)입니다. QoS 정책에 따라 TCP와 UDP 대역폭이 다를 수 있습니다.",
    section_refs:"참조 문서",
    ref_neat_fw:"네트워크 & 방화벽 요건",
    ref_zoom_fw:"Zoom 네트워크 방화벽 규칙",
    ref_zoom_net:"Zoom Rooms 네트워크 요건",
    ref_zoom_bw:"Zoom 대역폭 요건",
    ref_teams_net:"Microsoft 365 URL & IP 주소 범위 (Teams)",
    ref_teams_bw:"Teams 미디어 비트레이트 정책",
    ref_meet_net:"Meet 네트워크 준비",
    btn_start:"▶ 검사 시작",
    btn_stop:"⏹ 중지",
    btn_export_html:"📄 HTML 내보내기",
    btn_export_csv:"📊 CSV 내보내기",
    status_ready:"준비됨",
    col_category:"카테고리",
    col_name:"검사 항목",
    col_type:"유형",
    col_target:"대상",
    col_port:"포트",
    col_status:"상태",
    col_details:"상세",
    col_latency:"응답 시간",
    section_results:"검사 결과",
    alert_no_mode:"검사 모드를 하나 이상 선택해주세요.",
    footer_text:"기반:",
    sum_total:"합계",sum_pass:"정상",sum_fail:"실패",sum_warn:"경고",
    byod_title:"BYOD 모드는 Neat Common 검사로 충분합니다"
  },
  zh_tw: {
    title:"Neat 網路連線檢查工具",
    subtitle:"驗證 Neat 裝置的防火牆和網路需求",
    section_modes:"檢查模式",
    neat_always_badge:"永遠包含",
    neat_always_desc:"connectivitycheck · id · ota · pulse · api.pulse · NTP (time.neat.no)",
    section_platform:"選擇平台（可選）",
    direct_guest_hint:"若您的 Neat 裝置透過「直接訪客加入」連接至主要平台以外的會議（例如：Zoom Rooms 裝置加入 Teams 或 Google Meet 會議），請同時選取並檢查上方對應的平台。",
    section_options:"選用檢查",
    ntp_label:"NTP 伺服器",
    ntp_hint:"要檢查的 NTP 伺服器（UDP 123）。預設：time.neat.no",
    mdns_label:"mDNS 檢查",
    mdns_tag:"本地網路",
    mdns_hint:"向 224.0.0.251:5353 傳送 PTR 查詢，確認多播連通性與 Neat 裝置探索。",
    mdns_note:"可能需要管理員權限（macOS：sudo，Windows：以系統管理員身分執行）。",
    mdns_timeout_label:"逾時：",
    mdns_timeout_unit:"秒",
    proxy_label:"Proxy 與 SSL 檢查",
    proxy_tag:"安全性",
    proxy_hint:"偵測 Proxy 設定，並透過檢查憑證發行者確認是否存在 TLS MITM（SSL 解密）。",
    bw_label:"頻寬測試",
    bw_tag:"速度",
    bw_hint:"透過 Cloudflare 傳輸 20 MB 以測量吞吐量。Full HD 要求：Zoom 1080p 3.8↑/3.0↓ Mbps、Google Meet 1080p 3.6↑/3.6↓ Mbps、Teams Rooms 1080p 4.0↑/4.0↓ Mbps。",
    bw_note:"⚠️ 此測試使用 HTTP（TCP）。實際影音流量為 UDP（RTP/SRTP）。QoS 政策可能導致 TCP 與 UDP 頻寬有所差異。",
    section_refs:"參考文件",
    ref_neat_fw:"網路與防火牆需求",
    ref_zoom_fw:"Zoom 網路防火牆規則",
    ref_zoom_net:"Zoom Rooms 網路需求",
    ref_zoom_bw:"Zoom 頻寬需求",
    ref_teams_net:"Microsoft 365 URL 與 IP 位址範圍（Teams）",
    ref_teams_bw:"Teams 媒體位元率原則",
    ref_meet_net:"為 Meet 準備網路",
    btn_start:"▶ 開始檢查",
    btn_stop:"⏹ 停止",
    btn_export_html:"📄 匯出 HTML",
    btn_export_csv:"📊 匯出 CSV",
    status_ready:"就緒",
    col_category:"類別",
    col_name:"檢查項目",
    col_type:"類型",
    col_target:"目標",
    col_port:"埠號",
    col_status:"狀態",
    col_details:"詳細資訊",
    col_latency:"延遲",
    section_results:"檢查結果",
    alert_no_mode:"請選擇至少一個檢查模式。",
    footer_text:"基於",
    sum_total:"總計",sum_pass:"通過",sum_fail:"失敗",sum_warn:"警告",
    byod_title:"BYOD 模式僅需 Neat Common 檢查"
  },
  zh_cn: {
    title:"Neat 网络连接检查工具",
    subtitle:"验证 Neat 设备的防火墙和网络需求",
    section_modes:"检查模式",
    neat_always_badge:"始终包含",
    neat_always_desc:"connectivitycheck · id · ota · pulse · api.pulse · NTP (time.neat.no)",
    section_platform:"选择平台（可选）",
    direct_guest_hint:"如果您的 Neat 设备通过「直接访客加入」连接到主平台以外的会议（例如：Zoom Rooms 设备加入 Teams 或 Google Meet 会议），请同时选择并检查上方对应的平台。",
    section_options:"可选检查",
    ntp_label:"NTP 服务器",
    ntp_hint:"要检查的 NTP 服务器（UDP 123）。默认：time.neat.no",
    mdns_label:"mDNS 检查",
    mdns_tag:"本地网络",
    mdns_hint:"向 224.0.0.251:5353 发送 PTR 查询，确认组播连通性与 Neat 设备发现。",
    mdns_note:"可能需要管理员权限（macOS：sudo，Windows：以管理员身份运行）。",
    mdns_timeout_label:"超时：",
    mdns_timeout_unit:"秒",
    proxy_label:"代理 & SSL 检查",
    proxy_tag:"安全",
    proxy_hint:"检测代理配置，并通过检查证书颁发机构确认是否存在 TLS MITM（SSL 解密）。",
    bw_label:"带宽测试",
    bw_tag:"速度",
    bw_hint:"通过 Cloudflare 传输 20 MB 以测量吞吐量。Full HD 要求：Zoom 1080p 3.8↑/3.0↓ Mbps、Google Meet 1080p 3.6↑/3.6↓ Mbps、Teams Rooms 1080p 4.0↑/4.0↓ Mbps。",
    bw_note:"⚠️ 此测试使用 HTTP（TCP）。实际音视频流量为 UDP（RTP/SRTP）。QoS 策略可能导致 TCP 与 UDP 带宽存在差异。",
    section_refs:"参考文档",
    ref_neat_fw:"网络与防火墙要求",
    ref_zoom_fw:"Zoom 网络防火墙规则",
    ref_zoom_net:"Zoom Rooms 网络要求",
    ref_zoom_bw:"Zoom 带宽要求",
    ref_teams_net:"Microsoft 365 URL 与 IP 地址范围（Teams）",
    ref_teams_bw:"Teams 媒体比特率策略",
    ref_meet_net:"为 Meet 准备网络",
    btn_start:"▶ 开始检查",
    btn_stop:"⏹ 停止",
    btn_export_html:"📄 导出 HTML",
    btn_export_csv:"📊 导出 CSV",
    status_ready:"就绪",
    col_category:"类别",
    col_name:"检查项目",
    col_type:"类型",
    col_target:"目标",
    col_port:"端口",
    col_status:"状态",
    col_details:"详细信息",
    col_latency:"延迟",
    section_results:"检查结果",
    alert_no_mode:"请至少选择一个检查模式。",
    footer_text:"基于",
    sum_total:"总计",sum_pass:"通过",sum_fail:"失败",sum_warn:"警告",
    byod_title:"BYOD 模式仅需 Neat Common 检查"
  }
};

let curLang = 'en';
function t(key) { return LANGS[curLang][key] || LANGS.en[key] || key; }

function setLang(code) {
  curLang = code;
  document.querySelectorAll('.lang-btn').forEach(b => {
    b.classList.toggle('active', b.textContent.trim() === {
      en:'EN', ja:'日本語', ko:'한국어', zh_tw:'繁中', zh_cn:'简中'
    }[code]);
  });
  applyLang();
}

function applyLang() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.getAttribute('data-i18n-title'));
  });
  // Re-apply ↕ sort indicators to column headers
  document.querySelectorAll('th[onclick]').forEach(th => {
    const key = th.getAttribute('data-i18n');
    if (key) th.textContent = t(key) + ' ↕';
  });
  // Non-sortable headers
  ['col_type','col_target','col_details'].forEach(k => {
    const el = document.querySelector(`th[data-i18n="${k}"]`);
    if (el) el.textContent = t(k);
  });
}

// ── Mode toggle ──────────────────────────────────────────────
document.querySelectorAll('.mode-btn').forEach(lbl => {
  const cb = lbl.querySelector('input');
  lbl.addEventListener('click', () => {
    cb.checked = !cb.checked;
    lbl.classList.toggle('active', cb.checked);
  });
});

// ── mDNS toggle ──────────────────────────────────────────────
document.getElementById('mdnsCheck').addEventListener('change', function() {
  document.getElementById('mdnsOptions').style.display = this.checked ? 'flex' : 'none';
});

// ── State ────────────────────────────────────────────────────
let es = null, totalChecks = 0, doneChecks = 0;
const icons = {pass:'✅', fail:'❌', warn:'⚠️'};

// ── Start ─────────────────────────────────────────────────────
document.getElementById('btnStart').addEventListener('click', () => {
  // Neat Common is always included; add selected platforms on top
  const platforms = [...document.querySelectorAll('.mode-btn input:checked')].map(c=>c.value);
  const modes = ['neat', ...platforms];
  const ntp         = document.getElementById('ntpInput').value.trim() || 'time.neat.no';
  const mdns        = document.getElementById('mdnsCheck').checked;
  const mdnsTimeout = document.getElementById('mdnsTimeout').value || '3';
  const runProxy    = document.getElementById('proxyCheck').checked;
  const runBw       = document.getElementById('bwCheck').checked;

  document.getElementById('tbody').innerHTML = '';
  document.getElementById('summaryCard').style.display = 'none';
  document.getElementById('summaryBar').innerHTML = '';
  document.getElementById('pb').value = 0;
  document.getElementById('statusText').textContent = t('status_ready') + '…';
  document.getElementById('btnStart').disabled = true;
  document.getElementById('btnStop').disabled = false;
  document.getElementById('btnExportHTML').disabled = true;
  document.getElementById('btnExportCSV').disabled = true;
  doneChecks = 0; totalChecks = 0;

  let qs = 'modes=' + modes.join(',');
  qs += '&ntp=' + encodeURIComponent(ntp);
  if (mdns)     qs += '&mdns=1&mdns_timeout=' + encodeURIComponent(mdnsTimeout);
  if (runProxy) qs += '&proxy=1';
  if (runBw)    qs += '&bw=1';
  es = new EventSource('/api/check?' + qs);

  es.addEventListener('total', e => {
    totalChecks = parseInt(e.data);
    document.getElementById('pb').max = totalChecks;
  });

  es.addEventListener('result', e => {
    const r = JSON.parse(e.data);
    addRow(r);
    doneChecks++;
    document.getElementById('pb').value = doneChecks;
    document.getElementById('statusText').textContent =
      `[${doneChecks}/${totalChecks||'?'}] ${r.name}`;
  });

  es.addEventListener('done', e => {
    es.close(); es = null;
    const s = JSON.parse(e.data);
    showSummary(s);
    document.getElementById('statusText').textContent =
      `Done — ${s.pass}/${s.total} passed` + (s.fail ? `, ${s.fail} FAILED` : '');
    document.getElementById('btnStart').disabled = false;
    document.getElementById('btnStop').disabled = true;
    document.getElementById('btnExportHTML').disabled = false;
    document.getElementById('btnExportCSV').disabled = false;
  });

  es.onerror = () => {
    if (es) { es.close(); es = null; }
    document.getElementById('btnStart').disabled = false;
    document.getElementById('btnStop').disabled = true;
    document.getElementById('statusText').textContent = 'Connection error';
  };
});

// ── Stop ──────────────────────────────────────────────────────
document.getElementById('btnStop').addEventListener('click', () => {
  if (es) { es.close(); es = null; }
  fetch('/api/stop', {method:'POST'});
  document.getElementById('btnStart').disabled = false;
  document.getElementById('btnStop').disabled = true;
  document.getElementById('statusText').textContent = t('btn_stop');
});

// ── Export ────────────────────────────────────────────────────
document.getElementById('btnExportHTML').addEventListener('click',
  () => window.open('/api/export?format=html', '_blank'));
document.getElementById('btnExportCSV').addEventListener('click', () => {
  const a = document.createElement('a');
  a.href = '/api/export?format=csv';
  a.download = 'neat_network_check.csv';
  a.click();
});

// ── Row ───────────────────────────────────────────────────────
function addRow(r) {
  const tr = document.createElement('tr');
  // Special categories get their own class; otherwise use status for row colour
  const rowClass = r.category === 'Security'   ? 'security'  :
                   r.category === 'Bandwidth'  ? 'bandwidth' : r.status;
  tr.className = rowClass;
  const lat  = r.latency_ms != null ? r.latency_ms.toFixed(0) + ' ms' : '—';
  const port = (r.port > 0) ? r.port : '—';
  const typeLbl = {
    udp_stun:'UDP STUN', udp_ntp:'UDP NTP', udp_mdns:'UDP mDNS',
    proxy:'PROXY', ssl_inspect:'SSL',
    bw_download:'BW DOWN', bw_upload:'BW UP'
  }[r.check_type] || r.check_type.toUpperCase();
  tr.innerHTML = `
    <td>${r.category}</td>
    <td>${r.name}</td>
    <td><code>${typeLbl}</code></td>
    <td><code>${r.target}</code></td>
    <td style="text-align:center">${port}</td>
    <td><span class="badge ${(r.category==='Security'||r.category==='Bandwidth')?r.status:r.status}">${icons[r.status]||''} ${r.status.toUpperCase()}</span></td>
    <td class="details-cell">${r.message}</td>
    <td class="lat">${lat}</td>`;
  document.getElementById('tbody').appendChild(tr);
}

// ── Summary ───────────────────────────────────────────────────
function showSummary(s) {
  document.getElementById('summaryBar').innerHTML = `
    <span class="pill total">${t('sum_total')}: ${s.total}</span>
    <span class="pill pass">✅ ${t('sum_pass')}: ${s.pass}</span>
    <span class="pill fail">❌ ${t('sum_fail')}: ${s.fail}</span>
    <span class="pill warn">⚠️ ${t('sum_warn')}: ${s.warn}</span>`;
  document.getElementById('summaryCard').style.display = '';
}

// ── Sort ──────────────────────────────────────────────────────
let _sd = {};
function sortTable(col) {
  const tbody = document.getElementById('tbody');
  const rows  = [...tbody.querySelectorAll('tr')];
  const dir   = _sd[col] = !_sd[col];
  rows.sort((a, b) => {
    const av = a.cells[col]?.textContent.trim() || '';
    const bv = b.cells[col]?.textContent.trim() || '';
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return dir ? an-bn : bn-an;
    return dir ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(r => tbody.appendChild(r));
}

// Init
applyLang();
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────
# HTTP SERVER
# ─────────────────────────────────────────────────────────────

_last_results: List[CheckResult] = []
_lock = threading.Lock()


class Handler(http.server.BaseHTTPRequestHandler):
    stop_event = threading.Event()

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        qs     = urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self._send(200, "text/html; charset=utf-8", HTML_UI.encode())

        elif path == "/api/check":
            modes         = qs.get("modes",        ["neat"])[0].split(",")
            custom_ntp    = qs.get("ntp",          ["time.neat.no"])[0].strip()
            run_mdns      = qs.get("mdns",         ["0"])[0] == "1"
            mdns_timeout  = float(qs.get("mdns_timeout", ["3"])[0])
            run_proxy     = qs.get("proxy",        ["0"])[0] == "1"
            run_bandwidth = qs.get("bw",           ["0"])[0] == "1"
            self._stream_check(modes, custom_ntp, run_proxy, run_mdns, mdns_timeout, run_bandwidth)

        elif path == "/api/export":
            fmt = qs.get("format", ["html"])[0]
            with _lock:
                results = list(_last_results)
            if fmt == "csv":
                data = build_csv_report(results).encode("utf-8")
                self._send(200, "text/csv; charset=utf-8", data,
                           extra={"Content-Disposition":
                                  'attachment; filename="neat_network_check.csv"'})
            else:
                data = build_html_report(results).encode("utf-8")
                self._send(200, "text/html; charset=utf-8", data)

        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        if self.path == "/api/stop":
            Handler.stop_event.set()
            self._send(200, "text/plain", b"ok")
        else:
            self._send(404, "text/plain", b"Not found")

    def _send(self, code, ctype, body, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _sse(self, event, data):
        msg = f"event: {event}\ndata: {data}\n\n"
        self.wfile.write(msg.encode())
        self.wfile.flush()

    def _stream_check(self, modes, custom_ntp, run_proxy, run_mdns, mdns_timeout,
                      run_bandwidth=False):
        Handler.stop_event.clear()

        # Count expected checks
        total  = sum(len(ALL_CHECKS.get(m, [])) for m in modes)
        total += 1                           # NTP always runs (time.neat.no or custom)
        total += 2 if run_proxy     else 0   # proxy + ssl_inspect
        total += 1 if run_mdns      else 0
        total += 2 if run_bandwidth else 0   # download + upload

        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection",    "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        self._sse("total", str(total))

        results: List[CheckResult] = []
        try:
            for r in run_checks(modes, custom_ntp, run_proxy, run_mdns, mdns_timeout,
                                run_bandwidth):
                if Handler.stop_event.is_set():
                    break
                results.append(r)
                self._sse("result", json.dumps({
                    "name":       r.name,
                    "category":   r.category,
                    "check_type": r.check_type,
                    "target":     r.target,
                    "port":       r.port,
                    "status":     r.status,
                    "message":    r.message,
                    "latency_ms": r.latency_ms,
                }))
        except (BrokenPipeError, ConnectionResetError):
            pass

        with _lock:
            _last_results.clear()
            _last_results.extend(results)

        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        warned = sum(1 for r in results if r.status == "warn")
        self._sse("done", json.dumps({
            "total": len(results), "pass": passed, "fail": failed, "warn": warned
        }))


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main():
    server = ThreadedServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"╔══════════════════════════════════════════════╗")
    print(f"║   Neat Network Connectivity Checker v1.1     ║")
    print(f"║   Opening browser → {url:<24}║")
    print(f"║   Press Ctrl+C to quit                       ║")
    print(f"╚══════════════════════════════════════════════╝")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down. Goodbye!")


if __name__ == "__main__":
    main()
