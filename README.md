# 🎬 Movie Ticket Monitor

Automatically checks **BookMyShow**, **PVR**, and **INOX** every 10 minutes for
IMAX 2D tickets and emails you the moment they go live.

Runs entirely free on **GitHub Actions** — no server needed.

---

## Setup (5 minutes)

### 1. Create a new GitHub repo

Go to [github.com/new](https://github.com/new), create a **private** repo
(keep your email private), and upload both files:

```
ticket_monitor.py
.github/workflows/check_tickets.yml
```

### 2. Get a Gmail App Password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. App: **Mail** → Device: **Other** → Name: `ticket-monitor`
3. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)

### 3. Add GitHub Secrets

In your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these three secrets:

| Secret Name          | Value                          |
|----------------------|--------------------------------|
| `SENDER_EMAIL`       | your Gmail address             |
| `SENDER_APP_PASSWORD`| the 16-char app password       |
| `RECIPIENT_EMAIL`    | where to send the alert        |

### 4. Enable GitHub Actions

Go to the **Actions** tab in your repo and click **"I understand my workflows, go ahead and enable them"** if prompted.

### 5. Test it manually

Actions tab → **"🎬 Movie Ticket Monitor"** → **"Run workflow"** → **Run**

Check the logs to confirm it ran. You'll get an email as soon as tickets are available.

---

## How it works

- GitHub's cron scheduler triggers the workflow every 10 minutes
- The script does a single check across all three platforms
- If IMAX 2D shows are found, it sends you a formatted email with direct booking links
- GitHub Actions is **free** for public repos and has a generous free tier for private repos

---

## Files

```
├── ticket_monitor.py                    # The checker script
└── .github/
    └── workflows/
        └── check_tickets.yml           # GitHub Actions schedule
```