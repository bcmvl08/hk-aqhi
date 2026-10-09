#!/usr/bin/env python3
"""Fetch Hong Kong Observatory open-data JSON and write data/weather.json.

No API key. Traditional Chinese is the primary language; English is fetched
so the page can show both. An empty warning summary means nothing is in force.

The file is rewritten only when the weather itself changes. fetchedAt is
ignored in that comparison, same as the AQHI file.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from fetch_aqhi import USER_AGENT, iso_hkt, now_hkt, write_if_changed

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "weather.json"
API = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
MAX_BYTES = 2_000_000

# Short captions from the Observatory's weather-icon table.
# Night icons 70–75 differ only by lunar date; the public caption is still "fine".
ICONS = {
    50: ("陽光充沛", "Sunny"),
    51: ("間有陽光", "Sunny Periods"),
    52: ("短暫陽光", "Sunny Intervals"),
    53: ("間有陽光幾陣驟雨", "Sunny Periods with A Few Showers"),
    54: ("短暫陽光有驟雨", "Sunny Intervals with Showers"),
    60: ("多雲", "Cloudy"),
    61: ("密雲", "Overcast"),
    62: ("微雨", "Light Rain"),
    63: ("雨", "Rain"),
    64: ("大雨", "Heavy Rain"),
    65: ("雷暴", "Thunderstorms"),
    70: ("天色良好", "Fine"),
    71: ("天色良好", "Fine"),
    72: ("天色良好", "Fine"),
    73: ("天色良好", "Fine"),
    74: ("天色良好", "Fine"),
    75: ("天色良好", "Fine"),
    76: ("大致多雲", "Mainly Cloudy"),
    77: ("天色大致良好", "Mainly Fine"),
    80: ("大風", "Windy"),
    81: ("乾燥", "Dry"),
    82: ("潮濕", "Humid"),
    83: ("霧", "Fog"),
    84: ("薄霧", "Mist"),
    85: ("煙霞", "Haze"),
    90: ("熱", "Hot"),
    91: ("暖", "Warm"),
    92: ("涼", "Cool"),
    93: ("冷", "Cold"),
}

HKO_PLACES = {"香港天文台", "Hong Kong Observatory"}
KIND_ORDER = {
    "cyclone": 0,
    "rain": 1,
    "thunder": 2,
    "tsunami": 3,
    "landslip": 4,
    "wind": 5,
    "fire": 6,
    "hot": 7,
    "cold": 8,
    "alert": 9,
}


def endpoint(data_type: str, lang: str) -> str:
    return f"{API}?dataType={data_type}&lang={lang}"


def fetch_json(url: str):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"could not fetch {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ValueError(f"timed out fetching {url}") from exc
    if len(body) > MAX_BYTES:
        raise ValueError(f"response too large: {url}")
    payload = body.lstrip(b"\xef\xbb\xbf").strip()
    if not payload:
        raise ValueError(f"empty response: {url}")
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not JSON from {url}: {exc}") from exc
    if not isinstance(parsed, (dict, list)):
        raise ValueError(f"unexpected JSON from {url}")
    return parsed


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def as_number(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text) if "." in text else int(text)
        except ValueError:
            return None
    return None


def as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(part for part in (as_text(item) for item in value) if part).strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def icon_pair(number) -> tuple[str | None, str | None]:
    try:
        key = int(number)
    except (TypeError, ValueError):
        return None, None
    pair = ICONS.get(key)
    if pair is None:
        return None, None
    return pair


def pair_rows(tc_rows, en_rows, value_key: str) -> list[dict]:
    tc_rows = as_list(tc_rows)
    en_rows = as_list(en_rows)
    rows = []
    for index in range(max(len(tc_rows), len(en_rows))):
        tc = tc_rows[index] if index < len(tc_rows) and isinstance(tc_rows[index], dict) else {}
        en = en_rows[index] if index < len(en_rows) and isinstance(en_rows[index], dict) else {}
        value = as_number(tc.get(value_key))
        if value is None:
            value = as_number(en.get(value_key))
        place_zh = as_text(tc.get("place")) or as_text(en.get("place"))
        place_en = as_text(en.get("place")) or place_zh
        if value is None and not place_zh:
            continue
        rows.append(
            {
                "placeZh": place_zh,
                "placeEn": place_en,
                "value": value,
                "unit": as_text(tc.get("unit")) or as_text(en.get("unit")),
            }
        )
    return rows


def pick_hko(rows: list[dict]) -> dict | None:
    for row in rows:
        if row["placeZh"] in HKO_PLACES or row["placeEn"] in HKO_PLACES:
            return row
    return rows[0] if rows else None


def warning_kind(key: str, code: str) -> str:
    blob = f"{key} {code}".upper()
    if "WTCSGNL" in blob or code.upper().startswith("TC"):
        return "cyclone"
    if "RAIN" in blob:
        return "rain"
    if "FIRE" in blob:
        return "fire"
    if "FNT" in blob or key.upper() in {"WTS", "WFNTSA"} or code.upper().startswith("WTS"):
        return "thunder"
    if "FROST" in blob or "COLD" in blob:
        return "cold"
    if "HOT" in blob:
        return "hot"
    if "WMSGNL" in blob or "MONSOON" in blob:
        return "wind"
    if "WTMW" in blob or "TSUNAMI" in blob:
        return "tsunami"
    if key.upper() in {"WL", "WLANDSLIP"} or "LAND" in blob:
        return "landslip"
    return "alert"


def warning_level(code: str) -> str:
    token = (code or "").upper()
    if token in {"WRAINB", "TC10", "TC9"} or token.startswith("TC8"):
        return "serious"
    if token in {"WRAINR", "WFIRER", "TC3"}:
        return "high"
    if token in {"WRAINA", "WFIREY", "TC1"}:
        return "moderate"
    return "alert"


def iter_warnings(payload):
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield as_text(item.get("key")) or as_text(item.get("code")), item
        return
    if not isinstance(payload, dict) or not payload:
        return
    if "code" in payload or "name" in payload:
        yield as_text(payload.get("code")), payload
        return
    for key, item in payload.items():
        if isinstance(item, dict):
            yield str(key), item


def build_warnings(tc_payload, en_payload) -> list[dict]:
    english = {}
    for key, item in iter_warnings(en_payload):
        english[key] = item
    warnings = []
    for key, item in iter_warnings(tc_payload):
        action = as_text(item.get("actionCode")).upper()
        if action in {"CANCEL", "CANCELLED"}:
            continue
        en_item = english.get(key, {})
        code = as_text(item.get("code")) or as_text(en_item.get("code")) or key
        name_zh = as_text(item.get("name")) or code
        name_en = as_text(en_item.get("name")) or name_zh
        warnings.append(
            {
                "key": key,
                "code": code,
                "kind": warning_kind(key, code),
                "level": warning_level(code),
                "nameZh": name_zh,
                "nameEn": name_en,
                "typeZh": as_text(item.get("type")),
                "typeEn": as_text(en_item.get("type")),
                "actionCode": action,
                "issueTime": as_text(item.get("issueTime")) or None,
                "updateTime": as_text(item.get("updateTime")) or None,
            }
        )
    warnings.sort(key=lambda item: (KIND_ORDER.get(item["kind"], 9), item["nameZh"]))
    return warnings


def build_current(tc: dict, en: dict) -> dict:
    tc_temp = as_dict(tc.get("temperature"))
    en_temp = as_dict(en.get("temperature"))
    temperatures = pair_rows(tc_temp.get("data"), en_temp.get("data"), "value")
    chosen = pick_hko(temperatures)
    values = [row["value"] for row in temperatures if isinstance(row["value"], (int, float))]
    temperature = None
    if chosen and chosen["value"] is not None:
        temperature = {
            "placeZh": chosen["placeZh"],
            "placeEn": chosen["placeEn"],
            "value": chosen["value"],
            "unit": chosen["unit"] or "C",
            "time": as_text(tc_temp.get("recordTime")) or as_text(en_temp.get("recordTime")) or None,
            "min": min(values) if values else chosen["value"],
            "max": max(values) if values else chosen["value"],
        }

    tc_hum = as_dict(tc.get("humidity"))
    en_hum = as_dict(en.get("humidity"))
    humidity_rows = pair_rows(tc_hum.get("data"), en_hum.get("data"), "value")
    humidity_choice = pick_hko(humidity_rows)
    humidity = None
    if humidity_choice and humidity_choice["value"] is not None:
        humidity = {
            "placeZh": humidity_choice["placeZh"],
            "placeEn": humidity_choice["placeEn"],
            "value": humidity_choice["value"],
            "unit": "percent",
            "time": as_text(tc_hum.get("recordTime")) or as_text(en_hum.get("recordTime")) or None,
        }

    tc_rain = as_dict(tc.get("rainfall"))
    en_rain = as_dict(en.get("rainfall"))
    districts = pair_rows(tc_rain.get("data"), en_rain.get("data"), "max")
    rainfall = None
    if districts:
        numbers = [row["value"] for row in districts if isinstance(row["value"], (int, float))]
        maximum = max(numbers) if numbers else None
        leaders = []
        if maximum not in (None, 0):
            leaders = [
                {"placeZh": row["placeZh"], "placeEn": row["placeEn"], "value": row["value"]}
                for row in districts
                if row["value"] == maximum
            ][:6]
        rainfall = {
            "startTime": as_text(tc_rain.get("startTime")) or as_text(en_rain.get("startTime")) or None,
            "endTime": as_text(tc_rain.get("endTime")) or as_text(en_rain.get("endTime")) or None,
            "unit": "mm",
            "max": maximum,
            "districtCount": len(districts),
            "leaders": leaders,
        }

    tc_uv = as_dict(tc.get("uvindex"))
    en_uv = as_dict(en.get("uvindex"))
    uv_rows_tc = as_list(tc_uv.get("data"))
    uv_rows_en = as_list(en_uv.get("data"))
    uv = None
    if uv_rows_tc or uv_rows_en:
        tc_row = uv_rows_tc[0] if uv_rows_tc and isinstance(uv_rows_tc[0], dict) else {}
        en_row = uv_rows_en[0] if uv_rows_en and isinstance(uv_rows_en[0], dict) else {}
        value = as_number(tc_row.get("value"))
        if value is None:
            value = as_number(en_row.get("value"))
        if value is not None:
            uv = {
                "placeZh": as_text(tc_row.get("place")) or as_text(en_row.get("place")),
                "placeEn": as_text(en_row.get("place")) or as_text(tc_row.get("place")),
                "value": value,
                "descZh": as_text(tc_row.get("desc")),
                "descEn": as_text(en_row.get("desc")),
                "recordDescZh": as_text(tc_uv.get("recordDesc")),
                "recordDescEn": as_text(en_uv.get("recordDesc")),
            }

    icons = tc.get("icon") if isinstance(tc.get("icon"), list) else en.get("icon")
    icon_number = None
    if isinstance(icons, list) and icons:
        icon_number = as_number(icons[0])
        if isinstance(icon_number, float) and icon_number.is_integer():
            icon_number = int(icon_number)
    icon_zh, icon_en = icon_pair(icon_number)

    return {
        "updateTime": as_text(tc.get("updateTime")) or as_text(en.get("updateTime")) or None,
        "icon": icon_number,
        "iconZh": icon_zh,
        "iconEn": icon_en,
        "temperature": temperature,
        "humidity": humidity,
        "rainfall": rainfall,
        "uv": uv,
        "messageZh": as_text(tc.get("warningMessage")),
        "messageEn": as_text(en.get("warningMessage")),
        "cycloneMessageZh": as_text(tc.get("tcmessage")),
        "cycloneMessageEn": as_text(en.get("tcmessage")),
    }


def forecast_date(token: str) -> str:
    text = as_text(token)
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def build_forecast(tc: dict, en: dict) -> dict:
    en_by_date = {}
    for item in as_list(en.get("weatherForecast")):
        if isinstance(item, dict):
            en_by_date[forecast_date(item.get("forecastDate"))] = item
    days = []
    for item in as_list(tc.get("weatherForecast")):
        if not isinstance(item, dict):
            continue
        date = forecast_date(item.get("forecastDate"))
        other = en_by_date.get(date, {})
        icon_number = as_number(item.get("ForecastIcon"))
        if icon_number is None:
            icon_number = as_number(other.get("ForecastIcon"))
        if isinstance(icon_number, float) and icon_number.is_integer():
            icon_number = int(icon_number)
        icon_zh, icon_en = icon_pair(icon_number)
        max_temp = as_dict(item.get("forecastMaxtemp")).get("value")
        min_temp = as_dict(item.get("forecastMintemp")).get("value")
        if max_temp is None:
            max_temp = as_dict(other.get("forecastMaxtemp")).get("value")
        if min_temp is None:
            min_temp = as_dict(other.get("forecastMintemp")).get("value")
        days.append(
            {
                "date": date,
                "weekZh": as_text(item.get("week")),
                "weekEn": as_text(other.get("week")),
                "weatherZh": as_text(item.get("forecastWeather")),
                "weatherEn": as_text(other.get("forecastWeather")),
                "windZh": as_text(item.get("forecastWind")),
                "windEn": as_text(other.get("forecastWind")),
                "maxTemp": as_number(max_temp),
                "minTemp": as_number(min_temp),
                "icon": icon_number,
                "iconZh": icon_zh,
                "iconEn": icon_en,
                "psrZh": as_text(item.get("PSR")),
                "psrEn": as_text(other.get("PSR")),
            }
        )
    if not days:
        raise ValueError("forecast has no days")
    return {
        "updateTime": as_text(tc.get("updateTime")) or as_text(en.get("updateTime")) or None,
        "generalSituationZh": as_text(tc.get("generalSituation")),
        "generalSituationEn": as_text(en.get("generalSituation")),
        "days": days,
    }


def build_weather(
    current_tc: dict,
    current_en: dict,
    warn_tc,
    warn_en,
    forecast_tc: dict,
    forecast_en: dict,
    fetched_at: datetime | None = None,
) -> dict:
    if not isinstance(current_tc, dict) or not isinstance(forecast_tc, dict):
        raise ValueError("current weather and forecast must be JSON objects")
    fetched = fetched_at or now_hkt()
    current = build_current(current_tc, current_en if isinstance(current_en, dict) else {})
    forecast = build_forecast(forecast_tc, forecast_en if isinstance(forecast_en, dict) else {})
    if not current["updateTime"] and not forecast["updateTime"]:
        raise ValueError("weather response has no update time")
    return {
        "schemaVersion": 1,
        "provider": "Hong Kong Observatory",
        "timezone": "Asia/Hong_Kong",
        "fetchedAt": iso_hkt(fetched) if isinstance(fetched, datetime) else fetched,
        "sources": {
            "current": endpoint("rhrread", "tc"),
            "warnings": endpoint("warnsum", "tc"),
            "forecast": endpoint("fnd", "tc"),
        },
        "current": current,
        "warnings": build_warnings(warn_tc, warn_en),
        "forecast": forecast,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch HKO weather JSON.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true", help="fetch and validate, but do not write")
    args = parser.parse_args(argv)

    current_tc = fetch_json(endpoint("rhrread", "tc"))
    current_en = fetch_json(endpoint("rhrread", "en"))
    warn_tc = fetch_json(endpoint("warnsum", "tc"))
    warn_en = fetch_json(endpoint("warnsum", "en"))
    forecast_tc = fetch_json(endpoint("fnd", "tc"))
    forecast_en = fetch_json(endpoint("fnd", "en"))
    payload = build_weather(
        current_tc,
        current_en,
        warn_tc,
        warn_en,
        forecast_tc,
        forecast_en,
        fetched_at=now_hkt(),
    )
    warnings = len(payload["warnings"])
    days = len(payload["forecast"]["days"])
    if args.check:
        print(
            f"ok warnings={warnings} days={days} current={payload['current']['updateTime']}",
            flush=True,
        )
        return 0
    changed = write_if_changed(args.out, payload)
    print(
        f"{'updated' if changed else 'unchanged'} warnings={warnings} days={days} "
        f"current={payload['current']['updateTime']} out={args.out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
