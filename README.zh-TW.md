# Neat 網路連線檢查工具

這是一款基於瀏覽器的網路診斷工具，用於驗證 **Neat 裝置**在 Zoom Rooms、Microsoft Teams Rooms、Google Meet 及 BYOD 模式下運行所需的防火牆和網路設定是否符合要求。

無需外部套件 — 僅使用 Python 標準函式庫即可運行。

**Language / 言語 / 언어 / 語言:**
[English](README.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

---

## 系統需求

- Python 3.8 或以上版本
- macOS 或 Windows
- 無需外部套件

---

## 使用方式

```bash
python3 neat_network_checker.py
```

腳本會在 **17432** 埠啟動本地端 Web 伺服器，並自動在瀏覽器開啟 `http://localhost:17432`。

> **Windows 使用者：** `python neat_network_checker.py`

---

## 檢查項目

### 🖥 Neat Common（所有模式共用）
無論使用哪種會議平台，所有 Neat 裝置都需要連線至以下核心基礎設施。

| 檢查項目 | 目標 | 協定 |
|---|---|---|
| 連線確認 (HTTP) | connectivitycheck.neat.no | TCP 80 |
| 連線確認 (HTTPS) | connectivitycheck.neat.no | TCP 443 |
| 身份驗證 | id.neat.no | HTTPS 443 |
| OTA 更新 | ota.neat.no | HTTPS 443 |
| Pulse 平台 | pulse.neat.no | HTTPS 443 |
| Pulse API | api.pulse.neat.no | HTTPS 443 |
| 支援入口 | support.neat.no | HTTPS 443 |
| NTP | time.neat.no | UDP 123 |

### 🔵 Zoom Rooms
依據 [KB0060548](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) 及 [KB0065712](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712)。

目標網域：`zoom.us`、`zoom.com`、`zoomgov.com`
TCP 埠：80、443、8801、8802
UDP 埠：3478、3479（至 zoom.us）、8801〜8803（至 Zoom IP 範圍）

### 🟣 Microsoft Teams Rooms
依據 [Microsoft 365 URL 與 IP 位址範圍](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams)。

目標網域：`teams.microsoft.com`、`skype.com`、`lync.com`、`microsoftonline.com`、`graph.microsoft.com`、`office365.com`、`microsoft.com`、`office.com`、`sfbassets.com`
UDP 埠：3478〜3481（至 worldaz.relay.teams.microsoft.com → 52.112.0.0/14）

### 🟢 Google Meet
依據[為 Meet 準備網路](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams)。

目標網域：`meet.google.com`、`accounts.google.com`、`apis.google.com`、`googleapis.com`、`gstatic.com`、`googleusercontent.com`
UDP 埠：3478、19302、19309（至 workspace.turns.goog / meet.turns.goog）

### 💻 BYOD
BYOD 模式僅需通過 Neat Common 檢查即可。

---

## 選用檢查

### 自訂 NTP 伺服器
除 `time.neat.no` 外，另行測試使用者指定之 NTP 伺服器的 UDP 123 連線。

### mDNS 檢查
向 `224.0.0.251:5353` 傳送 `_neat._tcp.local` 的 PTR 查詢，確認多播連通性及本地端 Neat 裝置探索功能。
> 需要管理員權限（macOS：`sudo`，Windows：以系統管理員身分執行）。

### Proxy 與 SSL 檢查
- 從系統設定及環境變數偵測 HTTP/HTTPS Proxy 設定。
- 檢查 `zoom.us` 的 TLS 憑證發行者，與已知公開 CA 比對，確認是否存在 SSL 解密（TLS MITM）。

### 頻寬測試
透過 `speed.cloudflare.com` 傳輸 20 MB 以測量吞吐量。

Full HD 視訊會議所需頻寬（參考值）：

| 平台 | 上傳 | 下載 |
|---|---|---|
| Zoom Rooms 1080p | ≥ 3.8 Mbps | ≥ 3.0 Mbps |
| Google Meet 1080p | ≥ 3.6 Mbps | ≥ 3.6 Mbps |
| Teams 直播活動 | ≥ 10 Mbps（建議值） | ≥ 10 Mbps |

> **注意：** 此測試使用 HTTP（TCP）。實際影音流量為 UDP（RTP/SRTP）。QoS 政策可能導致 TCP 與 UDP 頻寬有所差異。測試結果僅供 TCP 參考。

---

## 結果狀態

| 狀態 | 說明 |
|---|---|
| ✅ PASS | 連線確認 |
| ⚠️ WARN | 可連線但有注意事項（例：UDP 封包已送出，無 ICMP 封鎖） |
| ❌ FAIL | 連線失敗或遭封鎖 |

### 關於 UDP STUN / 媒體埠
UDP 媒體埠（如 Zoom 的 8801〜8810、Teams 的 3478〜3481）**不會回應 STUN 探測封包**，這是正常行為。顯示「No ICMP block detected → port is likely OPEN」的 `WARN` 結果，表示該埠可能處於開放狀態；顯示「ICMP Port Unreachable」的 `FAIL` 結果，則表示防火牆正在主動封鎖該埠。

---

## 匯出功能

檢查結果可匯出為以下格式：
- **HTML 報告** — 含狀態色碼的格式化表格
- **CSV** — 適用於試算表分析或工單記錄

---

## UI 語言

瀏覽器介面支援：English、日本語、한국어、繁體中文、简体中文

---

## 參考文件

| 平台 | 連結 |
|---|---|
| Neat | [網路與防火牆需求](https://support.neat.no/article/network-and-firewall-requirements-for-neat/) |
| Zoom | [防火牆規則](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712) · [網路需求](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) · [頻寬需求](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748) |
| Teams | [M365 URL 與 IP 位址範圍](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams) · [媒體位元率原則](https://learn.microsoft.com/en-us/microsoftteams/meeting-policies-audio-and-video#media-bit-rate-kbps) |
| Google Meet | [為 Meet 準備網路](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams) |

---

## 免責聲明

本工具依現狀提供，僅供網路診斷使用。結果反映測試當下的網路狀況。如需確認正式需求，請諮詢網路管理員並參閱各廠商官方文件。
