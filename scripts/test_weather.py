#!/usr/bin/env python3
"""Unit tests for the Observatory weather parser. No network."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fetch_weather

HKT = ZoneInfo("Asia/Hong_Kong")
ROOT = Path(__file__).resolve().parents[1]

CURRENT_TC = {
    "icon": [51],
    "updateTime": "2026-10-09T14:02:00+08:00",
    "warningMessage": "",
    "tcmessage": "",
    "temperature": {
        "recordTime": "2026-10-09T14:00:00+08:00",
        "data": [
            {"place": "京士柏", "value": 29, "unit": "C"},
            {"place": "香港天文台", "value": 30, "unit": "C"},
        ],
    },
    "humidity": {
        "recordTime": "2026-10-09T14:00:00+08:00",
        "data": [{"unit": "percent", "value": 54, "place": "香港天文台"}],
    },
    "rainfall": {
        "startTime": "2026-10-09T12:45:00+08:00",
        "endTime": "2026-10-09T13:45:00+08:00",
        "data": [
            {"unit": "mm", "place": "中西區", "max": 0},
            {"unit": "mm", "place": "元朗", "max": 3},
            {"unit": "mm", "place": "屯門", "max": 3},
        ],
    },
    "uvindex": {
        "recordDesc": "過去一小時",
        "data": [{"place": "京士柏", "value": 7, "desc": "高"}],
    },
}

CURRENT_EN = {
    "icon": [51],
    "updateTime": "2026-10-09T14:02:00+08:00",
    "warningMessage": "",
    "temperature": {
        "data": [
            {"place": "King's Park", "value": 29, "unit": "C"},
            {"place": "Hong Kong Observatory", "value": 30, "unit": "C"},
        ]
    },
    "humidity": {"data": [{"unit": "percent", "value": 54, "place": "Hong Kong Observatory"}]},
    "rainfall": {
        "data": [
            {"unit": "mm", "place": "Central & Western District", "max": 0},
            {"unit": "mm", "place": "Yuen Long", "max": 3},
            {"unit": "mm", "place": "Tuen Mun", "max": 3},
        ]
    },
    "uvindex": {
        "recordDesc": "During the past hour",
        "data": [{"place": "King's Park", "value": 7, "desc": "high"}],
    },
}

WARN_TC = {
    "WRAIN": {
        "name": "紅色暴雨警告信號",
        "code": "WRAINR",
        "actionCode": "ISSUE",
        "issueTime": "2026-10-09T08:00:00+08:00",
        "updateTime": "2026-10-09T08:05:00+08:00",
    },
    "WFIRE": {
        "name": "黃色火災危險警告",
        "code": "WFIREY",
        "actionCode": "CANCEL",
    },
}

WARN_EN = {
    "WRAIN": {"name": "Red Rainstorm Warning Signal", "code": "WRAINR", "actionCode": "ISSUE"},
    "WFIRE": {"name": "Yellow Fire Danger Warning", "code": "WFIREY", "actionCode": "CANCEL"},
}

FORECAST_TC = {
    "generalSituation": "華南大致天晴。",
    "updateTime": "2026-10-09T11:30:00+08:00",
    "weatherForecast": [
        {
            "forecastDate": "20261010",
            "week": "星期六",
            "forecastWind": "東風4級。",
            "forecastWeather": "天晴。日間乾燥。",
            "forecastMaxtemp": {"value": 31, "unit": "C"},
            "forecastMintemp": {"value": 26, "unit": "C"},
            "ForecastIcon": 50,
            "PSR": "低",
        }
    ],
}

FORECAST_EN = {
    "generalSituation": "Fine over southern China.",
    "updateTime": "2026-10-09T11:30:00+08:00",
    "weatherForecast": [
        {
            "forecastDate": "20261010",
            "week": "Saturday",
            "forecastWind": "East force 4.",
            "forecastWeather": "Fine. Dry during the day.",
            "forecastMaxtemp": {"value": 31, "unit": "C"},
            "forecastMintemp": {"value": 26, "unit": "C"},
            "ForecastIcon": 50,
            "PSR": "Low",
        }
    ],
}


def sample(fetched_at):
    return fetch_weather.build_weather(
        CURRENT_TC,
        CURRENT_EN,
        WARN_TC,
        WARN_EN,
        FORECAST_TC,
        FORECAST_EN,
        fetched_at=fetched_at,
    )


class WeatherParseTests(unittest.TestCase):
    def setUp(self):
        self.payload = sample(datetime(2026, 10, 9, 14, 11, tzinfo=HKT))

    def test_current_hko_reading(self):
        current = self.payload["current"]
        self.assertEqual(current["updateTime"], "2026-10-09T14:02:00+08:00")
        self.assertEqual(current["icon"], 51)
        self.assertEqual(current["iconZh"], "間有陽光")
        self.assertEqual(current["iconEn"], "Sunny Periods")
        self.assertEqual(current["temperature"]["placeZh"], "香港天文台")
        self.assertEqual(current["temperature"]["placeEn"], "Hong Kong Observatory")
        self.assertEqual(current["temperature"]["value"], 30)
        self.assertEqual(current["temperature"]["min"], 29)
        self.assertEqual(current["temperature"]["max"], 30)
        self.assertEqual(current["humidity"]["value"], 54)
        self.assertEqual(current["uv"]["value"], 7)
        self.assertEqual(current["uv"]["descZh"], "高")
        self.assertEqual(current["uv"]["descEn"], "high")

    def test_rainfall_leaders_skip_zeros(self):
        rain = self.payload["current"]["rainfall"]
        self.assertEqual(rain["max"], 3)
        self.assertEqual(rain["districtCount"], 3)
        self.assertEqual([item["placeZh"] for item in rain["leaders"]], ["元朗", "屯門"])
        self.assertEqual(rain["leaders"][0]["placeEn"], "Yuen Long")

    def test_cancelled_warning_is_dropped(self):
        self.assertEqual(len(self.payload["warnings"]), 1)
        warning = self.payload["warnings"][0]
        self.assertEqual(warning["code"], "WRAINR")
        self.assertEqual(warning["nameZh"], "紅色暴雨警告信號")
        self.assertEqual(warning["nameEn"], "Red Rainstorm Warning Signal")
        self.assertEqual(warning["kind"], "rain")
        self.assertEqual(warning["level"], "high")

    def test_empty_warning_summary(self):
        payload = fetch_weather.build_weather(
            CURRENT_TC, CURRENT_EN, {}, {}, FORECAST_TC, FORECAST_EN,
            fetched_at=datetime(2026, 10, 9, 14, 11, tzinfo=HKT),
        )
        self.assertEqual(payload["warnings"], [])

    def test_forecast_day_and_missing_uv(self):
        day = self.payload["forecast"]["days"][0]
        self.assertEqual(day["date"], "2026-10-10")
        self.assertEqual(day["weekZh"], "星期六")
        self.assertEqual(day["weekEn"], "Saturday")
        self.assertEqual(day["maxTemp"], 31)
        self.assertEqual(day["minTemp"], 26)
        self.assertEqual(day["iconZh"], "陽光充沛")
        self.assertEqual(self.payload["forecast"]["generalSituationEn"], "Fine over southern China.")
        quiet = dict(CURRENT_TC)
        quiet_en = dict(CURRENT_EN)
        quiet.pop("uvindex")
        quiet_en.pop("uvindex")
        payload = fetch_weather.build_weather(
            quiet, quiet_en, {}, {}, FORECAST_TC, FORECAST_EN,
            fetched_at=datetime(2026, 10, 9, 14, 11, tzinfo=HKT),
        )
        self.assertIsNone(payload["current"]["uv"])

    def test_same_weather_does_not_rewrite(self):
        first = sample(datetime(2026, 10, 9, 14, 11, tzinfo=HKT))
        second = sample(datetime(2026, 10, 9, 15, 11, tzinfo=HKT))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "weather.json"
            self.assertTrue(fetch_weather.write_if_changed(path, first))
            written = path.read_text(encoding="utf-8")
            self.assertFalse(fetch_weather.write_if_changed(path, second))
            self.assertEqual(path.read_text(encoding="utf-8"), written)
            self.assertEqual(json.loads(written)["fetchedAt"], "2026-10-09T14:11:00+08:00")


class WeatherPageTests(unittest.TestCase):
    def test_page_and_workflow_include_weather(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "js" / "aqhi.js").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "update-aqhi.yml").read_text(encoding="utf-8")
        self.assertIn("data/weather.json", js)
        self.assertIn("id=\"weather\"", html)
        self.assertIn("香港天文台", html)
        self.assertIn("不是官方警報", html)
        self.assertIn("fetch_weather.py", workflow)
        self.assertIn("data/weather.json", workflow)
        self.assertNotIn("api.github.com", html + js)


if __name__ == "__main__":
    unittest.main()
