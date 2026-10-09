/* Turn live Observatory JSON and EPD AQHI XML into the same shapes as data/*.json.
   The Observatory responses allow any origin. The EPD XML does not, so the page
   catches that failure and uses the published file. */
(function (root) {
  "use strict";

  var HKO = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php";
  var AQHI_URL = "https://www.aqhi.gov.hk/epd/ddata/html/out/24aqhi_Eng.xml";
  var AQHI_PAGE = "https://data.gov.hk/tc-data/dataset/hk-epd-airteam-past24hr-aqhi-of-individual-air-quality-monitoring-stations";

  var ICONS = {
    50: ["陽光充沛", "Sunny"],
    51: ["間有陽光", "Sunny Periods"],
    52: ["短暫陽光", "Sunny Intervals"],
    53: ["間有陽光幾陣驟雨", "Sunny Periods with A Few Showers"],
    54: ["短暫陽光有驟雨", "Sunny Intervals with Showers"],
    60: ["多雲", "Cloudy"],
    61: ["密雲", "Overcast"],
    62: ["微雨", "Light Rain"],
    63: ["雨", "Rain"],
    64: ["大雨", "Heavy Rain"],
    65: ["雷暴", "Thunderstorms"],
    70: ["天色良好", "Fine"],
    71: ["天色良好", "Fine"],
    72: ["天色良好", "Fine"],
    73: ["天色良好", "Fine"],
    74: ["天色良好", "Fine"],
    75: ["天色良好", "Fine"],
    76: ["大致多雲", "Mainly Cloudy"],
    77: ["天色大致良好", "Mainly Fine"],
    80: ["大風", "Windy"],
    81: ["乾燥", "Dry"],
    82: ["潮濕", "Humid"],
    83: ["霧", "Fog"],
    84: ["薄霧", "Mist"],
    85: ["煙霞", "Haze"],
    90: ["熱", "Hot"],
    91: ["暖", "Warm"],
    92: ["涼", "Cool"],
    93: ["冷", "Cold"]
  };

  var HKO_PLACES = { "香港天文台": true, "Hong Kong Observatory": true };
  var KIND_ORDER = { cyclone: 0, rain: 1, thunder: 2, tsunami: 3, landslip: 4, wind: 5, fire: 6, hot: 7, cold: 8, alert: 9 };
  var STATION_ORDER = [
    ["General Stations", "Central/Western"],
    ["General Stations", "Southern"],
    ["General Stations", "Eastern"],
    ["General Stations", "Kwun Tong"],
    ["General Stations", "Sham Shui Po"],
    ["General Stations", "Kwai Chung"],
    ["General Stations", "Tsuen Wan"],
    ["General Stations", "Tseung Kwan O"],
    ["General Stations", "Yuen Long"],
    ["General Stations", "Tuen Mun"],
    ["General Stations", "Tung Chung"],
    ["General Stations", "Tai Po"],
    ["General Stations", "Sha Tin"],
    ["General Stations", "North"],
    ["General Stations", "Tap Mun"],
    ["Roadside Stations", "Causeway Bay"],
    ["Roadside Stations", "Central"],
    ["Roadside Stations", "Mong Kok"]
  ];
  var NAMES_ZH = {
    "Central/Western": "中西區", Southern: "南區", Eastern: "東區", "Kwun Tong": "觀塘",
    "Sham Shui Po": "深水埗", "Kwai Chung": "葵涌", "Tsuen Wan": "荃灣", "Tseung Kwan O": "將軍澳",
    "Yuen Long": "元朗", "Tuen Mun": "屯門", "Tung Chung": "東涌", "Tai Po": "大埔", "Sha Tin": "沙田",
    North: "北區", "Tap Mun": "塔門", "Causeway Bay": "銅鑼灣", Central: "中環", "Mong Kok": "旺角"
  };
  var IDS = {
    "Central/Western": "central-western", Southern: "southern", Eastern: "eastern", "Kwun Tong": "kwun-tong",
    "Sham Shui Po": "sham-shui-po", "Kwai Chung": "kwai-chung", "Tsuen Wan": "tsuen-wan",
    "Tseung Kwan O": "tseung-kwan-o", "Yuen Long": "yuen-long", "Tuen Mun": "tuen-mun",
    "Tung Chung": "tung-chung", "Tai Po": "tai-po", "Sha Tin": "sha-tin", North: "north",
    "Tap Mun": "tap-mun", "Causeway Bay": "causeway-bay", Central: "central", "Mong Kok": "mong-kok"
  };
  var MISSING = { "": true, "-": true, "—": true, "–": true, "*": true, "N/A": true, NA: true, "n.a.": true, "N.A.": true };

  function asDict(value) { return value && typeof value === "object" && !Array.isArray(value) ? value : {}; }
  function asList(value) { return Array.isArray(value) ? value : []; }
  function asText(value) {
    if (value == null) return "";
    if (Array.isArray(value)) return value.map(asText).filter(Boolean).join(" ").trim();
    if (typeof value === "string") return value.trim();
    return "";
  }
  function asNumber(value) {
    if (typeof value === "boolean" || value == null) return null;
    if (typeof value === "number" && !isNaN(value)) return value;
    if (typeof value === "string" && value.trim()) {
      var n = Number(value);
      return isNaN(n) ? null : n;
    }
    return null;
  }
  function whole(value) {
    if (typeof value === "number" && Math.floor(value) === value) return value;
    return value;
  }
  function grab(parts, type) {
    var found = parts.filter(function (part) { return part.type === type; })[0];
    return found ? found.value : "";
  }
  function isoHkt(date) {
    var parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Hong_Kong",
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      hourCycle: "h23"
    }).formatToParts(date);
    var hour = grab(parts, "hour");
    if (hour === "24") hour = "00";
    return grab(parts, "year") + "-" + grab(parts, "month") + "-" + grab(parts, "day") + "T" + hour + ":" + grab(parts, "minute") + ":" + grab(parts, "second") + "+08:00";
  }
  function nowIso() { return isoHkt(new Date()); }
  function iconPair(number) {
    var key = whole(asNumber(number));
    var pair = ICONS[key];
    return pair ? { n: key, zh: pair[0], en: pair[1] } : { n: key, zh: null, en: null };
  }
  function endpoint(dataType, lang) {
    var url = new URL(HKO);
    url.searchParams.set("dataType", dataType);
    url.searchParams.set("lang", lang);
    url.searchParams.set("_", String(Date.now()));
    return url.toString();
  }
  function getJson(url) {
    var opts = { cache: "no-store" };
    if (typeof AbortSignal !== "undefined" && AbortSignal.timeout) opts.signal = AbortSignal.timeout(20000);
    return fetch(url, opts).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    });
  }
  function pairRows(tcRows, enRows, valueKey) {
    tcRows = asList(tcRows);
    enRows = asList(enRows);
    var rows = [];
    var count = Math.max(tcRows.length, enRows.length);
    for (var i = 0; i < count; i += 1) {
      var tc = tcRows[i] && typeof tcRows[i] === "object" ? tcRows[i] : {};
      var en = enRows[i] && typeof enRows[i] === "object" ? enRows[i] : {};
      var value = asNumber(tc[valueKey]);
      if (value == null) value = asNumber(en[valueKey]);
      var placeZh = asText(tc.place) || asText(en.place);
      var placeEn = asText(en.place) || placeZh;
      if (value == null && !placeZh) continue;
      rows.push({ placeZh: placeZh, placeEn: placeEn, value: value, unit: asText(tc.unit) || asText(en.unit) });
    }
    return rows;
  }
  function pickHko(rows) {
    for (var i = 0; i < rows.length; i += 1) {
      if (HKO_PLACES[rows[i].placeZh] || HKO_PLACES[rows[i].placeEn]) return rows[i];
    }
    return rows[0] || null;
  }
  function warningKind(key, code) {
    var blob = (key + " " + code).toUpperCase();
    var token = (code || "").toUpperCase();
    if (blob.indexOf("WTCSGNL") !== -1 || token.indexOf("TC") === 0) return "cyclone";
    if (blob.indexOf("RAIN") !== -1) return "rain";
    if (blob.indexOf("FIRE") !== -1) return "fire";
    if (blob.indexOf("FNT") !== -1 || key.toUpperCase() === "WTS" || key.toUpperCase() === "WFNTSA" || token.indexOf("WTS") === 0) return "thunder";
    if (blob.indexOf("FROST") !== -1 || blob.indexOf("COLD") !== -1) return "cold";
    if (blob.indexOf("HOT") !== -1) return "hot";
    if (blob.indexOf("WMSGNL") !== -1 || blob.indexOf("MONSOON") !== -1) return "wind";
    if (blob.indexOf("WTMW") !== -1 || blob.indexOf("TSUNAMI") !== -1) return "tsunami";
    if (key.toUpperCase() === "WL" || key.toUpperCase() === "WLANDSLIP" || blob.indexOf("LAND") !== -1) return "landslip";
    return "alert";
  }
  function warningLevel(code) {
    var token = (code || "").toUpperCase();
    if (token === "WRAINB" || token === "TC10" || token === "TC9" || token.indexOf("TC8") === 0) return "serious";
    if (token === "WRAINR" || token === "WFIRER" || token === "TC3") return "high";
    if (token === "WRAINA" || token === "WFIREY" || token === "TC1") return "moderate";
    return "alert";
  }
  function iterWarnings(payload, visit) {
    if (Array.isArray(payload)) {
      payload.forEach(function (item) {
        if (item && typeof item === "object") visit(asText(item.key) || asText(item.code), item);
      });
      return;
    }
    if (!payload || typeof payload !== "object") return;
    if (payload.code || payload.name) {
      visit(asText(payload.code), payload);
      return;
    }
    Object.keys(payload).forEach(function (key) {
      if (payload[key] && typeof payload[key] === "object") visit(key, payload[key]);
    });
  }
  function buildWarnings(tcPayload, enPayload) {
    var english = {};
    iterWarnings(enPayload, function (key, item) { english[key] = item; });
    var warnings = [];
    iterWarnings(tcPayload, function (key, item) {
      var action = asText(item.actionCode).toUpperCase();
      if (action === "CANCEL" || action === "CANCELLED") return;
      var enItem = english[key] || {};
      var code = asText(item.code) || asText(enItem.code) || key;
      warnings.push({
        key: key,
        code: code,
        kind: warningKind(key, code),
        level: warningLevel(code),
        nameZh: asText(item.name) || code,
        nameEn: asText(enItem.name) || asText(item.name) || code,
        typeZh: asText(item.type),
        typeEn: asText(enItem.type),
        actionCode: action,
        issueTime: asText(item.issueTime) || null,
        updateTime: asText(item.updateTime) || null
      });
    });
    warnings.sort(function (a, b) {
      var diff = (KIND_ORDER[a.kind] == null ? 9 : KIND_ORDER[a.kind]) - (KIND_ORDER[b.kind] == null ? 9 : KIND_ORDER[b.kind]);
      if (diff) return diff;
      return a.nameZh < b.nameZh ? -1 : a.nameZh > b.nameZh ? 1 : 0;
    });
    return warnings;
  }
  function buildCurrent(tc, en) {
    tc = asDict(tc);
    en = asDict(en);
    var tcTemp = asDict(tc.temperature);
    var enTemp = asDict(en.temperature);
    var temperatures = pairRows(tcTemp.data, enTemp.data, "value");
    var chosen = pickHko(temperatures);
    var values = temperatures.map(function (row) { return row.value; }).filter(function (value) { return typeof value === "number"; });
    var temperature = null;
    if (chosen && chosen.value != null) {
      temperature = {
        placeZh: chosen.placeZh,
        placeEn: chosen.placeEn,
        value: chosen.value,
        unit: chosen.unit || "C",
        time: asText(tcTemp.recordTime) || asText(enTemp.recordTime) || null,
        min: values.length ? Math.min.apply(null, values) : chosen.value,
        max: values.length ? Math.max.apply(null, values) : chosen.value
      };
    }
    var tcHum = asDict(tc.humidity);
    var enHum = asDict(en.humidity);
    var humidityChoice = pickHko(pairRows(tcHum.data, enHum.data, "value"));
    var humidity = null;
    if (humidityChoice && humidityChoice.value != null) {
      humidity = {
        placeZh: humidityChoice.placeZh,
        placeEn: humidityChoice.placeEn,
        value: humidityChoice.value,
        unit: "percent",
        time: asText(tcHum.recordTime) || asText(enHum.recordTime) || null
      };
    }
    var tcRain = asDict(tc.rainfall);
    var enRain = asDict(en.rainfall);
    var districts = pairRows(tcRain.data, enRain.data, "max");
    var rainfall = null;
    if (districts.length) {
      var numbers = districts.map(function (row) { return row.value; }).filter(function (value) { return typeof value === "number"; });
      var maximum = numbers.length ? Math.max.apply(null, numbers) : null;
      var leaders = [];
      if (maximum != null && maximum !== 0) {
        leaders = districts.filter(function (row) { return row.value === maximum; }).slice(0, 6).map(function (row) {
          return { placeZh: row.placeZh, placeEn: row.placeEn, value: row.value };
        });
      }
      rainfall = {
        startTime: asText(tcRain.startTime) || asText(enRain.startTime) || null,
        endTime: asText(tcRain.endTime) || asText(enRain.endTime) || null,
        unit: "mm",
        max: maximum,
        districtCount: districts.length,
        leaders: leaders
      };
    }
    var tcUv = asDict(tc.uvindex);
    var enUv = asDict(en.uvindex);
    var uvRowsTc = asList(tcUv.data);
    var uvRowsEn = asList(enUv.data);
    var uv = null;
    if (uvRowsTc.length || uvRowsEn.length) {
      var tcRow = uvRowsTc[0] && typeof uvRowsTc[0] === "object" ? uvRowsTc[0] : {};
      var enRow = uvRowsEn[0] && typeof uvRowsEn[0] === "object" ? uvRowsEn[0] : {};
      var uvValue = asNumber(tcRow.value);
      if (uvValue == null) uvValue = asNumber(enRow.value);
      if (uvValue != null) {
        uv = {
          placeZh: asText(tcRow.place) || asText(enRow.place),
          placeEn: asText(enRow.place) || asText(tcRow.place),
          value: uvValue,
          descZh: asText(tcRow.desc),
          descEn: asText(enRow.desc),
          recordDescZh: asText(tcUv.recordDesc),
          recordDescEn: asText(enUv.recordDesc)
        };
      }
    }
    var icons = Array.isArray(tc.icon) ? tc.icon : en.icon;
    var icon = iconPair(Array.isArray(icons) ? icons[0] : null);
    return {
      updateTime: asText(tc.updateTime) || asText(en.updateTime) || null,
      icon: icon.n,
      iconZh: icon.zh,
      iconEn: icon.en,
      temperature: temperature,
      humidity: humidity,
      rainfall: rainfall,
      uv: uv,
      messageZh: asText(tc.warningMessage),
      messageEn: asText(en.warningMessage),
      cycloneMessageZh: asText(tc.tcmessage),
      cycloneMessageEn: asText(en.tcmessage)
    };
  }
  function forecastDate(token) {
    var text = asText(token);
    return text.length === 8 && /^\d{8}$/.test(text) ? text.slice(0, 4) + "-" + text.slice(4, 6) + "-" + text.slice(6, 8) : text;
  }
  function buildForecast(tc, en) {
    tc = asDict(tc);
    en = asDict(en);
    var enByDate = {};
    asList(en.weatherForecast).forEach(function (item) {
      if (item && typeof item === "object") enByDate[forecastDate(item.forecastDate)] = item;
    });
    var days = [];
    asList(tc.weatherForecast).forEach(function (item) {
      if (!item || typeof item !== "object") return;
      var date = forecastDate(item.forecastDate);
      var other = enByDate[date] || {};
      var icon = iconPair(item.ForecastIcon != null ? item.ForecastIcon : other.ForecastIcon);
      var maxTemp = asNumber(asDict(item.forecastMaxtemp).value);
      var minTemp = asNumber(asDict(item.forecastMintemp).value);
      if (maxTemp == null) maxTemp = asNumber(asDict(other.forecastMaxtemp).value);
      if (minTemp == null) minTemp = asNumber(asDict(other.forecastMintemp).value);
      days.push({
        date: date,
        weekZh: asText(item.week),
        weekEn: asText(other.week),
        weatherZh: asText(item.forecastWeather),
        weatherEn: asText(other.forecastWeather),
        windZh: asText(item.forecastWind),
        windEn: asText(other.forecastWind),
        maxTemp: maxTemp,
        minTemp: minTemp,
        icon: icon.n,
        iconZh: icon.zh,
        iconEn: icon.en,
        psrZh: asText(item.PSR),
        psrEn: asText(other.PSR)
      });
    });
    if (!days.length) throw new Error("forecast has no days");
    return {
      updateTime: asText(tc.updateTime) || asText(en.updateTime) || null,
      generalSituationZh: asText(tc.generalSituation),
      generalSituationEn: asText(en.generalSituation),
      days: days
    };
  }
  function buildWeather(currentTc, currentEn, warnTc, warnEn, forecastTc, forecastEn, fetchedAt) {
    var current = buildCurrent(currentTc, currentEn);
    var forecast = buildForecast(forecastTc, forecastEn);
    if (!current.updateTime && !forecast.updateTime) throw new Error("weather response has no update time");
    return {
      schemaVersion: 1,
      provider: "Hong Kong Observatory",
      timezone: "Asia/Hong_Kong",
      fetchedAt: fetchedAt || nowIso(),
      live: true,
      sources: {
        current: endpoint("rhrread", "tc").replace(/&_=.*/, ""),
        warnings: endpoint("warnsum", "tc").replace(/&_=.*/, ""),
        forecast: endpoint("fnd", "tc").replace(/&_=.*/, "")
      },
      current: current,
      warnings: buildWarnings(warnTc, warnEn),
      forecast: forecast
    };
  }
  function fetchWeather() {
    return Promise.all([
      getJson(endpoint("rhrread", "tc")),
      getJson(endpoint("rhrread", "en")),
      getJson(endpoint("warnsum", "tc")),
      getJson(endpoint("warnsum", "en")),
      getJson(endpoint("fnd", "tc")),
      getJson(endpoint("fnd", "en"))
    ]).then(function (parts) {
      return buildWeather(parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], nowIso());
    });
  }

  function classify(raw) {
    if (raw == null) return { aqhi: null, value: null, band: null };
    var text = String(raw).trim();
    if (MISSING[text]) return { aqhi: null, value: null, band: null };
    if (text === "10+" || text === "10＋") return { aqhi: "10+", value: 11, band: "serious" };
    if (/^\d+$/.test(text)) {
      var number = Number(text);
      if (number >= 11) return { aqhi: "10+", value: 11, band: "serious" };
      if (number < 1) return { aqhi: null, value: null, band: null };
      var band = number <= 3 ? "low" : number <= 6 ? "moderate" : number === 7 ? "high" : "very_high";
      return { aqhi: String(number), value: number, band: band };
    }
    return { aqhi: null, value: null, band: null };
  }
  function stationType(raw) {
    var lowered = raw.toLowerCase();
    if (lowered.indexOf("roadside") !== -1) return "roadside";
    if (lowered.indexOf("general") !== -1) return "general";
    return "other";
  }
  function childText(node, name) {
    var nodes = node.getElementsByTagName(name);
    return nodes.length ? nodes[0].textContent.trim() : "";
  }
  function parseRfc822(text) {
    if (!text) return null;
    var date = new Date(text);
    return isNaN(date.getTime()) ? null : isoHkt(date);
  }
  function pickMax(readings) {
    var ranked = readings.filter(function (item) { return item.value != null; });
    if (!ranked.length) return null;
    var best = ranked[0];
    ranked.forEach(function (item) {
      if (item.value > best.value || (item.value === best.value && item.time > best.time)) best = item;
    });
    return { time: best.time, aqhi: best.aqhi, value: best.value, band: best.band };
  }
  function dailyMaxes(hours) {
    var byDate = {};
    hours.forEach(function (hour) {
      var date = hour.time.slice(0, 10);
      if (!byDate[date]) byDate[date] = [];
      byDate[date].push(hour);
    });
    return Object.keys(byDate).sort().map(function (date) {
      var best = pickMax(byDate[date]);
      return best ? { date: date, time: best.time, aqhi: best.aqhi, value: best.value, band: best.band } : { date: date, time: null, aqhi: null, value: null, band: null };
    });
  }
  function notesFor(hours, latest) {
    var notes = [];
    var numeric = hours.filter(function (hour) { return hour.value != null; });
    var highHours = numeric.filter(function (hour) { return hour.value >= 7; }).length;
    if (latest.value == null) notes.push({ zh: "最新一小時沒有讀數。", en: "The latest hour has no reading." });
    else if (hours.length >= 2) {
      var previous = hours[hours.length - 2];
      if (previous.value == null) notes.push({ zh: "上一小時沒有讀數。", en: "The previous hour has no reading." });
      else if (latest.value > previous.value) notes.push({ zh: "較上一小時上升（" + previous.aqhi + " → " + latest.aqhi + "）。", en: "Up from the previous hour (" + previous.aqhi + " → " + latest.aqhi + ")." });
      else if (latest.value < previous.value) notes.push({ zh: "較上一小時下跌（" + previous.aqhi + " → " + latest.aqhi + "）。", en: "Down from the previous hour (" + previous.aqhi + " → " + latest.aqhi + ")." });
      else notes.push({ zh: "與上一小時相同。", en: "Same as the previous hour." });
    }
    if (highHours === 0) notes.push({ zh: "過去 24 小時沒有高、甚高或嚴重讀數。", en: "No High, Very High, or Serious reading in the past 24 hours." });
    else if (highHours === 1) notes.push({ zh: "過去 24 小時有 1 小時處於高或以上。", en: "1 hour at High or above in the past 24 hours." });
    else notes.push({ zh: "過去 24 小時有 " + highHours + " 小時處於高或以上。", en: highHours + " hours at High or above in the past 24 hours." });
    return { notes: notes, highHours: highHours };
  }
  function buildAqhi(xml, fetchedAt) {
    var doc = new DOMParser().parseFromString(xml, "text/xml");
    if (!doc || doc.getElementsByTagName("parsererror").length || !doc.documentElement || doc.documentElement.localName !== "AQHI24HrReport") {
      throw new Error("not AQHI XML");
    }
    var rootNode = doc.documentElement;
    var grouped = {};
    var seen = [];
    Array.prototype.forEach.call(rootNode.getElementsByTagName("item"), function (item) {
      var name = childText(item, "StationName");
      var rawType = childText(item, "type");
      var when = parseRfc822(childText(item, "DateTime"));
      if (!name || !when) return;
      var key = rawType + "\n" + name;
      if (!grouped[key]) {
        grouped[key] = {};
        seen.push([rawType, name]);
      }
      var classified = classify(childText(item, "aqhi"));
      grouped[key][when] = { time: when, aqhi: classified.aqhi, value: classified.value, band: classified.band };
    });
    if (!seen.length) throw new Error("XML has no station readings");
    var orderIndex = {};
    STATION_ORDER.forEach(function (pair, index) { orderIndex[pair[0] + "\n" + pair[1]] = index; });
    seen.sort(function (a, b) {
      var ai = orderIndex[a[0] + "\n" + a[1]];
      var bi = orderIndex[b[0] + "\n" + b[1]];
      if (ai != null && bi != null) return ai - bi;
      if (ai != null) return -1;
      if (bi != null) return 1;
      return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : 1;
    });
    var used = {};
    var stations = seen.map(function (pair) {
      var key = pair[0] + "\n" + pair[1];
      var hours = Object.keys(grouped[key]).sort().map(function (time) { return grouped[key][time]; });
      var latest = hours[hours.length - 1];
      var noted = notesFor(hours, latest);
      var baseId = IDS[pair[1]] || pair[1].toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "station";
      var stationId = baseId;
      var suffix = 2;
      while (used[stationId]) {
        stationId = baseId + "-" + suffix;
        suffix += 1;
      }
      used[stationId] = true;
      return {
        id: stationId,
        nameEn: pair[1],
        nameZh: NAMES_ZH[pair[1]] || pair[1],
        type: stationType(pair[0]),
        typeRaw: pair[0],
        latest: { time: latest.time, aqhi: latest.aqhi, value: latest.value, band: latest.band },
        max24h: pickMax(hours),
        dailyMax: dailyMaxes(hours),
        highHours: noted.highHours,
        notes: noted.notes,
        hours: hours
      };
    });
    var reportTime = parseRfc822(childText(rootNode, "lastBuildDate"));
    if (!reportTime) {
      reportTime = stations.map(function (station) { return station.latest.time; }).sort().pop();
    }
    if (!reportTime) throw new Error("no report time");
    return {
      schemaVersion: 1,
      source: AQHI_URL,
      sourcePage: AQHI_PAGE,
      provider: childText(rootNode, "copyright") || "Environmental Protection Department",
      timezone: "Asia/Hong_Kong",
      reportTime: reportTime,
      fetchedAt: fetchedAt || nowIso(),
      live: true,
      title: childText(rootNode, "title") || "AQHI",
      stations: stations
    };
  }
  function fetchAqhi() {
    var url = new URL(AQHI_URL);
    url.searchParams.set("_", String(Date.now()));
    var opts = { cache: "no-store" };
    if (typeof AbortSignal !== "undefined" && AbortSignal.timeout) opts.signal = AbortSignal.timeout(20000);
    return fetch(url, opts).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.text();
    }).then(function (xml) { return buildAqhi(xml, nowIso()); });
  }

  root.HkUpstream = {
    fetchWeather: fetchWeather,
    fetchAqhi: fetchAqhi,
    buildWeather: buildWeather,
    buildAqhi: buildAqhi
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
