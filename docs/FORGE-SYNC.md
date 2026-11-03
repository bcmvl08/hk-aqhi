# GitHub vs GitLab (hk-aqhi)

Two remotes host the same product name with **different `main` tips** and **different production hosts**. Treat them as related forks until someone merges them on purpose.

## Where each site is built from

| Host | URL | Source remote | `main` tip (verified 2026-11-03) | Role |
| --- | --- | --- | --- | --- |
| **Cloudflare Pages (production)** | https://hk-aqhi.pages.dev/ | **GitLab** `bcmvl08/hk-aqhi` | `3d803e84` — Layout C glass (2026-10-24) | Primary public site; see [`DEPLOY.md`](DEPLOY.md) on GitLab |
| **GitHub Pages** | https://bcmvl08.github.io/hk-aqhi/ | **GitHub** `bcmvl08/hk-aqhi` | `986a8e3` — PR #5 sky dashboard (2026-10-29) | Alternate UI; README still describes GitHub Pages |

Cloudflare project `hk-aqhi` uses production branch **`main` on GitLab**, not GitHub. Pushes to GitHub `main` do **not** update hk-aqhi.pages.dev unless GitLab `main` is updated too.

## How JSON snapshots are published

| Remote | Mechanism | Last `Update AQHI and weather` commit (verified 2026-11-03) |
| --- | --- | --- |
| GitHub | [`.github/workflows/update-aqhi.yml`](../.github/workflows/update-aqhi.yml) — hourly cron + manual **Run workflow** | `72b5ebc` (2026-10-10); scheduled runs stopped after that run |
| GitLab | **No CI schedule in repo today** — last bot commit matches GitHub mirror era | `4f3faab` (2026-10-10) |

Both sites still serve **fallback** `data/aqhi.json` and `data/weather.json` from those dates when live fetches fail. hk-aqhi.pages.dev also proxies EPD XML at `/epd/24aqhi_Eng.xml` (see GitLab `_worker.js`), so AQHI in the browser can be live even when JSON is stale.

## Divergence summary

- **GitHub-only on `main`:** PR #5 dashboard restyle (Noto fonts, sticky bar, dark mode).
- **GitLab-only on `main`:** Cloudflare worker, `_headers`, `stations-h3.json`, Gemini assets, Layout C UI, expanded attribution in README.
- **Shared history** through early October 2026 (initial Actions workflow, fetch scripts, many hourly JSON commits).

There is **no automatic bidirectional sync** between GitHub and GitLab in either repository.

## Recommended operating model (for Benny)

1. **Pick a canonical remote** for app code (likely GitLab if production stays on Pages).
2. **Run hourly data publish on that remote** (GitHub Actions on GitHub; GitLab CI schedule on GitLab — see open MR).
3. **Either** mirror the other remote periodically **or** retire one host to avoid split UI and stale JSON.
4. After any workflow stall, GitHub may need **Enable workflow** in Actions plus a cron-line change; GitLab needs an active **CI/CD → Schedules** entry once `.gitlab-ci.yml` lands.

## English

Same facts as above: production is GitLab → Cloudflare Pages; GitHub Pages is a separate tip; JSON auto-commits stopped on both remotes around 2026-10-10 until restored by the follow-up PR/MR.
