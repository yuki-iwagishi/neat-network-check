# Neat 网络连接检查工具

这是一款基于浏览器的网络诊断工具，用于验证 **Neat 设备**在 Zoom Rooms、Microsoft Teams Rooms、Google Meet 及 BYOD 模式下运行所需的防火墙和网络配置是否符合要求。

无需外部包 — 仅使用 Python 标准库即可运行。

**Language / 言語 / 언어 / 語言:**
[English](README.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

---

## 系统要求

- Python 3.8 或更高版本
- macOS 或 Windows
- 无需外部包

---

## 使用方法

```bash
python3 neat_network_checker.py
```

脚本将在 **17432** 端口启动本地 Web 服务器，并自动在浏览器中打开 `http://localhost:17432`。

> **Windows 用户：** `python neat_network_checker.py`

---

## 检查项目

### 🖥 Neat Common（所有模式共用）
无论使用哪种会议平台，所有 Neat 设备均需连接以下核心基础设施。

| 检查项目 | 目标 | 协议 |
|---|---|---|
| 连接确认 (HTTP) | connectivitycheck.neat.no | TCP 80 |
| 连接确认 (HTTPS) | connectivitycheck.neat.no | TCP 443 |
| 身份验证 | id.neat.no | HTTPS 443 |
| OTA 更新 | ota.neat.no | HTTPS 443 |
| Pulse 平台 | pulse.neat.no | HTTPS 443 |
| Pulse API | api.pulse.neat.no | HTTPS 443 |
| 支持门户 | support.neat.no | HTTPS 443 |
| NTP | time.neat.no | UDP 123 |

### 🔵 Zoom Rooms
依据 [KB0060548](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) 及 [KB0065712](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712)。

目标域名：`zoom.us`、`zoom.com`、`zoomgov.com`
TCP 端口：80、443、8801、8802
UDP 端口：3478、3479（至 zoom.us）、8801〜8803（至 Zoom IP 段）

### 🟣 Microsoft Teams Rooms
依据 [Microsoft 365 URL 与 IP 地址范围](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams)。

目标域名：`teams.microsoft.com`、`skype.com`、`lync.com`、`microsoftonline.com`、`graph.microsoft.com`、`office365.com`、`microsoft.com`、`office.com`、`sfbassets.com`
UDP 端口：3478〜3481（至 worldaz.relay.teams.microsoft.com → 52.112.0.0/14）

### 🟢 Google Meet
依据[为 Meet 准备网络](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams)。

目标域名：`meet.google.com`、`accounts.google.com`、`apis.google.com`、`googleapis.com`、`gstatic.com`、`googleusercontent.com`
UDP 端口：3478、19302、19309（至 workspace.turns.goog / meet.turns.goog）

### 💻 BYOD
BYOD 模式仅需通过 Neat Common 检查即可。

---

## 可选检查

### 自定义 NTP 服务器
除 `time.neat.no` 外，另行测试用户指定的 NTP 服务器的 UDP 123 连接。

### mDNS 检查
向 `224.0.0.251:5353` 发送 `_neat._tcp.local` 的 PTR 查询，确认组播连通性及本地 Neat 设备发现功能。
> 需要管理员权限（macOS：`sudo`，Windows：以管理员身份运行）。

### 代理 & SSL 检查
- 从系统设置及环境变量检测 HTTP/HTTPS 代理配置。
- 检查 `zoom.us` 的 TLS 证书颁发机构，与已知公开 CA 进行比对，确认是否存在 SSL 解密（TLS MITM）。

### 带宽测试
通过 `speed.cloudflare.com` 传输 20 MB 以测量吞吐量。

Full HD 视频会议所需带宽（参考值）：

| 平台 | 上传 | 下载 |
|---|---|---|
| Zoom Rooms 1080p | ≥ 3.8 Mbps | ≥ 3.0 Mbps |
| Google Meet 1080p | ≥ 3.6 Mbps | ≥ 3.6 Mbps |
| Teams 直播活动 | ≥ 10 Mbps（建议值） | ≥ 10 Mbps |

> **注意：** 此测试使用 HTTP（TCP）。实际音视频流量为 UDP（RTP/SRTP）。QoS 策略可能导致 TCP 与 UDP 带宽存在差异。测试结果仅供 TCP 参考。

---

## 结果状态

| 状态 | 含义 |
|---|---|
| ✅ PASS | 连接已确认 |
| ⚠️ WARN | 可连接但有注意事项（例：UDP 数据包已发送，无 ICMP 封锁） |
| ❌ FAIL | 连接失败或被封锁 |

### 关于 UDP STUN / 媒体端口
UDP 媒体端口（如 Zoom 的 8801〜8810、Teams 的 3478〜3481）**不会响应 STUN 探测包**，这是正常行为。显示"No ICMP block detected → port is likely OPEN"的 `WARN` 结果表示该端口可能处于开放状态；显示"ICMP Port Unreachable"的 `FAIL` 结果则表示防火墙正在主动封锁该端口。

---

## 导出功能

检查结果可导出为以下格式：
- **HTML 报告** — 含状态色码的格式化表格
- **CSV** — 适用于表格分析或工单记录

---

## UI 语言

浏览器界面支持：English、日本語、한국어、繁體中文、简体中文

---

## 参考文档

| 平台 | 链接 |
|---|---|
| Neat | [网络与防火墙要求](https://support.neat.no/article/network-and-firewall-requirements-for-neat/) |
| Zoom | [防火墙规则](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712) · [网络要求](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) · [带宽要求](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748) |
| Teams | [M365 URL 与 IP 地址范围](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams) · [媒体比特率策略](https://learn.microsoft.com/en-us/microsoftteams/meeting-policies-audio-and-video#media-bit-rate-kbps) |
| Google Meet | [为 Meet 准备网络](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams) |

---

## 免责声明

本工具按现状提供，仅供网络诊断使用。结果反映测试当时的网络状况。如需确认正式要求，请咨询网络管理员并参阅各厂商官方文档。
