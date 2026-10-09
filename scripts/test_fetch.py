#!/usr/bin/env python3
"""Unit tests for the AQHI XML parser. No network."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import fetch_aqhi

HKT = ZoneInfo("Asia/Hong_Kong")
ROOT = Path(__file__).resolve().parents[1]

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<AQHI24HrReport>
  <title>Environmental Protection Department - AQHI</title>
  <copyright>Environmental Protection Department</copyright>
  <lastBuildDate>Fri, 09 Oct 2026 02:30:00 +0800</lastBuildDate>
  <item><type>General Stations</type><StationName>Central/Western</StationName>
    <DateTime>Thu, 08 Oct 2026 22:00:00 +0800</DateTime><aqhi>4</aqhi></item>
  <item><type>General Stations</type><StationName>Central/Western</StationName>
    <DateTime>Thu, 08 Oct 2026 22:00:00 +0800</DateTime><aqhi>6</aqhi></item>
  <item><type>General Stations</type><StationName>Central/Western</StationName>
    <DateTime>Thu, 08 Oct 2026 23:00:00 +0800</DateTime><aqhi>6</aqhi></item>
  <item><type>General Stations</type><StationName>Central/Western</StationName>
    <DateTime>Fri, 09 Oct 2026 00:00:00 +0800</DateTime><aqhi>10+</aqhi></item>
  <item><type>General Stations</type><StationName>Central/Western</StationName>
    <DateTime>Fri, 09 Oct 2026 01:00:00 +0800</DateTime><aqhi>-</aqhi></item>
  <item><type>General Stations</type><StationName>Central/Western</StationName>
    <DateTime>Fri, 09 Oct 2026 02:00:00 +0800</DateTime><aqhi>7</aqhi></item>
  <item><type>Roadside Stations</type><StationName>Causeway Bay</StationName>
    <DateTime>Fri, 09 Oct 2026 01:00:00 +0800</DateTime><aqhi>3</aqhi></item>
  <item><type>Roadside Stations</type><StationName>Causeway Bay</StationName>
    <DateTime>Fri, 09 Oct 2026 02:00:00 +0800</DateTime><aqhi>3</aqhi></item>
  <item><type>Special Stations</type><StationName>Unknown Place</StationName>
    <DateTime>Fri, 09 Oct 2026 02:00:00 +0800</DateTime><aqhi>4</aqhi></item>
</AQHI24HrReport>
"""


class ClassifyTests(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(fetch_aqhi.classify("1")["band"], "low")
        self.assertEqual(fetch_aqhi.classify("3")["band"], "low")
        self.assertEqual(fetch_aqhi.classify("4")["band"], "moderate")
        self.assertEqual(fetch_aqhi.classify("6")["band"], "moderate")
        self.assertEqual(fetch_aqhi.classify("7")["band"], "high")
        self.assertEqual(fetch_aqhi.classify("8")["band"], "very_high")
        self.assertEqual(fetch_aqhi.classify("10")["band"], "very_high")
        serious = fetch_aqhi.classify("10+")
        self.assertEqual(serious["aqhi"], "10+")
        self.assertEqual(serious["value"], 11)
        self.assertEqual(serious["band"], "serious")
        self.assertEqual(fetch_aqhi.classify("10＋")["band"], "serious")
        self.assertEqual(fetch_aqhi.classify("12")["aqhi"], "10+")

    def test_missing(self):
        for token in ("-", "—", "*", "N/A", "", "0"):
            self.assertIsNone(fetch_aqhi.classify(token)["value"], token)


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.payload = fetch_aqhi.build_payload(
            SAMPLE.encode("utf-8"),
            fetched_at=datetime(2026, 10, 9, 2, 40, tzinfo=HKT),
        )

    def test_report_time_and_order(self):
        self.assertEqual(self.payload["reportTime"], "2026-10-09T02:30:00+08:00")
        self.assertEqual(self.payload["fetchedAt"], "2026-10-09T02:40:00+08:00")
        self.assertEqual(
            [station["id"] for station in self.payload["stations"]],
            ["central-western", "causeway-bay", "unknown-place"],
        )
        central = self.payload["stations"][0]
        self.assertEqual(central["nameZh"], "中西區")
        self.assertEqual(central["type"], "general")
        unknown = self.payload["stations"][2]
        self.assertEqual(unknown["nameZh"], "Unknown Place")
        self.assertEqual(unknown["type"], "other")

    def test_duplicate_hour_keeps_the_later_item(self):
        hours = self.payload["stations"][0]["hours"]
        self.assertEqual(hours[0]["aqhi"], "6")
        self.assertEqual(len(hours), 5)

    def test_daily_max_and_latest(self):
        central = self.payload["stations"][0]
        self.assertEqual(central["latest"]["aqhi"], "7")
        self.assertEqual(central["latest"]["band"], "high")
        self.assertEqual(central["max24h"]["aqhi"], "10+")
        self.assertEqual(central["max24h"]["time"], "2026-10-09T00:00:00+08:00")
        self.assertEqual(central["dailyMax"][0]["date"], "2026-10-08")
        self.assertEqual(central["dailyMax"][0]["time"], "2026-10-08T23:00:00+08:00")
        self.assertEqual(central["dailyMax"][1]["aqhi"], "10+")
        self.assertEqual(central["highHours"], 2)
        self.assertIn("上一小時沒有讀數", central["notes"][0]["zh"])
        roadside = self.payload["stations"][1]
        self.assertEqual(roadside["notes"][0]["en"], "Same as the previous hour.")
        self.assertEqual(roadside["highHours"], 0)

    def test_bad_xml(self):
        with self.assertRaises(ValueError):
            fetch_aqhi.parse_xml(b"<html>nope</html>")
        with self.assertRaises(ValueError):
            fetch_aqhi.build_payload(b"not xml")


class WriteTests(unittest.TestCase):
    def test_same_readings_do_not_rewrite(self):
        first = fetch_aqhi.build_payload(
            SAMPLE.encode("utf-8"),
            fetched_at=datetime(2026, 10, 9, 2, 40, tzinfo=HKT),
        )
        second = fetch_aqhi.build_payload(
            SAMPLE.encode("utf-8"),
            fetched_at=datetime(2026, 10, 9, 3, 40, tzinfo=HKT),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aqhi.json"
            self.assertTrue(fetch_aqhi.write_if_changed(path, first))
            written = path.read_text(encoding="utf-8")
            self.assertFalse(fetch_aqhi.write_if_changed(path, second))
            self.assertEqual(path.read_text(encoding="utf-8"), written)
            saved = json.loads(written)
            self.assertEqual(saved["fetchedAt"], "2026-10-09T02:40:00+08:00")

    def test_new_reading_rewrites(self):
        first = fetch_aqhi.build_payload(
            SAMPLE.encode("utf-8"),
            fetched_at=datetime(2026, 10, 9, 2, 40, tzinfo=HKT),
        )
        changed_xml = SAMPLE.replace("<aqhi>7</aqhi>", "<aqhi>8</aqhi>", 1)
        second = fetch_aqhi.build_payload(
            changed_xml.encode("utf-8"),
            fetched_at=datetime(2026, 10, 9, 3, 40, tzinfo=HKT),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aqhi.json"
            fetch_aqhi.write_if_changed(path, first)
            self.assertTrue(fetch_aqhi.write_if_changed(path, second))
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["stations"][0]["latest"]["aqhi"], "8")


class PageContractTests(unittest.TestCase):
    def test_page_refreshes_json_and_does_not_dispatch(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "js" / "aqhi.js").read_text(encoding="utf-8")
        css = (ROOT / "css" / "aqhi.css").read_text(encoding="utf-8")
        blob = html + js
        self.assertIn("立即更新", html)
        self.assertIn("Refresh", html)
        self.assertIn("data/aqhi.json", js)
        self.assertIn("cache", js)
        self.assertIn("no-store", js)
        self.assertNotIn("api.github.com", blob)
        self.assertNotIn("workflow/dispatches", blob)
        self.assertNotIn("github_token", blob.lower())
        self.assertNotIn("ghp_", blob)
        self.assertIn("actions/workflows/update-aqhi.yml", html)
        self.assertIn("#44af35", css)
        self.assertIn("#231816", css)
        self.assertIn(".refresh:active", css)
        self.assertIn(".refresh:disabled", css)
        self.assertIn(".section-nav a:active", css)
        self.assertIn("markNav", js)
        self.assertIn("https://data.weather.gov.hk", html)
        self.assertIn("https://www.aqhi.gov.hk", html)
        self.assertIn("id=\"countdown\"", html)
        self.assertIn("prefers-reduced-motion", css)
        self.assertNotIn("workflow/dispatches", blob)

    def test_workflow_schedule_and_dispatch(self):
        workflow = (ROOT / ".github" / "workflows" / "update-aqhi.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("cron:", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("fetch_aqhi.py", workflow)
        self.assertIn("data/aqhi.json", workflow)


if __name__ == "__main__":
    unittest.main()
