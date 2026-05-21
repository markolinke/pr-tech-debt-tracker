#!/usr/bin/env python3
"""
GitHub PR Review Debt Tracker - Supabase verzija
Izvlači PR review komentare i sprema ih u Supabase

Korištenje:
    python export_pr_comments.py [owner/repo] [--days 30] [--to-csv]
"""

import subprocess
import json
import csv
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from supabase_utils import get_supabase_client, bulk_insert_comments


def get_current_repo() -> str:
    """Auto-detektuj repo iz trenutnog git direktorijuma"""
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
    """Pokreni GitHub CLI komandu i vrati JSON"""
    try:
        result = subprocess.run(
            ["gh"] + cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Greška pri pokretu gh komande: {e.stderr}")
        raise
    except json.JSONDecodeError:
        print(f"❌ Greška pri parsiranju JSON-a")
        raise


def get_prs_from_last_n_days(repo: str, days: int) -> list:
    """Uzmi sve PR-ove koji su se mijenjali u posljednjih N dana"""
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    
    print(f"📋 Preuzimam PR-ove koji su se mijenjali od {cutoff_date}...")
    
    cmd = [
        "pr", "list",
        "--repo", repo,
        "--state", "all",
        "--limit", "10000",
        "--search", f"updated:>{cutoff_date}",
        "--json", "number,title,author,createdAt,updatedAt,url"
    ]
    
    prs = run_gh_command(cmd)
    print(f"   Pronađeno {len(prs)} PR-ova")
    return prs


def get_review_comments(repo: str, pr_number: int, cutoff_date: str) -> list:
    """Uzmi review komentare za specifičan PR"""
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
    """Formatiraj komentar za Supabase"""
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


def export_to_supabase(repo: str, days: int) -> None:
    """Glavna funkcija - izvlači komentare i sprema u Supabase"""
    
    print(f"🚀 Izvozim PR review komentare iz posljednjih {days} dana")
    print(f"   Repositorij: {repo}")
    print()
    
    # Inicijaliziraj Supabase klijent
    try:
        client = get_supabase_client()
        print("✅ Povezan na Supabase")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    
    # Uzmi sve PR-ove
    prs = get_prs_from_last_n_days(repo, days)
    
    # Prikupljaj sve komentare
    all_comments_for_db = []
    
    for pr in prs:
        pr_num = pr["number"]
        pr_title = pr["title"]
        
        print(f"  PR #{pr_num}: {pr_title[:50]}... ", end="", flush=True)
        
        # Uzmi review komentare
        comments = get_review_comments(repo, pr_num, cutoff_date)
        
        for comment in comments:
            db_record = format_for_supabase(pr, comment, repo)
            all_comments_for_db.append(db_record)
        
        print(f"✓ ({len(comments)} komentara)")
    
    # Umeć sve komentare u Supabase
    if all_comments_for_db:
        print()
        print(f"💾 Umećem {len(all_comments_for_db)} komentara u Supabase...")
        
        inserted, skipped = bulk_insert_comments(client, all_comments_for_db)
        
        print()
        print(f"✅ Supabase ažuriran!")
        print(f"   ➕ Umetano: {inserted} novih komentara")
        print(f"   ⏭️  Preskaču: {skipped} duplikata")
    else:
        print()
        print("⚠️  Nije pronađeno komentara u ovom periodu")


def export_to_csv(repo: str, days: int, output_file: str = None) -> None:
    """Opciono: Također spremi u CSV za backup"""
    
    if output_file is None:
        output_file = f"pr_review_debt.csv"
    
    print(f"💾 Izvozim u CSV: {output_file}")
    
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
        fieldnames = list(all_rows[0].keys())
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        
        print(f"✅ CSV exportan: {output_file}")
    else:
        print("⚠️  Nije pronađeno komentara")


def main():
    parser = argparse.ArgumentParser(
        description="Izvezi GitHub PR review komentare u Supabase"
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=None,
        help="Repositorij (format: owner/repo). Auto-detektuje ako je u git repo."
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=30,
        help="Koliko dana unatrag da se pretraži (default: 30)"
    )
    parser.add_argument(
        "--to-csv",
        action="store_true",
        help="Također spremi u CSV datoteku"
    )
    parser.add_argument(
        "--output", "-o",
        help="CSV output datoteka (default: pr_review_debt.csv)"
    )
    
    args = parser.parse_args()
    
    # Auto-detektuj repo ako nije proslijeđen
    repo = args.repo
    if not repo:
        print("🔍 Auto-detektujem repositorij...")
        repo = get_current_repo()
        if not repo:
            print("❌ Ne mogu auto-detektovati repo. Molim navedi: owner/repo")
            sys.exit(1)
        print(f"   Pronađeno: {repo}")
    
    try:
        export_to_supabase(repo, args.days)
        
        if args.to_csv:
            export_to_csv(repo, args.days, args.output)
    
    except KeyboardInterrupt:
        print("\n⚠️  Prekidač od strane korisnika")
    except Exception as e:
        print(f"\n❌ Greška: {e}")
        exit(1)


if __name__ == "__main__":
    main()
