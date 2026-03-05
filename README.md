<p align="center">
  <img src="./assets/logo.svg" alt="Korean Public Data MCP" width="420">
</p>

<p align="center">
  <strong>한국 공공데이터 5개를 AI에게 연결합니다</strong><br>
  날씨 · 부동산 실거래가 · 대기질 · 경제통계 · 사업자조회
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/MCP-Protocol-blue" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Claude-supported-d4a574" alt="Claude">
  <img src="https://img.shields.io/badge/Claude_Code-supported-5B21B6" alt="Claude Code">
  <img src="https://img.shields.io/badge/Data-공공데이터포털-0064FF" alt="Data.go.kr">
  <img src="https://img.shields.io/badge/Price-Free-10b981" alt="Free">
  <br>
  <a href="https://render.com/deploy?repo=https://github.com/SongT-50/korean-public-data-mcp"><img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render"></a>
</p>

---

## 뭘 할 수 있나요?

AI에게 한국 공공데이터를 물어보세요. 자연어로 질문하면 실시간 데이터를 가져옵니다.

```
"서울 내일 날씨 어때?"
"강남구 2026년 2월 아파트 실거래가 알려줘"
"지금 미세먼지 어때?"
"최근 기준금리 추이 알려줘"
"사업자번호 1234567890 조회해줘"
```

## 제공 도구 (6개)

| 도구 | 설명 | 데이터 출처 |
|------|------|-------------|
| `check_business_registration` | 사업자등록번호 상태 조회 (최대 100건 일괄) | 국세청 |
| `get_real_estate_trades` | 아파트 실거래가 조회 (서울 25구 + 주요 도시) | 국토교통부 |
| `get_weather_forecast` | 단기 날씨 예보 (25개 도시, 72시간) | 기상청 |
| `get_air_quality` | 실시간 대기질 (PM10, PM2.5, 오존 등) | 에어코리아 |
| `get_economic_stats` | 경제통계 (금리, 물가, 환율, 코스피 등 8종) | 한국은행 ECOS |
| `list_supported_options` | 지원 지역/도시/지표 목록 확인 | — |

## 아키텍처

```
┌─────────────────┐     MCP Protocol     ┌──────────────────────┐
│  AI 에이전트     │ ◄──────────────────► │  Korean Public Data  │
│  (Claude, etc)  │                      │  MCP Server          │
└─────────────────┘                      └──────┬───────────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              │                 │                 │
                        ┌─────▼─────┐    ┌──────▼──────┐   ┌─────▼─────┐
                        │ 공공데이터 │    │  에어코리아  │   │ 한국은행  │
                        │  포털 API  │    │     API     │   │ ECOS API │
                        │ (4개 API) │    │             │   │          │
                        └───────────┘    └─────────────┘   └──────────┘

                        날씨 · 부동산      대기질 실시간      경제통계
                        사업자 조회                          금리 · 환율
```

## 빠른 시작

### 1. Claude Code (권장)

```bash
# 설치
git clone https://github.com/SongT-50/korean-public-data-mcp.git
cd korean-public-data-mcp
pip install -r requirements.txt

# API 키 설정
cp .env.example .env
# .env 파일에 API 키 입력 (아래 "API 키 발급" 참고)

# Claude Code에 등록
claude mcp add korean-public-data -- python server.py
```

### 2. Claude Desktop

`~/.claude/settings.json`에 추가:

```json
{
  "mcpServers": {
    "korean-public-data": {
      "command": "python",
      "args": ["/path/to/korean-public-data-mcp/server.py"],
      "env": {
        "DATA_GO_KR_API_KEY": "your_key",
        "ECOS_API_KEY": "your_ecos_key"
      }
    }
  }
}
```

### 3. 원격 접속 (설치 없이)

Render에 배포된 서버를 바로 사용할 수 있습니다.

```bash
# Claude Code
claude mcp add korean-public-data --transport sse https://korean-public-data-mcp.onrender.com/sse
```

```json
// Claude Desktop
{
  "mcpServers": {
    "korean-public-data": {
      "transport": "sse",
      "url": "https://korean-public-data-mcp.onrender.com/sse"
    }
  }
}
```

> 무료 Render 인스턴스는 비활성 시 슬립됩니다. 첫 요청에 30~60초 걸릴 수 있습니다.
> 원격 서버의 API 키는 서버에 설정되어 있습니다. 로컬 설치 시에만 본인의 키가 필요합니다.

### 4. MCPize (설치 없이)

[MCPize에서 바로 사용하기](https://mcpize.com/mcp/korean-public-data)

## API 키 발급 (무료)

| API | 발급처 | 소요 시간 |
|-----|--------|-----------|
| 공공데이터포털 (4개 API 공통) | [data.go.kr](https://www.data.go.kr) → 회원가입 → API 활용신청 | 즉시 승인 |
| 한국은행 ECOS (경제통계) | [ecos.bok.or.kr/api](https://ecos.bok.or.kr/api) → API 키 발급 | 즉시 발급 |

> 모든 API는 **무료**입니다. 일일 호출 제한이 있지만 개인 사용에는 충분합니다.

## 지원 범위

<details>
<summary><strong>날씨 예보 — 25개 도시</strong></summary>

서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종, 수원, 성남, 고양, 용인, 창원, 청주, 전주, 천안, 제주, 춘천, 원주, 강릉, 포항, 김해, 파주, 화성, 평택
</details>

<details>
<summary><strong>부동산 실거래가 — 서울 25구 + 주요 도시</strong></summary>

**서울**: 강남구, 강동구, 강북구, 강서구, 관악구, 광진구, 구로구, 금천구, 노원구, 도봉구, 동대문구, 동작구, 마포구, 서대문구, 서초구, 성동구, 성북구, 송파구, 양천구, 영등포구, 용산구, 은평구, 종로구, 중구, 중랑구

**경기**: 성남시분당구, 수원시영통구, 고양시일산서구, 용인시수지구, 화성시, 평택시

**광역시**: 부산해운대구, 대구수성구, 인천연수구, 대전유성구
</details>

<details>
<summary><strong>대기질 — 15개 지역</strong></summary>

서울(중구), 강남, 송파, 마포, 종로, 영등포, 부산, 대구, 인천, 광주, 대전, 울산, 수원, 성남, 제주
</details>

<details>
<summary><strong>경제통계 — 8개 지표</strong></summary>

기준금리, 소비자물가지수, 실업률, GDP성장률, 수출액, 수입액, 원달러환율, 코스피
</details>

## 사용 예시

### 날씨
```
"서울 내일 날씨 어때?"
"제주 72시간 예보 알려줘"
"부산 오늘 비 와?"
```

### 부동산
```
"강남구 2026년 2월 아파트 실거래가"
"송파구 최근 거래 보여줘"
"분당 아파트 가격 어때?"
```

### 대기질
```
"지금 서울 미세먼지 어때?"
"강남 초미세먼지 확인해줘"
"제주 대기질 좋아?"
```

### 경제
```
"최근 기준금리 추이"
"올해 코스피 흐름 보여줘"
"원달러 환율 변화"
```

### 사업자 조회
```
"사업자번호 1234567890 유효한지 확인해줘"
"이 사업자 폐업했는지 알려줘"
```

## 기술 스택

| 항목 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| MCP SDK | `mcp[cli]` (FastMCP) |
| HTTP | `httpx` (async) |
| XML 파싱 | `xmltodict` |
| 전송 | stdio / SSE / Streamable HTTP |
| 배포 | 로컬 / MCPize |

## 프로젝트 구조

```
korean-public-data-mcp/
├── server.py          # MCP 서버 (6개 도구)
├── requirements.txt   # Python 의존성
├── mcpize.yaml        # MCPize 배포 설정
├── .env.example       # API 키 템플릿
├── Dockerfile         # 컨테이너 배포
└── README.md          # 이 문서
```

## 라이선스

MIT License — 자유롭게 사용, 수정, 배포할 수 있습니다.

## 만든 사람

**삽질코딩** — AI 코딩으로 실제 제품을 만드는 기록

- YouTube: [삽질코딩](https://www.youtube.com/channel/UCSHxaZHNDOrp0h0Ux8_6CVQ)
- GitHub: [SongT-50](https://github.com/SongT-50)
