# 香港空氣質素健康指數走勢

過去 24 小時、各監測站的空氣質素健康指數。頁面是靜態的，讀本倉庫的 [`data/aqhi.json`](data/aqhi.json)。沒有帳戶，沒有密鑰，也沒有付費服務。

GitHub Actions 每小時向環境保護署的公開 XML 取數。數字或報告時間有變才把新的 JSON 推上 `main`。取數失敗就停手，上一份照舊留在網站上。GitHub Pages 由 `main` 分支的根目錄發布。

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

工作流程是 [Update AQHI](.github/workflows/update-aqhi.yml)。

- Cron：`20 * * * *`，每小時第 20 分。香港是 UTC+8，所以分鐘和香港時間一樣。環保署的 XML 通常在每小時約第 10 分更新，第 20 分再抓，比較容易抓到該小時的檔。
- GitHub 的排程不保證準時，有時會遲十幾分鐘。
- 連續 60 日沒有任何倉庫活動時，GitHub 會暫停排程。到 Actions 手動跑一次就會恢復。
- 讀到的指數和報告時間跟上一份一樣時，不會 commit。

本機重抓：

```bash
python3 scripts/fetch_aqhi.py
python3 scripts/test_fetch.py
```

只檢查、不寫檔：`python3 scripts/fetch_aqhi.py --check`。

## 頁面按鈕和 Run workflow

兩件事不一樣。

| | 頁面「立即更新 / Refresh」 | Actions「Run workflow」 |
| --- | --- | --- |
| 做什麼 | 重新下載本站已發布的 `data/aqhi.json`，重畫圖表，更新畫面上的時間 | 向環保署抓 XML，數字有變才 commit |
| 會不會打到環保署 | 不會 | 會 |
| 要不要權杖 | 不要。頁面沒有 token，也不能幫你啟動工作流程 | 用你自己的 GitHub 登入。只有有寫入權的人按得到 |

真的要更新上游數據：打開 [Update AQHI](https://github.com/bcmvl08/hk-aqhi/actions/workflows/update-aqhi.yml)，按 **Run workflow**，分支選 `main`。

## 資料

- 環境保護署 XML：<https://www.aqhi.gov.hk/epd/ddata/html/out/24aqhi_Eng.xml>
- data.gov.hk 資料集：<https://data.gov.hk/tc-data/dataset/hk-epd-airteam-past24hr-aqhi-of-individual-air-quality-monitoring-stations>
- 正式網站與健康建議：<https://www.aqhi.gov.hk/>

指數 1–3 低、4–6 中、7 高、8–10 甚高、10+ 嚴重。顏色沿用環保署網站。本頁不是醫療建議。

## English

Static Hong Kong AQHI trend for the past 24 hours at each monitoring station. The page reads [`data/aqhi.json`](data/aqhi.json) from this repository. No account, no secrets, no paid services.

GitHub Actions fetches the Environmental Protection Department’s public XML every hour and pushes to `main` only when the readings or the report time change. A failed fetch leaves the last good file in place. GitHub Pages publishes the root of `main`.

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

Workflow: [Update AQHI](.github/workflows/update-aqhi.yml).

- Cron `20 * * * *` (minute 20 of every hour). Hong Kong is UTC+8, so the minute matches Hong Kong time. The EPD file usually appears around minute 10, and minute 20 is late enough to catch it.
- GitHub may start the job later than the cron time.
- GitHub pauses scheduled workflows after 60 days without repository activity. One manual run turns them back on.
- Identical readings do not produce a commit.

Local commands:

```bash
python3 scripts/fetch_aqhi.py
python3 scripts/test_fetch.py
```

Check without writing: `python3 scripts/fetch_aqhi.py --check`.

### Page button vs Run workflow

| | Page button, 立即更新 / Refresh | Actions, Run workflow |
| --- | --- | --- |
| What it does | Reloads this site’s published `data/aqhi.json`, redraws the charts, and updates the times on the page | Fetches the EPD XML and commits only when the figures change |
| Contacts the EPD | No | Yes |
| Token | None. The page cannot start the workflow | Your own GitHub login. Only someone with write access can run it |

For a true upstream refresh, open [Update AQHI](https://github.com/bcmvl08/hk-aqhi/actions/workflows/update-aqhi.yml) and click **Run workflow** on `main`.

### Data

- EPD XML: <https://www.aqhi.gov.hk/epd/ddata/html/out/24aqhi_Eng.xml>
- data.gov.hk dataset: <https://data.gov.hk/en-data/dataset/hk-epd-airteam-past24hr-aqhi-of-individual-air-quality-monitoring-stations>
- Official site and health advice: <https://www.aqhi.gov.hk/>

Bands: 1–3 Low, 4–6 Moderate, 7 High, 8–10 Very High, 10+ Serious. Colours follow the EPD site. This page is not medical advice.
