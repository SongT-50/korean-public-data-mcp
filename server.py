"""
Korean Public Data MCP Server
한국 공공데이터 MCP 서버 — 5개 핵심 공공 API를 AI 에이전트에 연결

APIs:
1. 국세청 사업자등록 상태조회
2. 국토교통부 부동산 실거래가
3. 기상청 단기예보
4. 에어코리아 대기질 실시간
5. 한국은행 ECOS 경제통계
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx
import xmltodict
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
ECOS_KEY = os.getenv("ECOS_API_KEY", "")

mcp = FastMCP("Korean Public Data")

# ─── 캐싱 레이어 (Daiso MCP 참고) ───

# TTL 설정 (초)
CACHE_TTL = {
    "weather": 600,        # 날씨: 10분
    "air_quality": 180,    # 대기질: 3분
    "real_estate": 86400,  # 부동산: 24시간
    "economic": 3600,      # 경제통계: 1시간
    "business": 86400,     # 사업자조회: 24시간
}

_cache: dict[str, tuple[float, str]] = {}


def _cache_get(key: str) -> str | None:
    if key in _cache:
        expires, value = _cache[key]
        if time.time() < expires:
            return value
        del _cache[key]
    return None


def _cache_set(key: str, value: str, ttl_key: str):
    ttl = CACHE_TTL.get(ttl_key, 600)
    _cache[key] = (time.time() + ttl, value)


# ─── HTTP 클라이언트 ───

async def _get(url: str, params: dict | None = None, timeout: float = 30.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.get(url, params=params)


async def _post_json(url: str, payload: dict, timeout: float = 30.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=payload)


def _parse_xml(text: str) -> dict:
    return xmltodict.parse(text)


def _check_api_key(key: str, name: str) -> str | None:
    if not key:
        return f"{name} API 키가 설정되지 않았습니다. .env 파일에 키를 추가해주세요."
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 국세청 사업자등록 상태조회
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
async def check_business_registration(
    business_numbers: list[str],
) -> str:
    """사업자등록번호로 사업 상태를 조회합니다.

    Args:
        business_numbers: 사업자등록번호 리스트 (예: ["1234567890", "0987654321"]). 하이픈 없이 10자리 숫자. 최대 100개.

    Returns:
        각 사업자의 등록 상태 (계속사업자, 휴업자, 폐업자 등)
    """
    err = _check_api_key(DATA_GO_KR_KEY, "공공데이터포털")
    if err:
        return err

    if len(business_numbers) > 100:
        return "최대 100개까지 조회 가능합니다."

    # 하이픈 제거
    cleaned = [b.replace("-", "") for b in business_numbers]

    url = f"https://api.odcloud.kr/api/nts-businessman/v1/status?serviceKey={DATA_GO_KR_KEY}"
    payload = {"b_no": cleaned}

    try:
        resp = await _post_json(url, payload)
        data = resp.json()
    except Exception as e:
        return f"API 호출 실패: {e}"

    if resp.status_code != 200:
        return f"API 오류 (HTTP {resp.status_code}): {resp.text[:500]}"

    results = []
    for item in data.get("data", []):
        b_no = item.get("b_no", "")
        status = item.get("b_stt", "알 수 없음")
        status_cd = item.get("b_stt_cd", "")
        tax_type = item.get("tax_type", "")
        end_dt = item.get("end_dt", "")

        formatted = f"- {b_no}: {status}"
        if tax_type:
            formatted += f" ({tax_type})"
        if end_dt:
            formatted += f" [폐업일: {end_dt}]"
        results.append(formatted)

    header = f"## 사업자등록 상태 조회 결과 ({len(results)}건)\n"
    return header + "\n".join(results)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 국토교통부 부동산 실거래가
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 주요 법정동코드 (LAWD_CD 앞 5자리)
DISTRICT_CODES = {
    "강남구": "11680", "서초구": "11650", "송파구": "11710",
    "마포구": "11440", "용산구": "11170", "성동구": "11200",
    "영등포구": "11560", "강서구": "11500", "노원구": "11350",
    "관악구": "11620", "종로구": "11110", "중구": "11140",
    "동대문구": "11230", "성북구": "11290", "강동구": "11740",
    "양천구": "11470", "구로구": "11530", "금천구": "11545",
    "동작구": "11590", "광진구": "11215", "중랑구": "11260",
    "서대문구": "11410", "도봉구": "11320", "강북구": "11305",
    "은평구": "11380",
    # 경기
    "성남시분당구": "41135", "수원시영통구": "41117",
    "고양시일산서구": "41287", "용인시수지구": "41465",
    "화성시": "41590", "평택시": "41220",
    # 광역시
    "부산해운대구": "26350", "대구수성구": "27260",
    "인천연수구": "28185", "대전유성구": "30200",
}


@mcp.tool()
async def get_real_estate_trades(
    district: str,
    year_month: str,
) -> str:
    """아파트 실거래가를 조회합니다.

    Args:
        district: 지역구 이름 (예: "강남구", "서초구", "성남시분당구"). 서울 25개구 + 주요 경기/광역시 지원.
        year_month: 조회할 연월 (예: "202602"). YYYYMM 형식.

    Returns:
        해당 지역/기간의 아파트 실거래 내역 (단지명, 면적, 가격, 층, 거래일)
    """
    err = _check_api_key(DATA_GO_KR_KEY, "공공데이터포털")
    if err:
        return err

    lawd_cd = DISTRICT_CODES.get(district)
    if not lawd_cd:
        available = ", ".join(sorted(DISTRICT_CODES.keys()))
        return f"'{district}'는 지원하지 않는 지역입니다.\n지원 지역: {available}"

    cache_key = f"realestate:{district}:{year_month}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    url = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
    params = {
        "serviceKey": DATA_GO_KR_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": year_month,
        "pageNo": "1",
        "numOfRows": "50",
    }

    try:
        resp = await _get(url, params=params)
        data = _parse_xml(resp.text)
    except Exception as e:
        return f"API 호출 실패: {e}"

    body = data.get("response", {}).get("body", {})
    items = body.get("items", {})

    if not items or items == "":
        return f"{district} {year_month} 기간의 거래 데이터가 없습니다."

    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    total = body.get("totalCount", len(item_list))

    results = [f"## {district} 아파트 실거래가 ({year_month}, 총 {total}건 중 {len(item_list)}건)\n"]

    for item in item_list:
        apt_name = item.get("aptNm", "?")
        area = item.get("excluUseAr", "?")
        price = item.get("dealAmount", "?")
        if isinstance(price, str):
            price = price.strip()
        floor = item.get("floor", "?")
        deal_day = item.get("dealDay", "?")
        deal_month = item.get("dealMonth", "?")
        build_year = item.get("buildYear", "?")

        results.append(
            f"- **{apt_name}** | {area}㎡ | **{price}만원** | {floor}층 | "
            f"{year_month[:4]}.{deal_month}.{str(deal_day).strip()} | 건축{build_year}"
        )

    result = "\n".join(results)
    _cache_set(cache_key, result, "real_estate")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 기상청 단기예보
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 주요 도시의 격자 좌표 (nx, ny)
CITY_GRID = {
    "서울": (60, 127), "부산": (98, 76), "대구": (89, 90),
    "인천": (55, 124), "광주": (58, 74), "대전": (67, 100),
    "울산": (102, 84), "세종": (66, 103), "수원": (60, 121),
    "성남": (63, 124), "고양": (57, 128), "용인": (64, 119),
    "창원": (89, 77), "청주": (69, 107), "전주": (63, 89),
    "천안": (63, 110), "제주": (52, 38), "춘천": (73, 134),
    "원주": (76, 122), "강릉": (92, 131), "포항": (102, 94),
    "김해": (95, 77), "파주": (56, 131), "화성": (57, 119),
    "평택": (62, 114),
}

WEATHER_CATEGORIES = {
    "TMP": "기온(℃)", "TMN": "최저기온(℃)", "TMX": "최고기온(℃)",
    "POP": "강수확률(%)", "PTY": "강수형태", "PCP": "강수량(mm)",
    "REH": "습도(%)", "SNO": "적설량(cm)", "SKY": "하늘상태",
    "WSD": "풍속(m/s)", "VEC": "풍향(°)",
}

PTY_MAP = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}
SKY_MAP = {"1": "맑음", "3": "구름많음", "4": "흐림"}


@mcp.tool()
async def get_weather_forecast(
    city: str,
    hours_ahead: int = 24,
) -> str:
    """도시별 단기 날씨 예보를 조회합니다.

    Args:
        city: 도시 이름 (예: "서울", "부산", "제주", "수원"). 25개 주요 도시 지원.
        hours_ahead: 앞으로 몇 시간 예보를 볼지 (기본 24시간, 최대 72시간)

    Returns:
        시간대별 기온, 강수확률, 하늘상태 등 날씨 정보
    """
    err = _check_api_key(DATA_GO_KR_KEY, "공공데이터포털")
    if err:
        return err

    grid = CITY_GRID.get(city)
    if not grid:
        available = ", ".join(sorted(CITY_GRID.keys()))
        return f"'{city}'는 지원하지 않는 도시입니다.\n지원 도시: {available}"

    # 캐시 확인
    cache_key = f"weather:{city}:{hours_ahead}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    nx, ny = grid

    # 발표 시각 계산 — 최신부터 시도, 403이면 이전 시간으로 폴백
    now = datetime.now()
    base_times = [2, 5, 8, 11, 14, 17, 20, 23]
    candidates = []
    for h in reversed(base_times):
        if h <= now.hour:
            candidates.append((now.strftime("%Y%m%d"), f"{h:02d}00"))
    # 전날 마지막 발표시각도 추가
    yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")
    candidates.append((yesterday, "2300"))
    candidates.append((yesterday, "2000"))

    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    data = None
    used_base = None

    for base_date, base_time in candidates:
        params = {
            "serviceKey": DATA_GO_KR_KEY,
            "pageNo": "1",
            "numOfRows": "1000",
            "dataType": "XML",
            "base_date": base_date,
            "base_time": base_time,
            "nx": str(nx),
            "ny": str(ny),
        }
        try:
            resp = await _get(url, params=params)
            if resp.status_code == 200 and "NORMAL_SERVICE" in resp.text:
                data = _parse_xml(resp.text)
                used_base = (base_date, base_time)
                break
        except Exception:
            continue

    if data is None:
        return f"{city} 날씨 데이터를 가져올 수 없습니다. 잠시 후 다시 시도해주세요."

    base_date, base_time = used_base

    header = data.get("response", {}).get("header", {})
    if header.get("resultCode") != "00":
        return f"API 오류: {header.get('resultMsg', '알 수 없는 오류')}"

    items_raw = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
    if isinstance(items_raw, dict):
        items_raw = [items_raw]
    items = items_raw
    if not items:
        return f"{city}의 예보 데이터가 없습니다."

    # 시간대별로 그룹핑 (XML 파싱 결과는 모두 문자열)
    forecasts: dict[str, dict] = {}
    for item in items:
        fc_date = str(item.get("fcstDate", ""))
        fc_time = str(item.get("fcstTime", ""))
        key = f"{fc_date} {fc_time}"
        cat = str(item.get("category", ""))
        val = str(item.get("fcstValue", ""))

        if key not in forecasts:
            forecasts[key] = {}
        forecasts[key][cat] = val

    # 시간순 정렬 후 hours_ahead만큼만
    sorted_keys = sorted(forecasts.keys())[:max(1, hours_ahead // 3)]

    results = [f"## {city} 날씨 예보 (발표: {base_date} {base_time})\n"]

    for key in sorted_keys:
        fc = forecasts[key]
        date_part, time_part = key.split(" ")
        hour = time_part[:2]

        temp = fc.get("TMP", "-")
        pop = fc.get("POP", "-")
        pty_code = fc.get("PTY", "0")
        sky_code = fc.get("SKY", "-")
        reh = fc.get("REH", "-")
        wsd = fc.get("WSD", "-")
        pcp = fc.get("PCP", "강수없음")

        sky = SKY_MAP.get(sky_code, sky_code)
        pty = PTY_MAP.get(pty_code, pty_code)
        weather = pty if pty_code != "0" else sky

        results.append(
            f"- **{date_part[4:6]}/{date_part[6:]}** {hour}시 | "
            f"{weather} | {temp}℃ | 강수 {pop}% | 습도 {reh}% | 풍속 {wsd}m/s"
            + (f" | {pcp}" if pcp != "강수없음" else "")
        )

    result = "\n".join(results)
    _cache_set(cache_key, result, "weather")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 에어코리아 대기질 실시간
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 주요 측정소 매핑
STATION_MAP = {
    "서울": "중구", "강남": "강남구", "송파": "송파구",
    "마포": "마포구", "종로": "종로구", "영등포": "영등포구",
    "부산": "부산 연산동", "대구": "대구 달서구", "인천": "인천 부평구",
    "광주": "광주 서석동", "대전": "대전 문화동", "울산": "울산 삼산동",
    "수원": "수원 인계동", "성남": "성남 수정구",
    "제주": "제주 이도동",
}

AQI_GRADE = {
    "1": "좋음", "2": "보통", "3": "나쁨", "4": "매우나쁨",
}


@mcp.tool()
async def get_air_quality(
    location: str,
) -> str:
    """실시간 대기질(미세먼지, 초미세먼지, 오존 등)을 조회합니다.

    Args:
        location: 지역명 (예: "서울", "강남", "부산", "제주"). 15개 주요 지역 지원.

    Returns:
        PM10, PM2.5, 오존, 이산화질소, 일산화탄소, 아황산가스 수치와 등급
    """
    err = _check_api_key(DATA_GO_KR_KEY, "공공데이터포털")
    if err:
        return err

    station = STATION_MAP.get(location)
    if not station:
        available = ", ".join(sorted(STATION_MAP.keys()))
        return f"'{location}'는 지원하지 않는 지역입니다.\n지원 지역: {available}"

    # 캐시 확인
    cache_key = f"air:{location}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    url = "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty"
    params = {
        "serviceKey": DATA_GO_KR_KEY,
        "returnType": "xml",
        "numOfRows": "1",
        "pageNo": "1",
        "stationName": station,
        "dataTerm": "DAILY",
        "ver": "1.5",
    }

    try:
        resp = await _get(url, params=params)
        if resp.status_code == 403:
            return f"대기질 API 접근이 거부되었습니다. data.go.kr에서 '에어코리아 대기오염정보' API 활용신청이 필요합니다."
        data = _parse_xml(resp.text)
    except Exception as e:
        return f"API 호출 실패: {e}"

    items_section = data.get("response", {}).get("body", {}).get("items", {})
    if not items_section:
        return f"{location}({station}) 대기질 데이터가 없습니다."

    item_list = items_section.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]
    if not item_list:
        return f"{location}({station}) 대기질 데이터가 없습니다."

    item = item_list[0]
    dt = item.get("dataTime", "?")
    pm10 = item.get("pm10Value", "-")
    pm25 = item.get("pm25Value", "-")
    pm10_grade = AQI_GRADE.get(item.get("pm10Grade", ""), "?")
    pm25_grade = AQI_GRADE.get(item.get("pm25Grade", ""), "?")
    o3 = item.get("o3Value", "-")
    o3_grade = AQI_GRADE.get(item.get("o3Grade", ""), "?")
    no2 = item.get("no2Value", "-")
    co = item.get("coValue", "-")
    so2 = item.get("so2Value", "-")
    khai_grade = AQI_GRADE.get(item.get("khaiGrade", ""), "?")

    result = f"""## {location} 대기질 ({dt})
측정소: {station}

| 항목 | 수치 | 등급 |
|------|------|------|
| 통합대기질(CAI) | {item.get('khaiValue', '-')} | {khai_grade} |
| 미세먼지(PM10) | {pm10} ㎍/㎥ | {pm10_grade} |
| 초미세먼지(PM2.5) | {pm25} ㎍/㎥ | {pm25_grade} |
| 오존(O₃) | {o3} ppm | {o3_grade} |
| 이산화질소(NO₂) | {no2} ppm | - |
| 일산화탄소(CO) | {co} ppm | - |
| 아황산가스(SO₂) | {so2} ppm | - |"""
    _cache_set(cache_key, result, "air_quality")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. 한국은행 ECOS 경제통계
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ECOS_STATS = {
    "기준금리": {"code": "722Y001", "item": "0101000", "cycle": "M"},
    "소비자물가지수": {"code": "901Y009", "item": "0", "cycle": "M"},
    "실업률": {"code": "901Y027", "item": "3130000", "cycle": "M"},
    "GDP성장률": {"code": "200Y002", "item": "10111", "cycle": "Q"},
    "수출액": {"code": "403Y003", "item": "1000", "cycle": "M"},
    "수입액": {"code": "403Y003", "item": "2000", "cycle": "M"},
    "원달러환율": {"code": "731Y001", "item": "0000001", "cycle": "M"},
    "코스피": {"code": "802Y001", "item": "0001000", "cycle": "M"},
}


@mcp.tool()
async def get_economic_stats(
    indicator: str,
    period: str = "latest",
) -> str:
    """한국은행 경제통계를 조회합니다.

    Args:
        indicator: 경제지표명. 지원 항목: 기준금리, 소비자물가지수, 실업률, GDP성장률, 수출액, 수입액, 원달러환율, 코스피
        period: 조회기간. "latest"(최근 12개월), "2025"(특정연도), "202501-202602"(기간지정)

    Returns:
        해당 경제지표의 시계열 데이터
    """
    err = _check_api_key(ECOS_KEY, "한국은행 ECOS")
    if err:
        return err

    stat = ECOS_STATS.get(indicator)
    if not stat:
        available = ", ".join(ECOS_STATS.keys())
        return f"'{indicator}'는 지원하지 않는 지표입니다.\n지원 지표: {available}"

    cache_key = f"econ:{indicator}:{period}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    stat_code = stat["code"]
    item_code = stat["item"]
    cycle = stat["cycle"]

    # 기간 파싱
    if period == "latest":
        if cycle == "Q":
            end = datetime.now()
            start = end - timedelta(days=365 * 3)
            start_str = start.strftime("%Y") + "Q1"
            end_str = end.strftime("%Y") + "Q4"
        else:
            end = datetime.now()
            start = end - timedelta(days=365)
            start_str = start.strftime("%Y%m")
            end_str = end.strftime("%Y%m")
    elif "-" in period:
        start_str, end_str = period.split("-")
    else:
        start_str = period + ("Q1" if cycle == "Q" else "01")
        end_str = period + ("Q4" if cycle == "Q" else "12")

    url = (
        f"https://ecos.bok.or.kr/api/StatisticSearch"
        f"/{ECOS_KEY}/json/kr/1/100"
        f"/{stat_code}/{cycle}/{start_str}/{end_str}/{item_code}"
    )

    try:
        resp = await _get(url)
        data = resp.json()
    except Exception as e:
        return f"API 호출 실패: {e}"

    stat_search = data.get("StatisticSearch")
    if not stat_search:
        error_msg = data.get("RESULT", {}).get("MESSAGE", "알 수 없는 오류")
        return f"ECOS API 오류: {error_msg}"

    rows = stat_search.get("row", [])
    if not rows:
        return f"{indicator} 데이터가 없습니다 ({start_str}~{end_str})"

    unit = rows[0].get("UNIT_NAME", "")
    stat_name = rows[0].get("STAT_NAME", indicator)

    results = [f"## {indicator} ({stat_name})\n단위: {unit}\n"]

    for row in rows:
        t = row.get("TIME", "?")
        value = row.get("DATA_VALUE", "-")
        results.append(f"- {t}: **{value}**")

    result = "\n".join(results)
    _cache_set(cache_key, result, "economic")
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 보너스: 지원 목록 조회 도구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
async def list_supported_options() -> str:
    """이 MCP 서버에서 지원하는 도시, 지역, 경제지표 목록을 확인합니다.

    Returns:
        각 도구별 지원 옵션 목록
    """
    sections = []

    sections.append("## 부동산 실거래가 — 지원 지역")
    sections.append(", ".join(sorted(DISTRICT_CODES.keys())))

    sections.append("\n## 날씨 예보 — 지원 도시")
    sections.append(", ".join(sorted(CITY_GRID.keys())))

    sections.append("\n## 대기질 — 지원 지역")
    sections.append(", ".join(sorted(STATION_MAP.keys())))

    sections.append("\n## 경제통계 — 지원 지표")
    sections.append(", ".join(ECOS_STATS.keys()))

    sections.append("\n## 사업자등록 조회")
    sections.append("10자리 사업자등록번호를 입력하세요 (하이픈 유무 무관)")

    return "\n".join(sections)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 서버 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        mcp.run()
    else:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = port
        mcp.run(transport=transport)
