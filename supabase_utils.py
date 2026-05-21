"""Supabase utilities for PR comments management"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def get_supabase_client() -> Client:
    """Initialize and return Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in the .env file")

    return create_client(url, key)


def upsert_pr_comment(client: Client, comment_data: dict) -> dict:
    """Insert a comment into Supabase, ignoring duplicates (by comment_url)."""
    try:
        response = client.table("pr_comments").upsert(
            comment_data,
            on_conflict="comment_url"
        ).execute()
        return response
    except Exception as e:
        print(f"❌ Upsert error: {e}")
        raise


def get_comment_by_url(client: Client, comment_url: str) -> dict:
    """Check if a comment with the given URL already exists."""
    try:
        response = client.table("pr_comments").select("id").eq(
            "comment_url", comment_url
        ).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"❌ Lookup error: {e}")
        return None


def bulk_insert_comments(client: Client, comments: list) -> tuple[int, int]:
    """
    Insert multiple comments, skipping duplicates.

    Returns:
        (inserted_count, skipped_count)
    """
    inserted = 0
    skipped = 0

    for comment in comments:
        try:
            existing = get_comment_by_url(client, comment["comment_url"])
            if existing:
                skipped += 1
                continue

            upsert_pr_comment(client, comment)
            inserted += 1
        except Exception as e:
            print(f"⚠️  Failed to insert comment {comment['comment_url']}: {e}")
            continue

    return inserted, skipped
