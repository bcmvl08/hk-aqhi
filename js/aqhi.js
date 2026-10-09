/* Draw the static AQHI page from data/aqhi.json on this origin.
   The refresh button reloads that file. It does not call GitHub or the EPD. */

(function () {
  "use strict";

  var BANDS = [
    { id: "low", zh: "低", en: "Low" },
    { id: "moderate", zh: "中", en: "Moderate" },
    { id: "high", zh: "高", en: "High" },
    { id: "very_high", zh: "甚高", en: "Very High" },
    { id: "serious", zh: "嚴重", en: "Serious" }
  ];

  var TYPE = {
    general: { zh: "一般", en: "General" },
    roadside: { zh: "路邊", en: "Roadside" },
    other: { zh: "其他", en: "Other" }
  };

  var state = {
    data: null,
    selectedId: null,
    filter: "all",
    loading: false
  };

  var SVG_NS = "http://www.w3.org/2000/svg";

  function $(id) {
    return document.getElementById(id);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function svgEl(tag, attrs) {
    var node = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        node.setAttribute(key, attrs[key]);
      });
    }
    return node;
  }

  function bandClass(band) {
    return band ? band.replace("_", "-") : "missing";
  }

  function bandLabel(band) {
    for (var i = 0; i < BANDS.length; i += 1) {
      if (BANDS[i].id === band) return BANDS[i];
    }
    return null;
  }

  function formatHKT(iso) {
    if (!iso) return "—";
    var date = new Date(iso);
    if (isNaN(date.getTime())) return "—";
    var parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Hong_Kong",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23"
    }).formatToParts(date);
    function grab(type) {
      var found = parts.find(function (part) { return part.type === type; });
      return found ? found.value : "";
    }
    return grab("year") + "-" + grab("month") + "-" + grab("day") + " " + grab("hour") + ":" + grab("minute");
  }

  function hourText(iso) {
    var full = formatHKT(iso);
    return full === "—" ? "—" : full.slice(11, 16);
  }

  function dayText(dateStr) {
    if (!dateStr || dateStr.length < 10) return "—";
    var month = Number(dateStr.slice(5, 7));
    var day = Number(dateStr.slice(8, 10));
    return month + "月" + day + "日";
  }

  function dayTextEn(dateStr) {
    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    if (!dateStr || dateStr.length < 10) return "";
    var month = Number(dateStr.slice(5, 7));
    var day = Number(dateStr.slice(8, 10));
    return day + " " + months[month - 1];
  }

  function setTime(id, iso) {
    var node = $(id);
    node.textContent = formatHKT(iso);
    if (iso) node.setAttribute("datetime", iso);
    else node.removeAttribute("datetime");
  }

  function setStatus(kind, text) {
    var node = $("status");
    node.dataset.state = kind || "";
    node.textContent = text || "";
  }

  function rank(station) {
    if (!station.latest || station.latest.value == null) return -1;
    return station.latest.value;
  }

  function latestObservation(data) {
    var best = null;
    data.stations.forEach(function (station) {
      var time = station.latest && station.latest.time;
      if (time && (!best || time > best)) best = time;
    });
    return best || data.reportTime || null;
  }

  function applyData(data) {
    state.data = data;
    var ids = data.stations.map(function (station) { return station.id; });
    if (!state.selectedId || ids.indexOf(state.selectedId) === -1) {
      var best = data.stations[0] || null;
      data.stations.forEach(function (station) {
        if (best && rank(station) > rank(best)) best = station;
      });
      state.selectedId = best ? best.id : null;
    }
    render(data);
  }

  function dataUrl() {
    var url = new URL("data/aqhi.json", document.baseURI);
    url.searchParams.set("t", String(Date.now()));
    return url;
  }

  function fetchData() {
    return fetch(dataUrl(), { cache: "no-store" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    }).then(function (data) {
      if (!data || !Array.isArray(data.stations)) throw new Error("bad json");
      return data;
    });
  }

  function refresh() {
    if (state.loading) return;
    state.loading = true;
    var button = $("refresh");
    var previous = state.data && state.data.reportTime;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    setStatus("loading", "更新中… Refreshing…");
    fetchData().then(function (data) {
      var hadData = !!state.data;
      applyData(data);
      if (!hadData) {
        setStatus("", "");
      } else if (previous && previous === data.reportTime) {
        setStatus("ok", "已重新載入。報告時間與剛才相同。 Reloaded. The report time is unchanged.");
      } else {
        setStatus("ok", "已重新載入本站數據。 Reloaded the published data.");
      }
    }).catch(function () {
      if (state.data) {
        setStatus("error", "讀取失敗，仍顯示上一次成功的數據。 Could not reload. Showing the last successful copy.");
      } else {
        setStatus("error", "讀取失敗。請再按「立即更新」。 Could not load data/aqhi.json. Press Refresh to try again.");
        var mount = $("summary-mount");
        mount.replaceChildren();
        mount.appendChild(el(
          "p",
          "summary-loading",
          "讀取失敗。請按「立即更新」再試。 Could not load the published data."
        ));
      }
    }).finally(function () {
      state.loading = false;
      button.disabled = false;
      button.removeAttribute("aria-busy");
    });
  }

  function badge(aqhi, band, large) {
    var node = el("span", "badge badge-" + bandClass(band) + (large ? " badge-lg" : ""), aqhi || "—");
    return node;
  }

  function sparkline(hours) {
    var svg = svgEl("svg", {
      viewBox: "0 0 120 36",
      class: "spark",
      "aria-hidden": "true"
    });
    var count = Math.max(hours.length, 1);
    hours.forEach(function (hour, index) {
      var slot = 120 / count;
      var value = hour.value == null ? 0 : hour.value;
      var height = hour.value == null ? 2 : Math.max((value / 11) * 32, 1.5);
      svg.appendChild(svgEl("rect", {
        x: (index * slot + 0.35).toFixed(2),
        y: (34 - height).toFixed(2),
        width: Math.max(slot - 0.7, 0.4).toFixed(2),
        height: height.toFixed(2),
        class: "fill-" + bandClass(hour.band)
      }));
    });
    return svg;
  }

  function renderSummary(data) {
    var mount = $("summary-mount");
    mount.replaceChildren();
    var stations = data.stations;
    var counts = {};
    BANDS.forEach(function (band) { counts[band.id] = 0; });
    var missing = 0;
    stations.forEach(function (station) {
      var band = station.latest && station.latest.band;
      if (band && counts[band] != null) counts[band] += 1;
      else missing += 1;
    });

    var bestValue = -1;
    stations.forEach(function (station) {
      if (rank(station) > bestValue) bestValue = rank(station);
    });
    var leaders = stations.filter(function (station) { return rank(station) === bestValue && bestValue >= 0; });
    var leader = leaders[0];
    var leaderBand = leader && leader.latest ? leader.latest.band : null;
    var leaderLabel = bandLabel(leaderBand);

    var hero = el("div", "hero");
    var figure = el("div", "hero-figure");
    var label = el("p", "rate-label");
    label.appendChild(document.createTextNode("現時最高 "));
    label.appendChild(el("span", "en", "Current high"));
    figure.appendChild(label);
    var heroBadge = badge(leader ? leader.latest.aqhi : "—", leaderBand, true);
    heroBadge.classList.add("rate-num");
    figure.appendChild(heroBadge);
    var bandLine = el("p", "rate-band");
    if (leader && leaderLabel) {
      bandLine.appendChild(document.createTextNode(leaderLabel.zh + " " + leaderLabel.en));
    } else {
      bandLine.textContent = "沒有讀數 No reading";
    }
    figure.appendChild(bandLine);
    hero.appendChild(figure);

    var copy = el("div");
    var lede = el("p", "lede");
    if (leaders.length) {
      var shown = leaders.slice(0, 3).map(function (station) {
        return station.nameZh;
      }).join("、");
      var extra = leaders.length > 3 ? "等 " + leaders.length + " 個站" : "";
      lede.textContent = stations.length + " 個監測站。現時最高 "
        + leader.latest.aqhi + "（" + leaderLabel.zh + " " + leaderLabel.en + "），"
        + (extra ? "包括" + shown + extra + "。" : "是" + shown + "。");
    } else {
      lede.textContent = stations.length + " 個監測站。現時沒有讀數。";
    }
    copy.appendChild(lede);

    var bar = el("div", "band-bar");
    bar.setAttribute("role", "img");
    var barLabel = BANDS.map(function (band) {
      return band.zh + " " + counts[band.id];
    }).join("，");
    bar.setAttribute("aria-label", "各站現時級別 " + barLabel);
    stations.forEach(function (station) {
      var piece = el("span", "seg-" + bandClass(station.latest && station.latest.band));
      var aqhi = station.latest && station.latest.aqhi ? station.latest.aqhi : "—";
      piece.title = station.nameZh + " " + aqhi;
      bar.appendChild(piece);
    });
    copy.appendChild(bar);

    var key = el("ul", "band-key");
    BANDS.forEach(function (band) {
      var item = el("li");
      item.appendChild(el("i", "swatch-" + bandClass(band.id)));
      item.appendChild(document.createTextNode(band.zh + " " + band.en + " " + counts[band.id]));
      key.appendChild(item);
    });
    if (missing) {
      key.appendChild(el("li", null, "沒有讀數 " + missing));
    }
    copy.appendChild(key);
    hero.appendChild(copy);
    mount.appendChild(hero);

    var stats = el("ul", "stats");
    BANDS.forEach(function (band) {
      var item = el("li");
      item.appendChild(el("span", "n", String(counts[band.id])));
      var caption = el("span", "l");
      caption.appendChild(document.createTextNode(band.zh + " "));
      caption.appendChild(el("span", "en", band.en));
      item.appendChild(caption);
      stats.appendChild(item);
    });
    mount.appendChild(stats);
  }

  function stationVisible(station) {
    return state.filter === "all" || station.type === state.filter;
  }

  function renderStations(data) {
    var grid = $("station-grid");
    grid.replaceChildren();
    var shown = 0;
    data.stations.forEach(function (station) {
      if (!stationVisible(station)) return;
      shown += 1;
      var typeInfo = TYPE[station.type] || TYPE.other;
      var latest = station.latest || {};
      var max24 = station.max24h;
      var today = station.dailyMax && station.dailyMax.length
        ? station.dailyMax[station.dailyMax.length - 1]
        : null;
      var label = bandLabel(latest.band);
      var card = el("button", "station-card");
      card.type = "button";
      card.dataset.station = station.id;
      card.setAttribute("aria-pressed", station.id === state.selectedId ? "true" : "false");

      var top = el("div", "card-top");
      var names = el("div");
      names.appendChild(el("div", "card-name", station.nameZh));
      names.appendChild(el("div", "card-en", station.nameEn));
      names.appendChild(el("div", "card-type", typeInfo.zh + " " + typeInfo.en));
      top.appendChild(names);
      top.appendChild(badge(latest.aqhi, latest.band, true));
      card.appendChild(top);

      card.appendChild(el(
        "div",
        "card-meta",
        (label ? label.zh + " " + label.en : "沒有讀數 No reading") + " · " + hourText(latest.time)
      ));
      var todayAqhi = today && today.aqhi ? today.aqhi : "—";
      var maxAqhi = max24 && max24.aqhi ? max24.aqhi : "—";
      var todayLabel = today ? dayText(today.date) + "最高 " + todayAqhi : "—";
      card.appendChild(el(
        "div",
        "card-meta",
        todayLabel + " · 24 小時最高 " + maxAqhi
      ));
      card.appendChild(sparkline(station.hours || []));
      (station.notes || []).forEach(function (note) {
        var line = el("div", "card-note");
        line.appendChild(el("span", "note-zh", note.zh));
        line.appendChild(el("span", "note-en", note.en));
        card.appendChild(line);
      });
      grid.appendChild(card);
    });
    $("station-empty").hidden = shown !== 0;

    [["all", data.stations.length], ["general", 0], ["roadside", 0]].forEach(function (pair) {
      var count = pair[0] === "all"
        ? pair[1]
        : data.stations.filter(function (station) { return station.type === pair[0]; }).length;
      var node = document.querySelector('[data-count="' + pair[0] + '"]');
      if (node) node.textContent = " " + count;
    });
  }

  function renderSelect(data) {
    var select = $("station-select");
    var current = state.selectedId;
    select.replaceChildren();
    data.stations.forEach(function (station) {
      var option = el("option", null, station.nameZh + " " + station.nameEn);
      option.value = station.id;
      select.appendChild(option);
    });
    if (current) select.value = current;
  }

  function renderChart(data) {
    var station = data.stations.find(function (item) { return item.id === state.selectedId; })
      || data.stations[0];
    var panel = $("chart-panel");
    var side = $("chart-side");
    var tableBody = $("hour-body");
    panel.replaceChildren();
    side.replaceChildren();
    tableBody.replaceChildren();
    if (!station) return;

    var hours = station.hours || [];
    panel.appendChild(buildChart(station, hours));

    var latest = station.latest || {};
    var label = bandLabel(latest.band);
    var typeInfo = TYPE[station.type] || TYPE.other;
    side.appendChild(el("h3", null, station.nameZh));
    side.appendChild(el("p", "muted", station.nameEn + " · " + typeInfo.zh + " " + typeInfo.en));
    var current = el("p");
    current.appendChild(document.createTextNode("最新 "));
    current.appendChild(badge(latest.aqhi, latest.band, false));
    current.appendChild(document.createTextNode(
      " " + (label ? label.zh + " " + label.en : "沒有讀數") + " · " + formatHKT(latest.time)
    ));
    side.appendChild(current);
    (station.dailyMax || []).forEach(function (day) {
      var line = el("p");
      line.appendChild(document.createTextNode(dayText(day.date) + " " + dayTextEn(day.date) + " 最高 "));
      line.appendChild(badge(day.aqhi, day.band, false));
      if (day.time) line.appendChild(document.createTextNode(" · " + hourText(day.time)));
      side.appendChild(line);
    });
    if (station.max24h) {
      var maxLine = el("p");
      maxLine.appendChild(document.createTextNode("24 小時最高 "));
      maxLine.appendChild(badge(station.max24h.aqhi, station.max24h.band, false));
      maxLine.appendChild(document.createTextNode(" · " + formatHKT(station.max24h.time)));
      side.appendChild(maxLine);
    }
    (station.notes || []).forEach(function (note) {
      var noteNode = el("p");
      noteNode.appendChild(el("span", "note-zh", note.zh));
      noteNode.appendChild(el("span", "note-en", note.en));
      side.appendChild(noteNode);
    });

    hours.forEach(function (hour) {
      var row = el("tr");
      row.appendChild(el("td", null, formatHKT(hour.time)));
      var valueCell = el("td");
      valueCell.appendChild(badge(hour.aqhi, hour.band, false));
      row.appendChild(valueCell);
      var band = bandLabel(hour.band);
      row.appendChild(el("td", null, band ? band.zh + " " + band.en : "—"));
      tableBody.appendChild(row);
    });
  }

  function buildChart(station, hours) {
    var width = 760;
    var height = 320;
    var left = 46;
    var right = 12;
    var top = 16;
    var bottom = 58;
    var plotW = width - left - right;
    var plotH = height - top - bottom;
    var count = Math.max(hours.length, 1);
    var svg = svgEl("svg", {
      viewBox: "0 0 " + width + " " + height,
      role: "img"
    });
    var latest = station.latest && station.latest.aqhi ? station.latest.aqhi : "—";
    var maxAqhi = station.max24h && station.max24h.aqhi ? station.max24h.aqhi : "—";
    svg.setAttribute(
      "aria-label",
      station.nameZh + " " + station.nameEn + " 過去 24 小時。最新 " + latest + "，最高 " + maxAqhi + "。"
    );

    [1, 3, 6, 7, 10, 11].forEach(function (tick) {
      var y = top + plotH - (tick / 11) * plotH;
      svg.appendChild(svgEl("line", {
        x1: left,
        x2: width - right,
        y1: y.toFixed(1),
        y2: y.toFixed(1),
        stroke: "#e3dacb",
        "stroke-width": "1"
      }));
      var text = svgEl("text", {
        x: left - 8,
        y: (y + 4).toFixed(1),
        "text-anchor": "end",
        fill: "#5f584e",
        "font-size": "12"
      });
      text.textContent = tick === 11 ? "10+" : String(tick);
      svg.appendChild(text);
    });

    hours.forEach(function (hour, index) {
      var slot = plotW / count;
      var barW = Math.max(slot - 3, 1);
      var x = left + index * slot + (slot - barW) / 2;
      var value = hour.value == null ? 0 : hour.value;
      var barH = hour.value == null ? 3 : Math.max((value / 11) * plotH, 2);
      var y = top + plotH - barH;
      var rect = svgEl("rect", {
        x: x.toFixed(2),
        y: y.toFixed(2),
        width: barW.toFixed(2),
        height: barH.toFixed(2),
        class: "fill-" + bandClass(hour.band)
      });
      var title = svgEl("title");
      var band = bandLabel(hour.band);
      title.textContent = formatHKT(hour.time) + "  " + (hour.aqhi || "—")
        + (band ? " " + band.zh + " " + band.en : "");
      rect.appendChild(title);
      svg.appendChild(rect);

      var showLabel = index === 0 || index === hours.length - 1 || index % 3 === 0;
      if (showLabel) {
        var label = svgEl("text", {
          x: (left + index * slot + slot / 2).toFixed(2),
          y: top + plotH + 18,
          "text-anchor": "middle",
          fill: "#5f584e",
          "font-size": "11"
        });
        var stamp = hourText(hour.time);
        if (index === 0 || stamp === "00:00") {
          label.textContent = dayText(hour.time.slice(0, 10)) + " " + stamp;
        } else {
          label.textContent = stamp;
        }
        svg.appendChild(label);
      }
    });
    return svg;
  }

  function renderDaily(data) {
    var head = $("daily-head");
    var body = $("daily-body");
    head.replaceChildren();
    body.replaceChildren();
    var dates = [];
    data.stations.forEach(function (station) {
      (station.dailyMax || []).forEach(function (day) {
        if (dates.indexOf(day.date) === -1) dates.push(day.date);
      });
    });
    dates.sort();

    var headRow = el("tr");
    headRow.appendChild(el("th", null, "監測站 Station"));
    dates.forEach(function (date) {
      var cell = el("th");
      cell.appendChild(document.createTextNode(dayText(date) + " "));
      cell.appendChild(el("span", "en", dayTextEn(date)));
      headRow.appendChild(cell);
    });
    headRow.appendChild(el("th", null, "24 小時最高 24h max"));
    headRow.appendChild(el("th", null, "備註 Notes"));
    head.appendChild(headRow);

    data.stations.forEach(function (station) {
      var row = el("tr");
      if (station.id === state.selectedId) row.className = "is-selected";
      var name = el("td");
      name.appendChild(el("span", "note-zh", station.nameZh));
      name.appendChild(el("span", "note-en", station.nameEn));
      row.appendChild(name);
      dates.forEach(function (date) {
        var day = (station.dailyMax || []).find(function (item) { return item.date === date; });
        var cell = el("td");
        if (!day) {
          cell.textContent = "—";
        } else {
          cell.appendChild(badge(day.aqhi, day.band, false));
          if (day.time) cell.appendChild(el("span", "cell-sub", hourText(day.time)));
        }
        row.appendChild(cell);
      });
      var maxCell = el("td");
      if (station.max24h) {
        maxCell.appendChild(badge(station.max24h.aqhi, station.max24h.band, false));
        maxCell.appendChild(el("span", "cell-sub", hourText(station.max24h.time)));
      } else {
        maxCell.textContent = "—";
      }
      row.appendChild(maxCell);
      var notes = el("td");
      (station.notes || []).forEach(function (note) {
        notes.appendChild(el("span", "note-zh", note.zh));
        notes.appendChild(el("span", "note-en", note.en));
      });
      row.appendChild(notes);
      body.appendChild(row);
    });
  }

  function render(data) {
    setTime("updated-time", latestObservation(data));
    setTime("report-time", data.reportTime);
    setTime("fetched-time", data.fetchedAt);
    renderSummary(data);
    renderStations(data);
    renderSelect(data);
    renderChart(data);
    renderDaily(data);
  }

  function bind() {
    $("refresh").addEventListener("click", refresh);
    document.querySelectorAll("[data-filter]").forEach(function (button) {
      button.addEventListener("click", function () {
        state.filter = button.getAttribute("data-filter");
        document.querySelectorAll("[data-filter]").forEach(function (other) {
          other.setAttribute("aria-pressed", other === button ? "true" : "false");
        });
        if (state.data) renderStations(state.data);
      });
    });
    $("station-grid").addEventListener("click", function (event) {
      var card = event.target.closest("[data-station]");
      if (!card || !state.data) return;
      state.selectedId = card.dataset.station;
      render(state.data);
      var trend = $("trend");
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        trend.scrollIntoView();
      } else {
        trend.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    $("station-select").addEventListener("change", function (event) {
      if (!state.data) return;
      state.selectedId = event.target.value;
      render(state.data);
    });

    var links = Array.prototype.slice.call(document.querySelectorAll(".section-nav a"));
    if ("IntersectionObserver" in window) {
      var observer = new IntersectionObserver(function (entries) {
        var visible = entries.filter(function (entry) { return entry.isIntersecting; });
        if (!visible.length) return;
        visible.sort(function (a, b) { return b.intersectionRatio - a.intersectionRatio; });
        var id = "#" + visible[0].target.id;
        links.forEach(function (link) {
          var on = link.getAttribute("href") === id;
          link.classList.toggle("is-active", on);
          if (on) link.setAttribute("aria-current", "location");
          else link.removeAttribute("aria-current");
        });
      }, { rootMargin: "-12% 0px -78% 0px", threshold: [0, 0.1, 0.25] });
      document.querySelectorAll("section[id]").forEach(function (section) {
        observer.observe(section);
      });
    }
  }

  bind();
  setStatus("loading", "正在讀取本站數據… Loading the published data…");
  refresh();
})();
