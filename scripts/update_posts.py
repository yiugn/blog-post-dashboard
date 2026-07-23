#!/usr/bin/env python3
"""Collect public post metadata without ever writing credentials to disk."""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "blogs.json"
JSON_PATH = ROOT / "data" / "posts.json"
CSV_PATH = ROOT / "data" / "posts.csv"
USER_AGENT = "Blog-Post-Dashboard/1.0 (+GitHub Actions)"
TIMEOUT = 40


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def get_json(session: requests.Session, url: str, attempts: int = 4) -> dict[str, Any]:
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def first_value(item: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return value
    return None


def normalise_date(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def collect_wikidocs(
    blog: dict[str, Any], token: str, known_ids: set[str], collected_at: str
) -> list[dict[str, Any]]:
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}", "User-Agent": USER_AGENT})
    profile = get_json(session, "https://wikidocs.net/napi/blog/profile/")
    actual_slug = str(profile.get("url", "")).strip("@/")
    if actual_slug != blog["slug"]:
        raise RuntimeError(
            f"@{blog['slug']}: token belongs to @{actual_slug or 'unknown'}, collection stopped"
        )

    result: list[dict[str, Any]] = []
    page = 1
    saw_known = False
    while True:
        payload = get_json(session, f"https://wikidocs.net/napi/blog/list/{page}")
        rows = payload.get("blog_pages")
        if not isinstance(rows, list) or not rows:
            break
        for item in rows:
            post_id = str(item.get("id", "")).strip()
            if not post_id:
                continue
            key = f"WikiDocs:{blog['slug']}:{post_id}"
            if key in known_ids:
                saw_known = True
                continue
            title = " ".join(
                str(first_value(item, ("subject", "title", "name")) or "(제목 없음)").split()
            )
            published_at = normalise_date(
                first_value(item, ("create_date", "created_at", "created", "pub_date"))
            )
            result.append(
                {
                    "key": key,
                    "platform": "WikiDocs",
                    "slug": blog["slug"],
                    "blog_name": blog["blog_name"],
                    "blog_url": blog["blog_url"],
                    "account_masked": blog["account_masked"],
                    "post_id": post_id,
                    "title": title,
                    "post_url": f"https://wikidocs.net/blog/@{blog['slug']}/{post_id}/",
                    "published_at": published_at,
                    "first_seen_at": collected_at,
                    "last_seen_at": collected_at,
                }
            )
        if saw_known:
            break
        page += 1
    print(f"WikiDocs @{blog['slug']}: {len(result)} new post(s), scanned {page} page(s)")
    return result


def fetch_tilnote_page(user_id: str, page: int) -> tuple[int, list[dict[str, Any]], int]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    response = session.get(
        f"https://server.tilnote.io/api/blogs/{user_id}/pages?page={page}",
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data", {})
    return page, list(data.get("pages", [])), int(data.get("lastPage", page))


def collect_tilnote(
    blog: dict[str, Any],
    known_ids: set[str],
    collected_at: str,
    previous_state: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    user_id = str(blog["source_id"])
    last_page = int(
        previous_state.get("total_pages") or blog.get("initial_last_page") or 1
    )
    completed_pages = {
        int(page)
        for page in previous_state.get("completed_pages", [])
        if str(page).isdigit() and 1 <= int(page) <= last_page
    }
    all_rows: list[dict[str, Any]] = []
    missing_pages = [
        page for page in range(1, last_page + 1) if page not in completed_pages
    ]
    pages_to_fetch = sorted(set(missing_pages + [1]))

    failed_pages: list[int] = []
    if pages_to_fetch:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(fetch_tilnote_page, user_id, page): page
                for page in pages_to_fetch
            }
            fetched: dict[int, list[dict[str, Any]]] = {}
            processed = 0
            for future in as_completed(futures):
                source_page = futures[future]
                try:
                    page, rows, observed_last_page = future.result()
                    last_page = max(last_page, observed_last_page)
                    fetched[page] = rows
                    completed_pages.add(page)
                except Exception:
                    failed_pages.append(source_page)
                processed += 1
                if processed % 50 == 0:
                    print(
                        f"Tilnote bootstrap: {processed}/{len(pages_to_fetch)} page attempts",
                        flush=True,
                    )
            for page in sorted(fetched):
                all_rows.extend(fetched[page])

    result: list[dict[str, Any]] = []
    for item in all_rows:
        post_id = str(item.get("_id", "")).strip()
        if not post_id:
            continue
        key = f"Tilnote:{blog['slug']}:{post_id}"
        if key in known_ids:
            continue
        result.append(
            {
                "key": key,
                "platform": "Tilnote",
                "slug": blog["slug"],
                "blog_name": blog["blog_name"],
                "blog_url": blog["blog_url"],
                "account_masked": blog["account_masked"],
                "post_id": post_id,
                "title": " ".join(
                    str(item.get("title") or "(제목 없음)").split()
                ),
                "post_url": f"https://tilnote.io/pages/{post_id}",
                "published_at": normalise_date(item.get("createdAt")),
                "first_seen_at": collected_at,
                "last_seen_at": collected_at,
            }
        )
    remaining = last_page - len(completed_pages)
    state = {
        "total_pages": last_page,
        "completed_pages": sorted(completed_pages),
        "completed_count": len(completed_pages),
        "remaining_pages": remaining,
        "history_complete": remaining == 0,
        "last_attempt_at": collected_at,
    }
    print(
        f"Tilnote @{blog['slug']}: {len(result)} new post(s), "
        f"history {len(completed_pages)}/{last_page} pages, "
        f"{len(failed_pages)} page attempt(s) deferred",
        flush=True,
    )
    return result, state


def main() -> int:
    blogs = load_json(CONFIG_PATH, [])
    existing_doc = load_json(JSON_PATH, {"posts": []})
    existing = list(existing_doc.get("posts", []))
    known_ids = {row["key"] for row in existing if row.get("key")}
    collected_at = utc_now()

    try:
        secrets = json.loads(os.environ.get("WIKIDOCS_BLOGS_JSON", "{}"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("WIKIDOCS_BLOGS_JSON is not valid JSON") from exc

    wiki_blogs = [blog for blog in blogs if blog["platform"] == "WikiDocs"]
    missing = [blog["slug"] for blog in wiki_blogs if not secrets.get(blog["slug"])]
    if missing:
        raise RuntimeError("Missing WikiDocs token(s): " + ", ".join(missing))

    new_posts: list[dict[str, Any]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(
                collect_wikidocs, blog, secrets[blog["slug"]], known_ids, collected_at
            ): blog
            for blog in wiki_blogs
        }
        for future in as_completed(futures):
            blog = futures[future]
            try:
                new_posts.extend(future.result())
            except Exception as exc:
                errors.append(f"{blog['blog_name']}: {exc}")

    tilnote = next(blog for blog in blogs if blog["platform"] == "Tilnote")
    tilnote_state = dict(existing_doc.get("source_state", {}).get("tilnote", {}))
    try:
        tilnote_posts, tilnote_state = collect_tilnote(
            tilnote, known_ids, collected_at, tilnote_state
        )
        new_posts.extend(tilnote_posts)
    except Exception as exc:
        errors.append(f"{tilnote['blog_name']}: {exc}")

    if errors:
        print("Collection completed with deferred source error(s):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)

    merged = {row["key"]: row for row in existing if row.get("key")}
    for row in new_posts:
        merged[row["key"]] = row
    posts = list(merged.values())
    posts.sort(
        key=lambda row: (
            row.get("published_at") or row.get("first_seen_at") or "",
            row.get("key", ""),
        ),
        reverse=True,
    )

    counts = {
        f"{blog['platform']}:{blog['slug']}": sum(
            1
            for row in posts
            if row["platform"] == blog["platform"] and row["slug"] == blog["slug"]
        )
        for blog in blogs
    }
    document = {
        "generated_at": collected_at,
        "total_posts": len(posts),
        "blog_count": len(blogs),
        "counts": counts,
        "source_state": {"tilnote": tilnote_state},
        "collection_errors": errors,
        "posts": posts,
    }
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fields = [
        "platform",
        "blog_name",
        "blog_url",
        "account_masked",
        "title",
        "post_url",
        "published_at",
        "first_seen_at",
    ]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(posts)
    print(f"Saved {len(posts)} total post(s); {len(new_posts)} new.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
