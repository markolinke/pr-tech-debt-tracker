#!/usr/bin/env python3
"""
GitHub PR Review Debt Tracker - Supabase edition
Fetches PR review comments and saves them to Supabase

Usage:
    python export_pr_comments.py [owner/repo] [--days 30] [--to-csv]
"""

import os
import subprocess
import json
import csv
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from supabase_utils import get_supabase_client, bulk_insert_comments


def get_current_repo() -> str:
    """Detect repo from the current git directory."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path.cwd()
        )
        url = result.stdout.strip()
        if "github.com" in url:
            if url.endswith(".git"):
                url = url[:-4]
            repo = url.split("github.com")[1].lstrip("/:").rstrip("/")
            return repo
    except (subprocess.CalledProcessError, IndexError):
        pass

    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner"],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        return data["nameWithOwner"]
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        return None


def run_gh_command(cmd: list) -> dict | list:
    """Run a GitHub CLI command and return parsed JSON."""
    try:
        result = subprocess.run(
            ["gh"] + cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ gh command failed: {e.stderr}")
        raise
    except json.JSONDecodeError:
        print(f"❌ Failed to parse JSON response")
        raise


def get_prs_from_last_n_days(repo: str, days: int) -> list:
    """Fetch all PRs updated within the last N days."""
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    print(f"📋 Fetching PRs updated since {cutoff_date}...")

    cmd = [
        "pr", "list",
        "--repo", repo,
        "--state", "all",
        "--limit", "10000",
        "--search", f"updated:>{cutoff_date}",
        "--json", "number,title,author,createdAt,updatedAt,url"
    ]

    prs = run_gh_command(cmd)
    print(f"   Found {len(prs)} PRs")
    return prs


def get_review_comments(repo: str, pr_number: int, cutoff_date: str) -> list:
    """Fetch review comments for a specific PR."""
    try:
        cmd = [
            "api",
            f"repos/{repo}/pulls/{pr_number}/comments",
            "--paginate",
            "-H", "Accept: application/vnd.github.v3+json"
        ]

        data = run_gh_command(cmd)

        if isinstance(data, dict) and "message" in data:
            return []

        comments_list = data if isinstance(data, list) else [data]

        all_comments = []
        for comment in comments_list:
            created_at = comment.get("created_at", "")
            if created_at > cutoff_date:
                all_comments.append({
                    "body": comment.get("body", ""),
                    "author": {"login": comment.get("user", {}).get("login", "unknown")},
                    "createdAt": created_at,
                    "path": comment.get("path", ""),
                    "line": comment.get("line", ""),
                    "url": comment.get("html_url", ""),
                    "diff_hunk": comment.get("diff_hunk", "")
                })

        return all_comments
    except (subprocess.CalledProcessError, KeyError, TypeError):
        return []


def format_for_supabase(pr: dict, comment: dict, repo: str) -> dict:
    """Format a comment record for Supabase insertion."""
    return {
        "repo": repo,
        "pr_number": pr["number"],
        "pr_title": pr["title"],
        "pr_author": pr["author"]["login"],
        "pr_created_at": pr["createdAt"],
        "pr_url": pr["url"],
        "comment_author": comment["author"]["login"],
        "comment_date": comment["createdAt"],
        "comment_path": comment["path"],
        "comment_line": comment["line"],
        "comment_text": comment["body"],
        "comment_url": comment["url"],
        "comment_diff_hunk": comment["diff_hunk"],
        "viewed": False,
        "status": "open",
        "priority": "medium"
    }


def export_to_supabase(repo: str, days: int, dry_run: bool = False) -> None:
    """Main function — fetch comments and save to Supabase."""

    print(f"🚀 Exporting PR review comments from the last {days} days")
    print(f"   Repository: {repo}")
    if dry_run:
        print("   Mode: DRY RUN — nothing will be saved")
    print()

    if not dry_run:
        try:
            client = get_supabase_client()
            print("✅ Connected to Supabase")
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
    else:
        client = None

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    prs = get_prs_from_last_n_days(repo, days)

    all_comments_for_db = []

    for pr in prs:
        pr_num = pr["number"]
        pr_title = pr["title"]

        print(f"  PR #{pr_num}: {pr_title[:50]}... ", end="", flush=True)

        comments = get_review_comments(repo, pr_num, cutoff_date)

        for comment in comments:
            db_record = format_for_supabase(pr, comment, repo)
            all_comments_for_db.append(db_record)

        print(f"✓ ({len(comments)} comments)")

    print()
    if not all_comments_for_db:
        print("⚠️  No comments found in this period")
        return

    if dry_run:
        print(f"🔍 Dry run — would insert {len(all_comments_for_db)} comments into Supabase")
    else:
        print(f"💾 Inserting {len(all_comments_for_db)} comments into Supabase...")

        inserted, skipped = bulk_insert_comments(client, all_comments_for_db)

        print(f"✅ Supabase updated!")
        print(f"   ➕ Inserted: {inserted} new comments")
        print(f"   ⏭️  Skipped: {skipped} duplicates")


def export_to_csv(repo: str, days: int, output_file: str = None, dry_run: bool = False) -> None:
    """Optional: also save comments to a CSV file for backup."""

    if output_file is None:
        output_file = "pr_review_debt.csv"

    if dry_run:
        print(f"🔍 Dry run — would export to CSV: {output_file}")
    else:
        print(f"💾 Exporting to CSV: {output_file}")

    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    prs = get_prs_from_last_n_days(repo, days)

    all_rows = []

    for pr in prs:
        pr_num = pr["number"]
        comments = get_review_comments(repo, pr_num, cutoff_date)

        for comment in comments:
            row = {
                "PR_Number": pr_num,
                "PR_Title": pr["title"],
                "PR_Author": pr["author"]["login"],
                "PR_Created_At": pr["createdAt"],
                "PR_URL": pr["url"],
                "Comment_Author": comment["author"]["login"],
                "Comment_Date": comment["createdAt"],
                "Comment_Path": comment["path"],
                "Comment_Line": comment["line"],
                "Comment_URL": comment.get("url", ""),
                "Comment_Text": comment["body"].replace("\n", " ").replace('"', '""')
            }
            all_rows.append(row)

    if all_rows:
        if dry_run:
            print(f"🔍 Dry run — would write {len(all_rows)} rows to {output_file}")
        else:
            fieldnames = list(all_rows[0].keys())
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)

            print(f"✅ CSV exported: {output_file}")
    else:
        print("⚠️  No comments found")


def main():
    parser = argparse.ArgumentParser(
        description="Export GitHub PR review comments to Supabase"
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=None,
        help="Repository in owner/repo format. Auto-detected if running inside a git repo."
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="How many days back to search (default: 30)"
    )
    parser.add_argument(
        "--to-csv",
        action="store_true",
        help="Also save to a CSV file"
    )
    parser.add_argument(
        "--output", "-o",
        help="CSV output file (default: pr_review_debt.csv)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and process comments but do not write anything to Supabase or CSV"
    )

    args = parser.parse_args()

    # Repo resolution: CLI argument → REPO env var → auto-detect from git
    repo = args.repo
    if repo:
        print(f"   Repo (argument): {repo}")
    else:
        env_repo = os.getenv("REPO")
        if env_repo:
            repo = env_repo
            print(f"   Repo (env REPO): {repo}")
        else:
            print("🔍 Auto-detecting repository...")
            repo = get_current_repo()
            if not repo:
                print("❌ Could not detect repo. Pass it as an argument or set the REPO env variable.")
                sys.exit(1)
            print(f"   Repo (auto-detected): {repo}")

    try:
        export_to_supabase(repo, args.days, dry_run=args.dry_run)

        if args.to_csv:
            export_to_csv(repo, args.days, args.output, dry_run=args.dry_run)

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
