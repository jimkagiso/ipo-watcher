# IPO Watcher

Checks daily for new stock market listings on the JSE (via SENS), Nasdaq's IPO calendar,
and StockTitan's IPO news feed. Emails you a digest whenever something new shows up.

## What this can and can't do

- **Can:** tell you when a company IPOs/lists on the JSE or a major US exchange, based on
  public announcement sources.
- **Can't:** tell you the moment something becomes tradable on EasyEquities specifically —
  EasyEquities has no public API or IPO calendar. Treat this as an early-warning system,
  then check the EasyEquities app/site directly (search the ticker) to confirm availability.

## Setup (5–10 min)

1. Create a new **private** GitHub repo, e.g. `ipo-watcher`.
2. Push these files to it (same GitHub workflow you already use for JK Media's site).
3. Set up a free email sender — easiest is a Gmail **App Password**:
   - Go to your Google Account → Security → App Passwords → generate one for "Mail".
4. In the repo, go to **Settings → Secrets and variables → Actions → New repository secret**
   and add:
   - `SMTP_HOST` = `smtp.gmail.com`
   - `SMTP_PORT` = `465`
   - `SMTP_USER` = your Gmail address
   - `SMTP_PASSWORD` = the app password from step 3
   - `ALERT_TO_EMAIL` = the email address you want alerts sent to
5. Done. It runs daily at 08:00 SAST automatically. You can also trigger it manually from
   the **Actions** tab → "IPO Watcher" → "Run workflow".

## Getting the phone dashboard live

The daily job now also writes `docs/listings_data.json`, and there's a dashboard page at
`docs/index.html` that reads it. Easiest way to publish it — free, no extra account needed:

1. Push the updated files (including the new `docs/` folder) to your `ipo-watcher` repo.
2. In the repo, go to **Settings → Pages**.
3. Under "Build and deployment", set **Source** to "Deploy from a branch".
4. Set **Branch** to `main` and the folder to `/docs`, then **Save**.
5. GitHub will give you a URL like `https://jimkagiso.github.io/ipo-watcher/` — that's your
   dashboard. Takes a minute or two to go live the first time.
6. Bookmark it on your phone (or "Add to Home Screen" for an app-like icon).

The dashboard updates automatically each time the daily Action runs and commits fresh data —
no separate deploy step needed. If you'd rather use Netlify (same flow as JK Media's site),
that works too: just point it at this repo with `docs` as the publish directory.

## Customizing

- **Add more sources**: write a `fetch_x()` function following the same pattern as the
  existing ones, then wire it into `main()`.
- **Add LSE / other EasyEquities-supported markets**: the London Stock Exchange publishes
  a "new issues" list — worth adding once you confirm which specific international
  exchanges matter most to you (EasyEquities offers access to several, not just US/UK).
- **Change frequency**: edit the `cron` line in `.github/workflows/ipo-watcher.yml`.
- **Cross-check EasyEquities directly**: the unofficial `easy-equities-client` Python
  package (github.com/deanmalan/easy-equities-client) can search EasyEquities' instrument
  list programmatically — useful for a future version that auto-checks whether a flagged
  IPO has actually landed on the platform.

## Notes

- Sources here are free/public but unofficial in places (e.g. Nasdaq's and StockTitan's
  internal JSON endpoints). They can change format without notice — if the digest goes
  quiet, check the Actions tab for errors first.
- This is an information tool, not investment advice.
