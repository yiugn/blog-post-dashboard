#!/usr/bin/env python3
"""Locate a missing Tilnote post with logarithmic page checks."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import requests

from bootstrap_tilnote_search import JSON_PATH, save_document

USER_ID = "67262953c0c5c088c26e4fd0"
PAGE_SIZE = 20
URL = f"https://server.tilnote.io/api/blogs/{USER_ID}/pages"
HEADERS = {"User-Agent": "Blog-Post-Dashboard/1.0 (+GitHub Actions)"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch(page: int, timeout: int) -> dict:
    response = requests.get(
        f"{URL}?page={page}",
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["data"]


def merge_rows(merged: dict[str, dict], rows: list[dict]) -> int:
    added = 0
    stamp = now()
    for item in rows:
        post_id = str(item["_id"])
        key = f"Tilnote:knarchive:{post_id}"
        current = merged.get(key)
        if current is None:
            added += 1
            current = {}
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
    return added


def main() -> int:
    document = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    merged = {row["key"]: row for row in document["posts"]}

    first = fetch(1, 60)
    merge_rows(merged, list(first["pages"]))
    low, high = 1, int(first["lastPage"])
    found = 0

    while low <= high and found == 0:
        # Merge posts published while the binary search is running so page
        # offsets continue to refer to the same known newest-first ordering.
        first = fetch(1, 60)
        merge_rows(merged, list(first["pages"]))
        high = min(high, int(first["lastPage"]))
        known_ids = sorted(
            (
                row["post_id"]
                for row in merged.values()
                if row.get("platform") == "Tilnote"
            ),
            reverse=True,
        )
        index_by_id = {post_id: index for index, post_id in enumerate(known_ids)}

        middle = (low + high) // 2
        payload = fetch(middle, 300)
        rows = list(payload.get("pages", []))
        unknown = [
            row for row in rows if str(row.get("_id")) not in index_by_id
        ]
        if unknown:
            found += merge_rows(merged, unknown)
            print(
                f"Found {found} missing post(s) on page {middle}.",
                flush=True,
            )
            break

        start = (middle - 1) * PAGE_SIZE
        offsets = {
            index_by_id[str(row["_id"])] - (start + position)
            for position, row in enumerate(rows)
        }
        print(
            f"Checked page {middle}; range {low}-{high}; offsets {sorted(offsets)}",
            flush=True,
        )
        if offsets == {-1}:
            high = middle - 1
        elif offsets == {0}:
            low = middle + 1
        else:
            # A new publication likely shifted the page between the two
            # requests. Refresh the newest page and retry this midpoint.
            print("Page shifted during check; refreshing and retrying.", flush=True)

    posts = list(merged.values())
    posts.sort(
        key=lambda row: (
            row.get("published_at") or row.get("first_seen_at") or "",
            row.get("key", ""),
        ),
        reverse=True,
    )
    document["posts"] = posts
    document["generated_at"] = now()
    save_document(document)
    tilnote_count = sum(1 for row in posts if row.get("platform") == "Tilnote")
    print(f"Tilnote collected after binary search: {tilnote_count}", flush=True)
    return 0 if found else 2


if __name__ == "__main__":
    raise SystemExit(main())
