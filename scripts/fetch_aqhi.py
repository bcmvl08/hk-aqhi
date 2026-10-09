#!/usr/bin/env python3
"""Fetch the EPD past-24-hour AQHI XML and write data/aqhi.json.

Source (no API key):
https://www.aqhi.gov.hk/epd/ddata/html/out/24aqhi_Eng.xml

The file is rewritten only when the readings or report time change.
`fetchedAt` is ignored in that comparison, so an hourly run that sees the
same figures does not touch the file and GitHub Actions does not commit.

Chinese station names are the Traditional Chinese names published beside
these English names. Values come only from the English XML.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "aqhi.json"
SOURCE_URL = "https://www.aqhi.gov.hk/epd/ddata/html/out/24aqhi_Eng.xml"
SOURCE_PAGE = (
    "https://data.gov.hk/tc-data/dataset/"
    "hk-epd-airteam-past24hr-aqhi-of-individual-air-quality-monitoring-stations"
)
USER_AGENT = "hk-aqhi/1.0 (+https://github.com/bcmvl08/hk-aqhi)"
MAX_BYTES = 5_000_000

# EPD order on the past-24-hour feed, checked 2026-10-09.
STATION_ORDER = [
    ("General Stations", "Central/Western"),
    ("General Stations", "Southern"),
    ("General Stations", "Eastern"),
    ("General Stations", "Kwun Tong"),
    ("General Stations", "Sham Shui Po"),
    ("General Stations", "Kwai Chung"),
    ("General Stations", "Tsuen Wan"),
    ("General Stations", "Tseung Kwan O"),
    ("General Stations", "Yuen Long"),
    ("General Stations", "Tuen Mun"),
    ("General Stations", "Tung Chung"),
    ("General Stations", "Tai Po"),
    ("General Stations", "Sha Tin"),
    ("General Stations", "North"),
    ("General Stations", "Tap Mun"),
    ("Roadside Stations", "Causeway Bay"),
    ("Roadside Stations", "Central"),
    ("Roadside Stations", "Mong Kok"),
]

NAMES_ZH = {
    "Central/Western": "中西區",
    "Southern": "南區",
    "Eastern": "東區",
    "Kwun Tong": "觀塘",
    "Sham Shui Po": "深水埗",
    "Kwai Chung": "葵涌",
    "Tsuen Wan": "荃灣",
    "Tseung Kwan O": "將軍澳",
    "Yuen Long": "元朗",
    "Tuen Mun": "屯門",
    "Tung Chung": "東涌",
    "Tai Po": "大埔",
    "Sha Tin": "沙田",
    "North": "北區",
    "Tap Mun": "塔門",
    "Causeway Bay": "銅鑼灣",
    "Central": "中環",
    "Mong Kok": "旺角",
}

IDS = {
    "Central/Western": "central-western",
    "Southern": "southern",
    "Eastern": "eastern",
    "Kwun Tong": "kwun-tong",
    "Sham Shui Po": "sham-shui-po",
    "Kwai Chung": "kwai-chung",
    "Tsuen Wan": "tsuen-wan",
    "Tseung Kwan O": "tseung-kwan-o",
    "Yuen Long": "yuen-long",
    "Tuen Mun": "tuen-mun",
    "Tung Chung": "tung-chung",
    "Tai Po": "tai-po",
    "Sha Tin": "sha-tin",
    "North": "north",
    "Tap Mun": "tap-mun",
    "Causeway Bay": "causeway-bay",
    "Central": "central",
    "Mong Kok": "mong-kok",
}

MISSING = {"", "-", "—", "–", "*", "N/A", "NA", "n.a.", "N.A."}


def now_hkt() -> datetime:
    return datetime.now(HKT)


def iso_hkt(dt: datetime) -> str:
    return dt.astimezone(HKT).isoformat(timespec="seconds")


def parse_rfc822(text: str | None) -> datetime | None:
    if not text or not text.strip():
        return None
    try:
        parsed = parsedate_to_datetime(text.strip())
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=HKT)
    return parsed.astimezone(HKT)


def classify(raw: str | None) -> dict:
    """Map one AQHI token to a display string, a sortable value, and a band.

    10+ sorts as 11. The public scale has no 11; EPD prints it as 10+.
    """
    if raw is None:
        return {"aqhi": None, "value": None, "band": None}
    text = raw.strip()
    if text in MISSING:
        return {"aqhi": None, "value": None, "band": None}
    if text in {"10+", "10＋"}:
        return {"aqhi": "10+", "value": 11, "band": "serious"}
    if text.isdigit():
        number = int(text)
        if number >= 11:
            return {"aqhi": "10+", "value": 11, "band": "serious"}
        if number < 1:
            return {"aqhi": None, "value": None, "band": None}
        if number <= 3:
            band = "low"
        elif number <= 6:
            band = "moderate"
        elif number == 7:
            band = "high"
        else:
            band = "very_high"
        return {"aqhi": str(number), "value": number, "band": band}
    return {"aqhi": None, "value": None, "band": None}


def station_type(raw: str) -> str:
    lowered = raw.lower()
    if "roadside" in lowered:
        return "roadside"
    if "general" in lowered:
        return "general"
    return "other"


def slugify(name: str) -> str:
    out = []
    prev_dash = False
    for char in name.lower():
        if char.isascii() and char.isalnum():
            out.append(char)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    slug = "".join(out).strip("-")
    return slug or "station"


def strip_namespaces(root: ET.Element) -> None:
    for elem in root.iter():
        if isinstance(elem.tag, str) and "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]


def reading_from(when: datetime, raw: str | None) -> dict:
    classified = classify(raw)
    return {
        "time": iso_hkt(when),
        "aqhi": classified["aqhi"],
        "value": classified["value"],
        "band": classified["band"],
    }


def pick_max(readings: list[dict]) -> dict | None:
    """Highest numeric AQHI. Ties keep the latest hour."""
    ranked = [item for item in readings if item["value"] is not None]
    if not ranked:
        return None
    best = max(ranked, key=lambda item: (item["value"], item["time"]))
    return {
        "time": best["time"],
        "aqhi": best["aqhi"],
        "value": best["value"],
        "band": best["band"],
    }


def daily_maxes(hours: list[dict]) -> list[dict]:
    by_date: dict[str, list[dict]] = {}
    for hour in hours:
        date = hour["time"][:10]
        by_date.setdefault(date, []).append(hour)
    rows = []
    for date in sorted(by_date):
        best = pick_max(by_date[date])
        if best is None:
            rows.append(
                {
                    "date": date,
                    "time": None,
                    "aqhi": None,
                    "value": None,
                    "band": None,
                }
            )
        else:
            rows.append({"date": date, **best})
    return rows


def notes_for(hours: list[dict], latest: dict) -> tuple[list[dict], int]:
    notes = []
    numeric = [hour for hour in hours if hour["value"] is not None]
    high_hours = sum(1 for hour in numeric if hour["value"] >= 7)

    if latest["value"] is None:
        notes.append(
            {
                "zh": "最新一小時沒有讀數。",
                "en": "The latest hour has no reading.",
            }
        )
    elif len(hours) >= 2:
        previous = hours[-2]
        if previous["value"] is None:
            notes.append(
                {
                    "zh": "上一小時沒有讀數。",
                    "en": "The previous hour has no reading.",
                }
            )
        elif latest["value"] > previous["value"]:
            notes.append(
                {
                    "zh": f"較上一小時上升（{previous['aqhi']} → {latest['aqhi']}）。",
                    "en": (
                        f"Up from the previous hour "
                        f"({previous['aqhi']} → {latest['aqhi']})."
                    ),
                }
            )
        elif latest["value"] < previous["value"]:
            notes.append(
                {
                    "zh": f"較上一小時下跌（{previous['aqhi']} → {latest['aqhi']}）。",
                    "en": (
                        f"Down from the previous hour "
                        f"({previous['aqhi']} → {latest['aqhi']})."
                    ),
                }
            )
        else:
            notes.append(
                {
                    "zh": "與上一小時相同。",
                    "en": "Same as the previous hour.",
                }
            )

    if high_hours == 0:
        notes.append(
            {
                "zh": "過去 24 小時沒有高、甚高或嚴重讀數。",
                "en": "No High, Very High, or Serious reading in the past 24 hours.",
            }
        )
    elif high_hours == 1:
        notes.append(
            {
                "zh": "過去 24 小時有 1 小時處於高或以上。",
                "en": "1 hour at High or above in the past 24 hours.",
            }
        )
    else:
        notes.append(
            {
                "zh": f"過去 24 小時有 {high_hours} 小時處於高或以上。",
                "en": f"{high_hours} hours at High or above in the past 24 hours.",
            }
        )
    return notes, high_hours


def parse_xml(xml: bytes) -> ET.Element:
    if len(xml) > MAX_BYTES:
        raise ValueError("response too large")
    payload = xml.lstrip(b"\xef\xbb\xbf").strip()
    if not payload.startswith(b"<"):
        raise ValueError("response is not XML")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError(f"not AQHI XML: {exc}") from exc
    strip_namespaces(root)
    if root.tag != "AQHI24HrReport":
        raise ValueError(f"unexpected root <{root.tag}>")
    return root


def build_payload(xml: bytes, fetched_at: datetime | None = None) -> dict:
    root = parse_xml(xml)
    grouped: dict[tuple[str, str], dict[str, dict]] = {}
    seen: list[tuple[str, str]] = []
    for item in root.findall("item"):
        name = (item.findtext("StationName") or "").strip()
        raw_type = (item.findtext("type") or "").strip()
        if not name:
            continue
        when = parse_rfc822(item.findtext("DateTime"))
        if when is None:
            continue
        key = (raw_type, name)
        if key not in grouped:
            grouped[key] = {}
            seen.append(key)
        reading = reading_from(when, item.findtext("aqhi"))
        grouped[key][reading["time"]] = reading

    if not grouped:
        raise ValueError("XML has no station readings")

    order_index = {pair: index for index, pair in enumerate(STATION_ORDER)}

    def sort_key(pair: tuple[str, str]) -> tuple:
        if pair in order_index:
            return (0, order_index[pair])
        return (1, pair[0], pair[1])

    used_ids: set[str] = set()
    stations = []
    for raw_type, name in sorted(seen, key=sort_key):
        hours = [grouped[(raw_type, name)][key] for key in sorted(grouped[(raw_type, name)])]
        latest = dict(hours[-1])
        maximum = pick_max(hours)
        notes, high_hours = notes_for(hours, latest)
        base_id = IDS.get(name) or slugify(name)
        station_id = base_id
        suffix = 2
        while station_id in used_ids:
            station_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(station_id)
        stations.append(
            {
                "id": station_id,
                "nameEn": name,
                "nameZh": NAMES_ZH.get(name, name),
                "type": station_type(raw_type),
                "typeRaw": raw_type,
                "latest": latest,
                "max24h": maximum,
                "dailyMax": daily_maxes(hours),
                "highHours": high_hours,
                "notes": notes,
                "hours": hours,
            }
        )

    report = parse_rfc822(root.findtext("lastBuildDate"))
    if report is None:
        latest_times = [
            station["latest"]["time"]
            for station in stations
            if station["latest"]["time"]
        ]
        if not latest_times:
            raise ValueError("no report time")
        report_time = max(latest_times)
    else:
        report_time = iso_hkt(report)

    fetched = fetched_at or now_hkt()
    return {
        "schemaVersion": 1,
        "source": SOURCE_URL,
        "sourcePage": SOURCE_PAGE,
        "provider": (root.findtext("copyright") or "Environmental Protection Department").strip(),
        "timezone": "Asia/Hong_Kong",
        "reportTime": report_time,
        "fetchedAt": iso_hkt(fetched) if isinstance(fetched, datetime) else fetched,
        "title": (root.findtext("title") or "AQHI").strip(),
        "stations": stations,
    }


def without_fetched(payload: dict) -> dict:
    copy = json.loads(json.dumps(payload))
    copy.pop("fetchedAt", None)
    return copy


def write_if_changed(path: Path, payload: dict) -> bool:
    path = Path(path)
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = None
        if isinstance(old, dict) and without_fetched(old) == without_fetched(payload):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return True


def fetch_xml(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/xml, text/xml, */*",
        },
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
        raise ValueError("response too large")
    if not body.strip():
        raise ValueError("empty response")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch EPD 24-hour AQHI XML into JSON.")
    parser.add_argument("--xml", type=Path, help="parse a local XML file instead of fetching")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--url", default=SOURCE_URL)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fetch and validate, but do not write",
    )
    args = parser.parse_args(argv)

    xml = args.xml.read_bytes() if args.xml else fetch_xml(args.url)
    payload = build_payload(xml, fetched_at=now_hkt())
    count = len(payload["stations"])
    hours = sum(len(station["hours"]) for station in payload["stations"])
    if args.check:
        print(
            f"ok stations={count} hours={hours} report={payload['reportTime']}",
            flush=True,
        )
        return 0
    changed = write_if_changed(args.out, payload)
    print(
        f"{'updated' if changed else 'unchanged'} stations={count} "
        f"hours={hours} report={payload['reportTime']} out={args.out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
