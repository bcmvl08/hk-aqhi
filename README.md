# 香港空氣質素與天氣

同一個靜態頁：環境保護署過去 24 小時的空氣質素健康指數，加上香港天文台的現況、生效警告和九天預報。頁面讀本倉庫的 [`data/aqhi.json`](data/aqhi.json) 和 [`data/weather.json`](data/weather.json)。沒有帳戶，沒有密鑰，也沒有付費服務。

GitHub Actions 每小時向兩個公開來源取數。空氣質素或天氣有變才把新的 JSON 推上 `main`。任一次取數失敗就停手，不 commit，上一份照舊留在網站上。GitHub Pages 由 `main` 分支的根目錄發布。

這不是官方警報工具。排程大約每小時一次，GitHub 也可能遲到，警告會遲過天文台網站。

[English notes](#english)

## 啟用 GitHub Pages

1. 打開 **Settings → Pages**。
2. **Build and deployment** 選 **Deploy from a branch**。
3. Branch 選 `main`，資料夾選 `/ (root)`，然後儲存。
4. 網站會在 [https://bcmvl08.github.io/hk-aqhi/](https://bcmvl08.github.io/hk-aqhi/)。第一次啟用可能要等一兩分鐘。

倉庫保持公開。不要加密碼或 Actions secret。

## 讓 Actions 可以寫入

排程和 **Run workflow** 都要把更新推回 `main`。

1. **Settings → Actions → General**。
2. **Workflow permissions** 選 **Read and write permissions**。
3. 儲存。

如果另有 ruleset 擋住機器人推 `main`，要允許 `github-actions[bot]` 推送。頁面來源維持「Deploy from a branch」，不用改成 GitHub Actions 部署。

## 排程

工作流程是 [Update AQHI and weather](.github/workflows/update-aqhi.yml)。

- Cron：`20 * * * *`，每小時第 20 分。香港是 UTC+8，所以分鐘和香港時間一樣。環保署的 XML 通常在每小時約第 10 分更新，第 20 分再抓，比較容易抓到該小時的檔。天文台的現況更新更密，但本站跟著同一個小時排程走。
- GitHub 的排程不保證準時，有時會遲十幾分鐘。警告因此可能遲過天文台。
- 連續 60 日沒有任何倉庫活動時，GitHub 會暫停排程。到 Actions 手動跑一次就會恢復。
- 空氣質素和天氣都跟上一份一樣時，不會 commit。只有其中一份有變，也會 commit。

本機重抓：

```bash
python3 scripts/fetch_aqhi.py
python3 scripts/fetch_weather.py
python3 scripts/test_fetch.py
python3 scripts/test_weather.py
```

只檢查、不寫檔：`python3 scripts/fetch_aqhi.py --check` 和 `python3 scripts/fetch_weather.py --check`。

## 頁面按鈕和 Run workflow

兩件事一起用。

| | 頁面「立即更新 / Refresh」 | Actions「Run workflow」 |
| --- | --- | --- |
| 做什麼 | 瀏覽器直接向天文台讀現況、警告和九天預報，並嘗試讀環保署 XML。失敗就用本站已發布的 JSON，狀態列會寫明。大約每 5 分鐘再試，分頁在背景時暫停 | 向環保署和天文台抓數，有變才 commit，留給頁面當備用 |
| 會不會打到官方 | 會。天文台允許跨站；環保署 XML 只允許 `aqhi.gov.hk`，瀏覽器通常會被拒 | 會。Actions 的伺服器不受那個跨站限制 |
| 要不要權杖 | 不要。頁面沒有 token，也不能幫你啟動工作流程 | 用你自己的 GitHub 登入。只有有寫入權的人按得到 |

排程仍然每小時更新已發布的 JSON。打開 [Update AQHI and weather](https://github.com/bcmvl08/hk-aqhi/actions/workflows/update-aqhi.yml)，按 **Run workflow**，分支選 `main`，可以立刻重抓備用檔。

## 資料

- 環境保護署 XML：<https://www.aqhi.gov.hk/epd/ddata/html/out/24aqhi_Eng.xml>
- 空氣質素資料集：<https://data.gov.hk/tc-data/dataset/hk-epd-airteam-past24hr-aqhi-of-individual-air-quality-monitoring-stations>
- 天文台現況：<https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc>
- 天文台警告一覽（空白即沒有生效警告）：<https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=tc>
- 天文台九天預報：<https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=tc>
- 正式網站：<https://www.aqhi.gov.hk/> 、<https://www.hko.gov.hk/>

指數 1–3 低、4–6 中、7 高、8–10 甚高、10+ 嚴重。顏色沿用環保署網站。本頁不是醫療建議。

## English

One static page: the Environmental Protection Department’s past-24-hour Air Quality Health Index, plus the Hong Kong Observatory’s current weather, warnings in force, and 9-day forecast. The page reads [`data/aqhi.json`](data/aqhi.json) and [`data/weather.json`](data/weather.json). No account, no secrets, no paid services.

GitHub Actions fetches both public sources every hour and pushes to `main` only when AQHI or weather changed. If either fetch fails, the job stops without a commit and the last good files stay in place. GitHub Pages publishes the root of `main`.

This is not an official alert tool. The schedule is about hourly, and GitHub may start it late, so warnings can lag the Observatory.

### GitHub Pages

1. **Settings → Pages**.
2. **Deploy from a branch**.
3. Branch `main`, folder `/ (root)`.
4. The site is [https://bcmvl08.github.io/hk-aqhi/](https://bcmvl08.github.io/hk-aqhi/).

Keep the repository public. Do not add a password or an Actions secret.

### Actions write permission

Scheduled runs and **Run workflow** both push the JSON back to `main`.

1. **Settings → Actions → General**.
2. **Workflow permissions → Read and write permissions**.
3. Save.

If a ruleset blocks the bot, allow `github-actions[bot]` to push. Leave Pages on “Deploy from a branch”.

### Schedule

Workflow: [Update AQHI and weather](.github/workflows/update-aqhi.yml).

- Cron `20 * * * *` (minute 20 of every hour). Hong Kong is UTC+8, so the minute matches Hong Kong time. The EPD file usually appears around minute 10, and minute 20 is late enough to catch it. Observatory observations update more often; this site still follows the same hourly job.
- GitHub may start the job later than the cron time, so warnings can lag the Observatory.
- GitHub pauses scheduled workflows after 60 days without repository activity. One manual run turns them back on.
- A commit happens when either file changed. Identical AQHI and weather produce no commit.

Local commands:

```bash
python3 scripts/fetch_aqhi.py
python3 scripts/fetch_weather.py
python3 scripts/test_fetch.py
python3 scripts/test_weather.py
```

Check without writing: `python3 scripts/fetch_aqhi.py --check` and `python3 scripts/fetch_weather.py --check`.

### Page button vs Run workflow

| | Page button, 立即更新 / Refresh | Actions, Run workflow |
| --- | --- | --- |
| What it does | The browser fetches Observatory current weather, warnings, and the 9-day forecast, and tries the EPD XML. On failure it uses the published JSON and says so. It tries again about every 5 minutes, and pauses while the tab is hidden | Fetches the EPD and the Observatory, and commits only when either file changed, which leaves a cache for the page |
| Contacts the official sources | Yes. Observatory feeds allow other sites. The EPD XML allows only `aqhi.gov.hk`, so a browser on this site is usually blocked | Yes. The Actions runner is not limited by that browser rule |
| Token | None. The page cannot start the workflow | Your own GitHub login. Only someone with write access can run it |

The hourly job still refreshes the published JSON. Open [Update AQHI and weather](https://github.com/bcmvl08/hk-aqhi/actions/workflows/update-aqhi.yml) and click **Run workflow** on `main` to refresh that cache immediately.

### Data

- EPD XML: <https://www.aqhi.gov.hk/epd/ddata/html/out/24aqhi_Eng.xml>
- AQHI dataset: <https://data.gov.hk/en-data/dataset/hk-epd-airteam-past24hr-aqhi-of-individual-air-quality-monitoring-stations>
- Observatory current weather: <https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=en>
- Observatory warning summary (an empty object means nothing is in force): <https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=en>
- Observatory 9-day forecast: <https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=fnd&lang=en>
- Official sites: <https://www.aqhi.gov.hk/> and <https://www.hko.gov.hk/>

Bands: 1–3 Low, 4–6 Moderate, 7 High, 8–10 Very High, 10+ Serious. Colours follow the EPD site. This page is not medical advice.
