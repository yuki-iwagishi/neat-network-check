# Neat ネットワーク接続チェッカー

**Neat デバイス**が Zoom Rooms・Microsoft Teams Rooms・Google Meet・BYOD モードで正常に動作するために必要なファイアウォールおよびネットワーク要件を検証する、ブラウザベースのネットワーク診断ツールです。

外部パッケージは不要 — Python 標準ライブラリのみで動作します。

**Language / 言語 / 언어 / 語言:**
[English](README.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

---

## 動作環境

- Python 3.8 以上
- macOS または Windows
- 外部パッケージ不要

---

## 起動方法

```bash
python3 neat_network_checker.py
```

ポート **17432** でローカル Web サーバーが起動し、ブラウザで `http://localhost:17432` が自動的に開きます。

> **Windows の場合:** `python neat_network_checker.py`

---

## チェック内容

### 🖥 Neat Common（全モード共通）
プラットフォームに関わらず、すべての Neat デバイスに必要なコアインフラへの接続を確認します。

| チェック項目 | 対象 | プロトコル |
|---|---|---|
| 接続確認 (HTTP) | connectivitycheck.neat.no | TCP 80 |
| 接続確認 (HTTPS) | connectivitycheck.neat.no | TCP 443 |
| 認証 | id.neat.no | HTTPS 443 |
| OTA アップデート | ota.neat.no | HTTPS 443 |
| Pulse プラットフォーム | pulse.neat.no | HTTPS 443 |
| Pulse API | api.pulse.neat.no | HTTPS 443 |
| サポートポータル | support.neat.no | HTTPS 443 |
| NTP | time.neat.no | UDP 123 |

### 🔵 Zoom Rooms
[KB0060548](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) および [KB0065712](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712) に基づいています。

対象ドメイン: `zoom.us`、`zoom.com`、`zoomgov.com`
TCP ポート: 80、443、8801、8802
UDP ポート: 3478、3479（zoom.us 宛）、8801〜8803（Zoom IP レンジ宛）

### 🟣 Microsoft Teams Rooms
[Microsoft 365 URL & IP アドレス範囲](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams) に基づいています。

対象ドメイン: `teams.microsoft.com`、`skype.com`、`lync.com`、`microsoftonline.com`、`graph.microsoft.com`、`office365.com`、`microsoft.com`、`office.com`、`sfbassets.com`
UDP ポート: 3478〜3481（worldaz.relay.teams.microsoft.com → 52.112.0.0/14 宛）

### 🟢 Google Meet
[Meet のネットワーク準備](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams) に基づいています。

対象ドメイン: `meet.google.com`、`accounts.google.com`、`apis.google.com`、`googleapis.com`、`gstatic.com`、`googleusercontent.com`
UDP ポート: 3478、19302、19309（workspace.turns.goog / meet.turns.goog 宛）

### 💻 BYOD
BYOD モードには Neat Common チェックのみ必要です。

---

## オプションチェック

### カスタム NTP サーバ
`time.neat.no` に加えて、任意の NTP サーバへの UDP 123 接続をテストします。

### mDNS チェック
`224.0.0.251:5353` に `_neat._tcp.local` の PTR クエリを送信し、マルチキャスト疎通とローカルネットワーク上の Neat デバイス検出を確認します。
> 管理者権限が必要です（macOS: `sudo`、Windows: 管理者として実行）。

### プロキシ & SSL インスペクション
- システム設定および環境変数から HTTP/HTTPS プロキシ設定を検出します。
- `zoom.us` の TLS 証明書の発行者を既知のパブリック CA と照合し、SSL インスペクション（TLS MITM）の有無を確認します。

### 帯域幅テスト
`speed.cloudflare.com` 経由で 20 MB の送受信を行い、スループットを測定します。

Full HD 映像会議の必要帯域（参考値）:

| プラットフォーム | アップロード | ダウンロード |
|---|---|---|
| Zoom Rooms 1080p | ≥ 3.8 Mbps | ≥ 3.0 Mbps |
| Google Meet 1080p | ≥ 3.6 Mbps | ≥ 3.6 Mbps |
| Teams ライブイベント | ≥ 10 Mbps（推奨） | ≥ 10 Mbps |

> **注意:** このテストは HTTP (TCP) を使用します。実際の映像・音声通信は UDP (RTP/SRTP) です。QoS ポリシーによって TCP と UDP の帯域が異なる場合があります。結果は TCP での参考値としてご利用ください。

---

## 結果ステータス

| ステータス | 意味 |
|---|---|
| ✅ PASS | 接続確認済み |
| ⚠️ WARN | 到達可能だが注意が必要（例：UDP パケット送信済み、ICMP ブロックなし） |
| ❌ FAIL | 接続失敗またはブロックされている |

### UDP STUN / メディアポートについて
UDP メディアポート（Zoom の 8801〜8810、Teams の 3478〜3481 など）は **STUN プローブに応答しません** — これは正常な動作です。「No ICMP block detected → port is likely OPEN」という `WARN` 結果は、そのポートへの通信が通過している可能性が高いことを意味します。「ICMP Port Unreachable」という `FAIL` 結果は、ファイアウォールがそのポートを積極的にブロックしていることを意味します。

---

## エクスポート

チェック結果は以下の形式でエクスポートできます:
- **HTML レポート** — ステータス色分け付きのフォーマット済みテーブル
- **CSV** — スプレッドシート分析やチケット起票用

---

## UI 言語

ブラウザ UI は以下の言語に対応しています: English、日本語、한국어、繁體中文、简体中文

---

## 参照ドキュメント

| プラットフォーム | リンク |
|---|---|
| Neat | [ネットワーク & ファイアウォール要件](https://support.neat.no/article/network-and-firewall-requirements-for-neat/) |
| Zoom | [ファイアウォールルール](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712) · [ネットワーク要件](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) · [帯域幅要件](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748) |
| Teams | [M365 URL & IP アドレス範囲](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams) · [メディアビットレートポリシー](https://learn.microsoft.com/en-us/microsoftteams/meeting-policies-audio-and-video#media-bit-rate-kbps) |
| Google Meet | [ネットワーク準備](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams) |

---

## 免責事項

本ツールはネットワーク診断を目的として現状のまま提供されます。結果はテスト実施時点のネットワーク状況を反映したものです。正確な要件については、ネットワーク管理者および各ベンダーの公式ドキュメントをご参照ください。
