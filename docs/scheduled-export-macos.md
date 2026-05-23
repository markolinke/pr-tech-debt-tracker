# Scheduled Export on macOS (launchd)

This guide explains how to run `export_pr_comments.py` automatically every hour on macOS using `launchd`.

## Prerequisites

- The repository is cloned and the `.venv` virtual environment is set up
- A `.env` file exists in the project root with `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `REPO` set
- The `gh` CLI is installed (via Homebrew: `brew install gh`) and authenticated (`gh auth login`)

## Setup

### 1. Create the LaunchAgent plist

Create the file `~/Library/LaunchAgents/com.marko.pr-tech-debt-tracker.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.marko.pr-tech-debt-tracker</string>

    <key>ProgramArguments</key>
    <array>
        <string>/path/to/pr-tech-debt-tracker/.venv/bin/python</string>
        <string>/path/to/pr-tech-debt-tracker/export_pr_comments.py</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>

    <key>WorkingDirectory</key>
    <string>/path/to/pr-tech-debt-tracker</string>

    <key>StartInterval</key>
    <integer>3600</integer>

    <key>StandardOutPath</key>
    <string>/Users/your-username/Library/Logs/pr-tech-debt-tracker.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/your-username/Library/Logs/pr-tech-debt-tracker.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

Replace `/path/to/pr-tech-debt-tracker` with the actual absolute path to the repository, and `your-username` with your macOS username.

> **Note on PATH:** launchd does not inherit your shell's `$PATH`. The `EnvironmentVariables` block ensures the `gh` CLI (installed via Homebrew at `/opt/homebrew/bin/gh`) is found at runtime.

### 2. Load and start the agent

```bash
launchctl load ~/Library/LaunchAgents/com.marko.pr-tech-debt-tracker.plist

# Optional: trigger a run immediately to verify everything works
launchctl start com.marko.pr-tech-debt-tracker
```

### 3. Check the logs

```bash
tail -f ~/Library/Logs/pr-tech-debt-tracker.log
```

A successful run looks like:

```
   Repo (env REPO): owner/repo
🚀 Exporting PR review comments from the last 30 days
   Repository: owner/repo

✅ Connected to Supabase
📋 Fetching PRs updated since ...
   Found 57 PRs
  PR #123: ... ✓ (4 comments)
  ...
✅ Supabase updated!
   ➕ Inserted: 12 new comments
   ⏭️  Skipped: 45 duplicates
```

## Useful commands

| Action | Command |
|---|---|
| Check logs | `tail -f ~/Library/Logs/pr-tech-debt-tracker.log` |
| Trigger manually | `launchctl start com.marko.pr-tech-debt-tracker` |
| Stop the agent | `launchctl unload ~/Library/LaunchAgents/com.marko.pr-tech-debt-tracker.plist` |
| Restart the agent | `launchctl unload ... && launchctl load ...` |
| Verify it is loaded | `launchctl list | grep pr-tech-debt` |

## How it works

- `StartInterval 3600` tells launchd to run the job every 3600 seconds (1 hour)
- `RunAtLoad false` means it does **not** run immediately when the agent is loaded — only on the next scheduled interval
- The agent is user-scoped (`~/Library/LaunchAgents`) so it runs as your user and has access to your `gh` authentication and `.env` file
- If the Mac is asleep when a scheduled run is due, launchd will run the job the next time the Mac is awake

## Troubleshooting

**`[Errno 2] No such file or directory: 'gh'`**
The PATH in the plist does not include the Homebrew bin directory. Make sure `/opt/homebrew/bin` is in the `PATH` value (Apple Silicon Macs) or `/usr/local/bin` (Intel Macs).

**`SUPABASE_URL and SUPABASE_ANON_KEY must be set`**
The `.env` file is missing or the `WorkingDirectory` in the plist does not point to the correct folder. The script loads `.env` relative to the working directory.

**Nothing appears in the log**
Check if the agent is actually loaded:
```bash
launchctl list | grep pr-tech-debt
```
If it's missing, run the `launchctl load` command again.
