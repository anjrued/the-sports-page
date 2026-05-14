# The Sports Page — Go-Live Guide

## What You Have

Five files to deploy:

| File | Purpose |
|------|---------|
| `SportsGazette.jsx` | **Demo/preview only** — the Claude artifact you've been testing |
| `pipeline.py` | Runs daily, fetches real scores, calls Claude to write stories, outputs `data.json` |
| `.github/workflows/daily.yml` | GitHub Actions cron job that runs `pipeline.py` every morning automatically |
| `docs/index.html` | The actual live website — reads `data.json` and renders the newspaper |
| `docs/data.json` | Generated daily by the pipeline (auto-committed by the bot) |

> **Note:** `SportsGazette.jsx` is your preview tool inside Claude. The live site is `docs/index.html` — a static HTML file that reads `data.json`. They share the same design but the HTML file is what visitors see.

---

## Part 1 — Set Up GitHub (Free)

GitHub hosts your code and runs the daily automation for free.

1. Go to **github.com** and create a free account if you don't have one
2. Click the **+** icon → **New repository**
3. Name it: `the-sports-page` (or whatever you want)
4. Set it to **Public** (required for free GitHub Pages hosting)
5. Click **Create repository**

### Upload your files

In the new repo, click **Add file → Upload files** and upload these in their exact folder structure:

```
the-sports-page/
├── pipeline.py
├── docs/
│   └── index.html
└── .github/
    └── workflows/
        └── daily.yml
```

**Important:** The `.github` folder starts with a dot — your computer may hide it. On Mac, press `Cmd+Shift+.` to show hidden files. On Windows, enable "Show hidden items" in File Explorer.

---

## Part 2 — Add Your Anthropic API Key (Secret)

The pipeline calls Claude to write stories. Your API key must be stored as a secret (never put it in a file).

1. In your GitHub repo, go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`
4. Value: your key from **console.anthropic.com** (sign up free, pay only for usage — roughly $0.30–$1.00/month)
5. Click **Add secret**

---

## Part 3 — Enable GitHub Pages (Free Hosting)

1. In your repo, go to **Settings → Pages**
2. Under **Source**, select **Deploy from a branch**
3. Branch: `main` — Folder: `/docs`
4. Click **Save**

Your site will go live at:
`https://YOUR-GITHUB-USERNAME.github.io/the-sports-page/`

It may take 2–3 minutes the first time.

---

## Part 4 — Run the Pipeline for the First Time

The automation runs every morning at 7 AM UTC automatically — but you need to kick off the first run manually to generate `data.json`.

1. Go to your repo → **Actions** tab
2. Click **Daily Sports Edition** in the left sidebar
3. Click **Run workflow → Run workflow**
4. Wait 1–2 minutes
5. Refresh your live site — it should now show today's sports section

After this, it runs on its own every morning. You never touch it again.

---

## Part 5 — Buy a Custom Domain

### Where to buy

| Registrar | Cost/year | Notes |
|-----------|-----------|-------|
| **Namecheap** (namecheap.com) | ~$9–14 | Best value, clean interface, recommended |
| **Cloudflare** (cloudflare.com/products/registrar) | At-cost (~$8–10) | Cheapest, excellent security, no markup |
| **Squarespace Domains** (domains.squarespace.com) | ~$12–20 | Simple, formerly Google Domains |
| **GoDaddy** (godaddy.com) | ~$12+ | Widely known, watch for upsells |

### What to buy

Pick a `.com` if available. Ideas:
- `thesportspage.com`
- `yourlastname-sportspage.com`
- `treasurecoastsports.com`
- `sportspagefl.com`

A `.com` runs about $10–14/year. Avoid paying for extras like "privacy protection upsell" — Namecheap and Cloudflare include WHOIS privacy free.

---

## Part 6 — Connect Your Domain to GitHub Pages

### Step A — Add the domain in GitHub

1. Repo → **Settings → Pages**
2. Under **Custom domain**, type your domain (e.g. `www.thesportspage.com`)
3. Click **Save**
4. GitHub will create a `CNAME` file in your `docs/` folder automatically

### Step B — Point your DNS to GitHub

Log into your domain registrar and find **DNS Settings** or **Manage DNS**.

Add these records:

**For the root domain** (e.g. `thesportspage.com`) — add 4 A records:

| Type | Host | Value |
|------|------|-------|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |

**For www** — add 1 CNAME record:

| Type | Host | Value |
|------|------|-------|
| CNAME | www | YOUR-GITHUB-USERNAME.github.io |

### Step C — Enable HTTPS (free SSL)

Back in GitHub → Settings → Pages, check **Enforce HTTPS** once it appears (takes 15–30 minutes after DNS propagates).

DNS propagation takes anywhere from 15 minutes to 48 hours. Usually under an hour with Cloudflare or Namecheap.

---

## What Happens Every Day (Automatically)

```
7:00 AM UTC (3:00 AM Eastern)
        ↓
GitHub Actions wakes up
        ↓
Runs pipeline.py
        ↓
Fetches real scores from ESPN API (free, no key needed)
        ↓
Calls Claude to write headlines, stories, and opinion column
        ↓
Writes docs/data.json
        ↓
Commits and pushes to GitHub
        ↓
GitHub Pages serves the updated site
        ↓
Visitors see today's fresh sports section
```

**Monthly cost estimate:**
- GitHub: Free
- GitHub Pages: Free
- ESPN API: Free
- Anthropic API (Claude): ~$0.30–$1.00/month
- Domain: ~$1.00/month ($10–14/year)

**Total: roughly $1–2/month**

---

## Troubleshooting

**Site not updating:** Go to Actions tab and check if the daily run succeeded. Red = failed, green = success.

**Pipeline failing:** Check that your `ANTHROPIC_API_KEY` secret is set correctly.

**Domain not working:** DNS propagation can take up to 48 hours. Use **dnschecker.org** to see if your records have propagated.

**Want to change the schedule:** Edit the cron line in `.github/workflows/daily.yml`. Use crontab.guru to find the right time format.
