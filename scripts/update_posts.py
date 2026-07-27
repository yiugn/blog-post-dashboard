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
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "blogs.json"
JSON_PATH = ROOT / "data" / "posts.json"
CSV_PATH = ROOT / "data" / "posts.csv"
USER_AGENT = "Blog-Post-Dashboard/1.0 (+GitHub Actions)"
TIMEOUT = 40
KST = ZoneInfo("Asia/Seoul")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def kst_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(KST).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 else ""


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


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
                    "views_total": None,
                    "views_checked_at": "",
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
    history_complete = bool(previous_state.get("history_complete"))
    missing_pages = [page for page in range(1, last_page + 1) if page not in completed_pages]
    pages_to_fetch = (
        list(range(1, last_page + 1))
        if history_complete
        else sorted(set(missing_pages + [1]))
    )

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
                "views_total": safe_int(item.get("view")),
                "views_checked_at": collected_at,
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
        "last_full_refresh_at": (
            collected_at
            if history_complete and not failed_pages
            else previous_state.get("last_full_refresh_at", "")
        ),
    }
    print(
        f"Tilnote @{blog['slug']}: {len(result)} refreshed post row(s), "
        f"history {len(completed_pages)}/{last_page} pages, "
        f"{len(failed_pages)} page attempt(s) deferred",
        flush=True,
    )
    return result, state


def finalise_post(
    row: dict[str, Any],
    previous: dict[str, Any] | None,
    previous_stats_date: str,
    today: str,
    collected_at: str,
) -> dict[str, Any]:
    result = dict(row)
    previous = previous or {}
    result["first_seen_at"] = previous.get("first_seen_at") or result.get("first_seen_at") or collected_at
    result["last_seen_at"] = result.get("last_seen_at") or previous.get("last_seen_at") or collected_at

    published_date = kst_date(result.get("published_at"))
    if published_date:
        result["post_date"] = published_date
        result["post_date_source"] = "published"
    else:
        result["post_date"] = kst_date(result.get("first_seen_at"))
        result["post_date_source"] = "first_seen"

    current_total = safe_int(result.get("views_total"))
    previous_total = safe_int(previous.get("views_total"))
    if current_total is None:
        result["views_total"] = None
        result["views_day_start"] = None
        result["views_today"] = None
        result["views_checked_at"] = ""
        return result

    result["views_total"] = current_total
    if previous_stats_date == today:
        baseline = safe_int(previous.get("views_day_start"))
        if baseline is None:
            baseline = 0 if result["post_date"] == today and not previous_total else current_total
    else:
        baseline = previous_total
        if baseline is None:
            baseline = 0 if result["post_date"] == today else current_total
    if current_total < baseline:
        baseline = current_total
    result["views_day_start"] = baseline
    result["views_today"] = current_total - baseline
    result["views_checked_at"] = result.get("views_checked_at") or previous.get("views_checked_at") or ""
    return result


def main() -> int:
    blogs = load_json(CONFIG_PATH, [])
    existing_doc = load_json(JSON_PATH, {"posts": []})
    existing = list(existing_doc.get("posts", []))
    existing_by_key = {row["key"]: row for row in existing if row.get("key")}
    known_ids = {row["key"] for row in existing if row.get("key")}
    collected_at = utc_now()
    today = kst_date(collected_at)
    previous_stats_date = str(existing_doc.get("stats_date") or "")

    try:
        secrets = json.loads(os.environ.get("WIKIDOCS_BLOGS_JSON", "{}"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("WIKIDOCS_BLOGS_JSON is not valid JSON") from exc

    wiki_blogs = [blog for blog in blogs if blog["platform"] == "WikiDocs"]
    missing = [blog["slug"] for blog in wiki_blogs if not secrets.get(blog["slug"])]
    if missing:
        raise RuntimeError("Missing WikiDocs token(s): " + ", ".join(missing))

    collected_rows: list[dict[str, Any]] = []
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
                collected_rows.extend(future.result())
            except Exception as exc:
                errors.append(f"{blog['blog_name']}: {exc}")

    tilnote = next(blog for blog in blogs if blog["platform"] == "Tilnote")
    tilnote_state = dict(existing_doc.get("source_state", {}).get("tilnote", {}))
    try:
        tilnote_posts, tilnote_state = collect_tilnote(
            tilnote, known_ids, collected_at, tilnote_state
        )
        collected_rows.extend(tilnote_posts)
    except Exception as exc:
        errors.append(f"{tilnote['blog_name']}: {exc}")

    if errors:
        print("Collection completed with deferred source error(s):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)

    merged = {key: dict(row) for key, row in existing_by_key.items()}
    for row in collected_rows:
        previous = existing_by_key.get(row["key"], {})
        merged[row["key"]] = {**previous, **row}
    posts = [
        finalise_post(
            row,
            existing_by_key.get(key),
            previous_stats_date,
            today,
            collected_at,
        )
        for key, row in merged.items()
    ]
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
    blog_stats: dict[str, dict[str, Any]] = {}
    for blog in blogs:
        key = f"{blog['platform']}:{blog['slug']}"
        rows = [
            row
            for row in posts
            if row["platform"] == blog["platform"] and row["slug"] == blog["slug"]
        ]
        supported = [row for row in rows if safe_int(row.get("views_total")) is not None]
        blog_stats[key] = {
            "platform": blog["platform"],
            "slug": blog["slug"],
            "blog_name": blog["blog_name"],
            "posts_total": len(rows),
            "posts_today": sum(1 for row in rows if row.get("post_date") == today),
            "views_total": (
                sum(int(row["views_total"]) for row in supported) if supported else None
            ),
            "views_today": (
                sum(int(row.get("views_today") or 0) for row in supported)
                if supported
                else None
            ),
            "view_posts": len(supported),
            "views_supported": len(supported) == len(rows) and bool(rows),
            "views_checked_at": max(
                (str(row.get("views_checked_at") or "") for row in supported),
                default="",
            ),
        }
    view_rows = [row for row in posts if safe_int(row.get("views_total")) is not None]
    view_blog_count = sum(1 for stat in blog_stats.values() if stat["view_posts"] > 0)
    document = {
        "generated_at": collected_at,
        "stats_date": today,
        "total_posts": len(posts),
        "blog_count": len(blogs),
        "counts": counts,
        "blog_stats": blog_stats,
        "views": {
            "total": sum(int(row["views_total"]) for row in view_rows),
            "today": sum(int(row.get("views_today") or 0) for row in view_rows),
            "supported_posts": len(view_rows),
            "total_posts": len(posts),
            "supported_blogs": view_blog_count,
            "total_blogs": len(blogs),
            "checked_at": max(
                (str(row.get("views_checked_at") or "") for row in view_rows),
                default="",
            ),
            "note": "Tilnote API 제공 범위 합계. WikiDocs 공식 API는 조회수를 제공하지 않습니다.",
        },
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
        "post_date",
        "post_date_source",
        "published_at",
        "views_total",
        "views_today",
        "views_checked_at",
        "first_seen_at",
    ]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(posts)
    new_count = sum(1 for row in collected_rows if row["key"] not in existing_by_key)
    print(
        f"Saved {len(posts)} total post(s); {new_count} new; "
        f"{len(view_rows)} row(s) with view metrics."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
