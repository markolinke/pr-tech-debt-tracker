# GitHub PR Review Debt Tracker - Supabase version

Extracts GitHub PR review comments and stores them in a Supabase database. Enables tracking, filtering, and actions on comments.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the `.env` file

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and add your Supabase credentials:

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
```

### 3. Create the table in Supabase

Run the SQL script `create_supabase_table.sql` in the Supabase SQL editor.

## Usage

### Basic example — save to Supabase only

```bash
# In a git repository — auto-detects the repo
python export_pr_comments.py

# Or specify the repo explicitly
python export_pr_comments.py owner/repo

# Last 14 days
python export_pr_comments.py owner/repo --days 14
```

### With CSV export

```bash
# Save to both Supabase and CSV
python export_pr_comments.py --to-csv

# Custom CSV file
python export_pr_comments.py --to-csv -o my_comments.csv
```

## How it works

1. **Fetch PRs** — `gh pr list` finds all PRs that changed in the last N days
2. **Fetch comments** — For each PR, pulls review comments from the GitHub API
3. **Upsert to Supabase** — Saves comments to the `pr_comments` table
   - Adds new comments
   - Ignores duplicates (by `comment_url`)
4. **CSV optional** — For backup or analysis in another tool

## Database structure

The `pr_comments` table contains:

- **PR info**: `pr_number`, `pr_title`, `pr_author`, `pr_created_at`, `pr_url`
- **Comment**: `comment_author`, `comment_date`, `comment_path`, `comment_line`, `comment_text`, `comment_url`, `comment_diff_hunk`
- **Actions**: `viewed`, `status`, `priority`, `assigned_to`, `notes`
- **Timestamps**: `created_at`, `updated_at`

## Cron setup (optional)

To run automatically every 24 hours:

```bash
# Linux/Mac — add to crontab
0 2 * * * cd /path/to/project && python export_pr_comments.py >> /var/log/pr_tracker.log 2>&1
```

## Dashboard

To run locally, serve the `docs/` folder with a local HTTP server:

```bash
cd docs && python3 -m http.server 8081
# → http://localhost:8081
```

On `localhost` auth is skipped automatically — the dashboard loads directly without a login prompt.

**What the dashboard provides:**
- ✅ Real-time display of all comments
- ✅ Inline editing — change status or priority directly (no reload)
- ✅ Live filters — by status, priority, author, text
- ✅ Stats — counts of total, open, and resolved comments
- ✅ Auto-refresh every 30 seconds

**Statuses:**
- **Open** — needs work
- **Resolved** — done, action completed
- **Dismissed** — ignoring, not relevant

**Priorities:**
- **Low** — can wait
- **Medium** — work on it now
- **High** — urgent

## Authentication setup

The dashboard uses GitHub OAuth via Supabase Auth. Only invited users can log in — open signups are disabled.

### 1. Create a GitHub OAuth App

Go to github.com → Settings → Developer settings → OAuth Apps → New OAuth App:

| Field | Value |
|---|---|
| Homepage URL | your GitHub Pages URL (or any URL) |
| Authorization callback URL | `https://<your-supabase-id>.supabase.co/auth/v1/callback` |
| Enable Device Flow | No |

Copy the **Client ID** and **Client Secret**.

### 2. Enable GitHub provider in Supabase

Authentication → Providers → GitHub → Enable, paste Client ID and Client Secret.

### 3. Disable open signups

Authentication → Settings → **Enable sign ups → OFF**

This ensures nobody can self-register — only users you explicitly invite can access the dashboard.

### 4. Set up RLS policies

Run in the Supabase SQL Editor:

```sql
ALTER TABLE pr_comments ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read and update
CREATE POLICY "Authenticated users can read"
  ON pr_comments FOR SELECT TO authenticated USING (true);

CREATE POLICY "Authenticated users can update"
  ON pr_comments FOR UPDATE TO authenticated USING (true) WITH CHECK (true);

-- Anon key allowed to insert (used by the sync script)
CREATE POLICY "Script can insert"
  ON pr_comments FOR INSERT TO anon WITH CHECK (true);
```

### 5. Invite team members

Authentication → Users → **Invite user** → enter their email (must match their GitHub account email).

They'll receive an email link, click it once to activate, then use "Sign in with GitHub" normally from that point on.

### 6. Add redirect URLs (if hosting publicly)

Authentication → URL Configuration → Redirect URLs → add your hosted URL (e.g. `https://yourteam.github.io/pr-tech-debt-tracker`).

## Adding or changing statuses

Current statuses: `open`, `accepted`, `resolved`, `dismissed`, `archived`.

To add a new status (e.g. `in-progress`), update these four places:

**1. Supabase — check for a CHECK constraint**

In the Supabase dashboard: *Database → Tables → pr_comments → Constraints tab*.

If a `status` constraint exists, update it in the SQL Editor:

```sql
ALTER TABLE pr_comments
  DROP CONSTRAINT IF EXISTS pr_comments_status_check;

ALTER TABLE pr_comments
  ADD CONSTRAINT pr_comments_status_check
  CHECK (status IN ('open', 'accepted', 'resolved', 'dismissed', 'archived', 'ticket-created'));
```

If no constraint exists, skip this step.

**2. `dashboard/index.html` — filter dropdown**

```html
<select id="filterStatus">
  ...
  <option value="in-progress">In progress</option>  <!-- add here -->
</select>
```

**3. `dashboard/index.html` — per-comment status select (inside `renderComments()`)**

```js
<option value="in-progress" ${comment.status === 'in-progress' ? 'selected' : ''}>In progress</option>
```

**4. `dashboard/index.html` — stats card and `updateStats()`**

Add a stat card in the HTML:
```html
<div class="stat-card">
  <div class="stat-number" id="inProgressComments">0</div>
  <div class="stat-label">In progress</div>
</div>
```

Add a line in `updateStats()`:
```js
const inProgress = allComments.filter(c => c.status === 'in-progress').length
document.getElementById('inProgressComments').textContent = inProgress
```

**5. `dashboard/index.html` — badge color (optional)**

```css
.status-in-progress {
  background: #fff3cd;
  color: #856404;
}
```

## Errors & troubleshooting

**"SUPABASE_URL and SUPABASE_ANON_KEY must be set"**
- Check that the `.env` file exists and has the correct credentials

**"gh: command not found"**
- Install GitHub CLI: `brew install gh` (macOS) or `choco install gh` (Windows)

**Duplicates in the database?**
- The script uses `upsert` on `comment_url` — if the URL is the same, the comment is updated

**Dashboard did not load in the browser?**
- Check that credentials in `dashboard/index.html` are correct (they must match `.env`)
- Check CORS — Supabase must allow requests from local hosting
