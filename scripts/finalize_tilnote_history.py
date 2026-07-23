#!/usr/bin/env python3
"""Confirm Tilnote's exact total from its last page and close the bootstrap."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import requests

from bootstrap_tilnote_search import JSON_PATH, save_document

USER_ID = "67262953c0c5c088c26e4fd0"
PAGE_SIZE = 20


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    first_response = requests.get(
        f"https://server.tilnote.io/api/blogs/{USER_ID}/pages?page=1",
        headers={"User-Agent": "Blog-Post-Dashboard/1.0 (+GitHub Actions)"},
        timeout=60,
    )
    first_response.raise_for_status()
    first_payload = first_response.json()["data"]
    first_rows = list(first_payload.get("pages", []))
    current_last_page = int(first_payload["lastPage"])
    response = requests.get(
        f"https://server.tilnote.io/api/blogs/{USER_ID}/pages?page={current_last_page}",
        headers={"User-Agent": "Blog-Post-Dashboard/1.0 (+GitHub Actions)"},
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()["data"]
    last_rows = list(payload.get("pages", []))
    rows_by_id = {
        str(item["_id"]): item for item in first_rows + last_rows
    }
    rows = list(rows_by_id.values())
    actual_last_page = int(payload.get("lastPage", current_last_page))
    exact_total = (actual_last_page - 1) * PAGE_SIZE + len(last_rows)

    document = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    merged = {row["key"]: row for row in document["posts"]}
    stamp = now()
    for item in rows:
        post_id = str(item["_id"])
        key = f"Tilnote:knarchive:{post_id}"
        current = merged.get(key, {})
        merged[key] = {
            "key": key,
            "platform": "Tilnote",
            "slug": "knarchive",
            "blog_name": "knarchive",
            "blog_url": "https://tilnote.io/@knarchive",
            "account_masked": "",
            "post_id": post_id,
            "title": " ".join(str(item.get("title") or "(제목 없음)").split()),
            "post_url": f"https://tilnote.io/pages/{post_id}",
            "published_at": str(item.get("createdAt") or ""),
            "first_seen_at": current.get("first_seen_at") or stamp,
            "last_seen_at": stamp,
        }

    posts = list(merged.values())
    posts.sort(
        key=lambda row: (
            row.get("published_at") or row.get("first_seen_at") or "",
            row.get("key", ""),
        ),
        reverse=True,
    )
    document["posts"] = posts
    document["generated_at"] = stamp
    tilnote_count = sum(1 for row in posts if row.get("platform") == "Tilnote")
    state = document.setdefault("source_state", {}).setdefault("tilnote", {})
    state.update(
        {
            "total_pages": actual_last_page,
            "history_expected_posts": exact_total,
            "history_collected_posts": tilnote_count,
            "history_complete": tilnote_count >= exact_total,
            "remaining_pages": 0 if tilnote_count >= exact_total else state.get("remaining_pages"),
            "completed_count": actual_last_page if tilnote_count >= exact_total else state.get("completed_count"),
            "last_page_verified_at": stamp,
        }
    )
    if tilnote_count >= exact_total:
        state["completed_pages"] = list(range(1, actual_last_page + 1))
    save_document(document)
    print(
        f"Tilnote exact total: {exact_total}; collected: {tilnote_count}; "
        f"last page rows: {len(last_rows)}; complete: {state['history_complete']}",
        flush=True,
    )
    return 0 if state["history_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
