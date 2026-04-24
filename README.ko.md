# Neat 네트워크 연결 검사기

**Neat 디바이스**가 Zoom Rooms, Microsoft Teams Rooms, Google Meet, BYOD 모드에서 정상적으로 동작하기 위해 필요한 방화벽 및 네트워크 요건을 검증하는 브라우저 기반 네트워크 진단 도구입니다.

외부 패키지 불필요 — Python 표준 라이브러리만으로 동작합니다.

**Language / 言語 / 언어 / 語言:**
[English](README.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

---

## 동작 환경

- Python 3.8 이상
- macOS 또는 Windows
- 외부 패키지 불필요

---

## 실행 방법

```bash
python3 neat_network_checker.py
```

포트 **17432**에서 로컬 웹 서버가 시작되고, 브라우저에서 `http://localhost:17432`가 자동으로 열립니다.

> **Windows의 경우:** `python neat_network_checker.py`

---

## 검사 항목

### 🖥 Neat Common (모든 모드 공통)
플랫폼에 관계없이 모든 Neat 디바이스에 필요한 핵심 인프라 연결을 확인합니다.

| 검사 항목 | 대상 | 프로토콜 |
|---|---|---|
| 연결 확인 (HTTP) | connectivitycheck.neat.no | TCP 80 |
| 연결 확인 (HTTPS) | connectivitycheck.neat.no | TCP 443 |
| 인증 | id.neat.no | HTTPS 443 |
| OTA 업데이트 | ota.neat.no | HTTPS 443 |
| Pulse 플랫폼 | pulse.neat.no | HTTPS 443 |
| Pulse API | api.pulse.neat.no | HTTPS 443 |
| NTP | time.neat.no | UDP 123 |

### 🔵 Zoom Rooms
[KB0060548](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) 및 [KB0065712](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712) 기반.

대상 도메인: `zoom.us`, `zoom.com`, `zoomgov.com`
TCP 포트: 80, 443, 8801, 8802
UDP 포트: 3478, 3479 (zoom.us), 8801~8803 (Zoom IP 범위)

### 🟣 Microsoft Teams Rooms
[Microsoft 365 URL & IP 주소 범위](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams) 기반.

대상 도메인: `teams.microsoft.com`, `skype.com`, `lync.com`, `microsoftonline.com`, `graph.microsoft.com`, `office365.com`, `microsoft.com`, `office.com`
UDP 포트: 3478~3481 (worldaz.relay.teams.microsoft.com → 52.112.0.0/14)

### 🟢 Google Meet
[Meet 네트워크 준비](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams) 기반.

대상 도메인: `meet.google.com`, `accounts.google.com`, `apis.google.com`, `googleapis.com`, `gstatic.com`, `googleusercontent.com`
UDP 포트: 3478, 19302, 19309 (workspace.turns.goog / meet.turns.goog)

### 💻 BYOD
BYOD 모드는 Neat Common 검사만으로 충분합니다.

---

## 선택 검사

### 사용자 지정 NTP 서버
`time.neat.no` 외에 사용자가 지정한 NTP 서버로의 UDP 123 연결을 테스트합니다.

### mDNS 검사
`224.0.0.251:5353`으로 `_neat._tcp.local` PTR 쿼리를 전송하여 멀티캐스트 연결 및 로컬 네트워크 상의 Neat 디바이스 검색을 확인합니다.
> 관리자 권한 필요 (macOS: `sudo`, Windows: 관리자 권한으로 실행).

### 프록시 & SSL 검사
- 시스템 설정 및 환경 변수에서 HTTP/HTTPS 프록시 설정을 감지합니다.
- `zoom.us`의 TLS 인증서 발급자를 알려진 공개 CA와 대조하여 SSL 검사(TLS MITM) 여부를 확인합니다.

### 대역폭 테스트
`speed.cloudflare.com`을 통해 20 MB를 송수신하여 처리량을 측정합니다.

Full HD 화상회의 필요 대역폭 (참고값):

| 플랫폼 | 업로드 | 다운로드 |
|---|---|---|
| Zoom Rooms 1080p | ≥ 3.8 Mbps | ≥ 3.0 Mbps |
| Google Meet 1080p | ≥ 3.6 Mbps | ≥ 3.6 Mbps |
| Teams 라이브 이벤트 | ≥ 10 Mbps (권장) | ≥ 10 Mbps |

> **주의:** 이 테스트는 HTTP(TCP)를 사용합니다. 실제 영상·음성 트래픽은 UDP(RTP/SRTP)입니다. QoS 정책에 따라 TCP와 UDP 대역폭이 다를 수 있습니다. 결과는 TCP 참고값으로 활용하시기 바랍니다.

---

## 결과 상태

| 상태 | 의미 |
|---|---|
| ✅ PASS | 연결 확인됨 |
| ⚠️ WARN | 도달 가능하나 주의 필요 (예: UDP 패킷 전송됨, ICMP 차단 없음) |
| ❌ FAIL | 연결 실패 또는 차단됨 |

### UDP STUN / 미디어 포트에 대하여
UDP 미디어 포트(Zoom의 8801~8810, Teams의 3478~3481 등)는 **STUN 프로브에 응답하지 않습니다** — 이는 정상적인 동작입니다. "No ICMP block detected → port is likely OPEN"이라는 `WARN` 결과는 해당 포트가 열려 있을 가능성이 높음을 의미합니다. "ICMP Port Unreachable"이라는 `FAIL` 결과는 방화벽이 해당 포트를 명시적으로 차단하고 있음을 의미합니다.

---

## 내보내기

검사 결과는 다음 형식으로 내보낼 수 있습니다:
- **HTML 보고서** — 상태별 색상 구분이 적용된 포맷 테이블
- **CSV** — 스프레드시트 분석 또는 티켓 등록용

---

## UI 언어

브라우저 UI는 English, 日本語, 한국어, 繁體中文, 简体中文를 지원합니다.

---

## 참조 문서

| 플랫폼 | 링크 |
|---|---|
| Neat | [네트워크 & 방화벽 요건](https://support.neat.no/article/network-and-firewall-requirements-for-neat/) |
| Zoom | [방화벽 규칙](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0065712) · [네트워크 요건](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060548) · [대역폭 요건](https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0060748) |
| Teams | [M365 URL & IP 주소 범위](https://learn.microsoft.com/en-us/microsoft-365/enterprise/urls-and-ip-address-ranges?view=o365-worldwide#microsoft-teams) · [미디어 비트레이트 정책](https://learn.microsoft.com/en-us/microsoftteams/meeting-policies-audio-and-video#media-bit-rate-kbps) |
| Google Meet | [네트워크 준비](https://knowledge.workspace.google.com/admin/meet/prepare-your-network-for-meet-meetings-and-live-streams) |

---

## 면책 조항

본 도구는 네트워크 진단 목적으로 현 상태 그대로 제공됩니다. 결과는 테스트 시점의 네트워크 상태를 반영합니다. 정확한 요건은 네트워크 관리자 및 각 벤더의 공식 문서를 참조하시기 바랍니다.
