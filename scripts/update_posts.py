#!/usr/bin/env python3
"""Collect public post metadata without ever writing credentials to disk."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "blogs.json"
JSON_PATH = ROOT / "data" / "posts.json"
CSV_PATH = ROOT / "data" / "posts.csv"
USER_AGENT = "Blog-Post-Dashboard/1.0 (+GitHub Actions)"
TIMEOUT = 40
KST = ZoneInfo("Asia/Seoul")
WIKIDOCS_BLOG = "https://wikidocs.net/blog"
WIKIDOCS_DASHBOARD_URL = os.environ.get(
    "WIKIDOCS_DASHBOARD_URL",
    "https://yiugn.github.io/wikidocs-dashboard/data/dashboard.json",
)
WIKIDOCS_SNAPSHOTS_URL = os.environ.get(
    "WIKIDOCS_SNAPSHOTS_URL",
    "https://raw.githubusercontent.com/yiugn/wikidocs-dashboard/main/data/snapshots.jsonl",
)


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


def get_latest_jsonl(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    for line in reversed(response.text.splitlines()):
        if line.strip():
            return json.loads(line)
    raise RuntimeError(f"{url} did not contain JSONL rows")


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


def parse_wikidocs_public_page(html: str, slug: str, page_no: int) -> tuple[int, list[dict[str, Any]]]:
    soup = BeautifulSoup(html, "html.parser")
    max_page = page_no
    for anchor in soup.select(".page-link"):
        try:
            max_page = max(max_page, int(anchor.get("data-page") or 0))
        except ValueError:
            continue

    posts: list[dict[str, Any]] = []
    href_re = re.compile(rf"^/blog/@{re.escape(slug)}/(\d+)/")
    for anchor in soup.find_all("a", href=True):
        match = href_re.match(anchor["href"])
        if not match:
            continue
        card = anchor.select_one("div.rounded-md") or anchor
        meta = card.select_one("div.mt-4.text-sm")
        meta_text = meta.get_text(" ", strip=True) if meta else ""
        numbers = [int(num.replace(",", "")) for num in re.findall(r"\d[\d,]*", meta_text)]
        if len(numbers) < 3:
            continue
        title_el = card.select_one("h2")
        posts.append(
            {
                "post_id": str(match.group(1)),
                "title": " ".join((title_el.get_text(" ", strip=True) if title_el else "").split()),
                "post_url": f"{WIKIDOCS_BLOG}/@{slug}/{match.group(1)}/",
                "thumbnail_url": urljoin("https://wikidocs.net", (card.select_one("img") or {}).get("src", "")),
                "views_total": numbers[-3],
                "likes": numbers[-2],
                "comments": numbers[-1],
                "source_page": page_no,
            }
        )
    return max_page, posts


def scrape_wikidocs_views(slug: str, delay: float = 0.12) -> dict[str, dict[str, Any]]:
    session = curl_requests.Session(impersonate="chrome124", verify=False)
    session.headers.update({"User-Agent": USER_AGENT})
    collected: dict[str, dict[str, Any]] = {}
    page_no = 1
    discovered_pages = 1

    while True:
        url = f"{WIKIDOCS_BLOG}/@{quote(slug)}/?page={page_no}&sort=recent"
        response = session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        html = response.content.decode("utf-8", "replace")
        discovered_pages, posts = parse_wikidocs_public_page(html, slug, page_no)
        for post in posts:
            collected[post["post_id"]] = post
        if page_no >= discovered_pages:
            break
        page_no += 1
        time.sleep(delay)

    return collected


def collect_wikidocs_dashboard_snapshot(
    blogs: list[dict[str, Any]], collected_at: str
) -> list[dict[str, Any]]:
    """Reuse the primary Wikidocs analytics snapshot when Actions cannot scrape pages."""

    wiki_by_slug = {
        blog["slug"]: blog for blog in blogs if blog.get("platform") == "WikiDocs"
    }
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    source = "raw snapshots"
    daily_by_post: dict[str, int] = {}
    try:
        payload = get_latest_jsonl(
            session, f"{WIKIDOCS_SNAPSHOTS_URL}?t={int(time.time())}"
        )
        try:
            summary = get_json(session, f"{WIKIDOCS_DASHBOARD_URL}?t={int(time.time())}")
            for blog_summary in summary.get("blogs", []):
                if not isinstance(blog_summary, dict):
                    continue
                summary_slug = str(
                    first_value(blog_summary, ("slug", "blog_slug", "name_slug")) or ""
                ).strip()
                if not summary_slug:
                    continue
                for post_summary in blog_summary.get("posts", []):
                    if not isinstance(post_summary, dict):
                        continue
                    summary_post_id = str(
                        first_value(post_summary, ("id", "post_id")) or ""
                    ).strip()
                    daily_views = safe_int(
                        first_value(post_summary, ("daily_views", "views_today"))
                    )
                    if summary_post_id and daily_views is not None:
                        daily_by_post[f"{summary_slug}:{summary_post_id}"] = daily_views
        except Exception as exc:  # noqa: BLE001 - cumulative snapshot is still useful.
            print(f"WikiDocs daily summary deferred ({exc})")
    except Exception as exc:  # noqa: BLE001 - fall back to the Pages summary.
        print(f"WikiDocs raw snapshot deferred ({exc}); using dashboard summary")
        source = "dashboard summary"
        payload = get_json(session, f"{WIKIDOCS_DASHBOARD_URL}?t={int(time.time())}")
    snapshot_at = str(
        first_value(
            payload,
            ("latest_snapshot_at", "static_generated_at", "catalog_updated_at"),
        )
        or collected_at
    )

    rows: list[dict[str, Any]] = []
    for blog_snapshot in payload.get("blogs", []):
        if not isinstance(blog_snapshot, dict):
            continue
        slug = str(
            first_value(blog_snapshot, ("slug", "blog_slug", "name_slug")) or ""
        ).strip()
        blog = wiki_by_slug.get(slug)
        if not blog:
            continue
        for post in blog_snapshot.get("posts", []):
            if not isinstance(post, dict):
                continue
            post_id = str(first_value(post, ("id", "post_id")) or "").strip()
            if not post_id:
                continue
            views_total = safe_int(first_value(post, ("views", "views_total")))
            daily_views = safe_int(first_value(post, ("daily_views", "views_today")))
            if daily_views is None:
                daily_views = daily_by_post.get(f"{slug}:{post_id}")
            rows.append(
                {
                    "key": f"WikiDocs:{slug}:{post_id}",
                    "platform": "WikiDocs",
                    "slug": slug,
                    "blog_name": blog["blog_name"],
                    "blog_url": blog["blog_url"],
                    "account_masked": blog["account_masked"],
                    "post_id": post_id,
                    "title": " ".join(
                        str(first_value(post, ("title", "subject")) or "(untitled)").split()
                    ),
                    "post_url": str(post.get("url") or f"{WIKIDOCS_BLOG}/@{slug}/{post_id}/"),
                    "thumbnail_url": str(post.get("thumbnail_url") or ""),
                    "views_total": views_total,
                    "views_today": daily_views,
                    "_views_today_override": daily_views,
                    "views_checked_at": snapshot_at if views_total is not None else "",
                    "first_seen_at": collected_at,
                    "last_seen_at": collected_at,
                }
            )

    print(
        f"WikiDocs {source}: {len(rows)} row(s), "
        f"{sum(1 for row in rows if safe_int(row.get('views_total')) is not None)} "
        "with view metrics"
    )
    return rows


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

    result_by_key: dict[str, dict[str, Any]] = {}
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
            api_views = safe_int(
                first_value(
                    item,
                    (
                        "view",
                        "views",
                        "view_count",
                        "views_count",
                        "hit",
                        "hits",
                        "hit_count",
                        "read_count",
                    ),
                )
            )
            result_by_key[key] = {
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
                "views_total": api_views,
                "views_checked_at": collected_at if api_views is not None else "",
                "first_seen_at": collected_at,
                "last_seen_at": collected_at,
            }
        if saw_known:
            break
        page += 1

    try:
        view_rows = scrape_wikidocs_views(blog["slug"])
    except Exception as exc:  # noqa: BLE001 - keep post metadata if public views are blocked.
        print(f"WikiDocs @{blog['slug']}: public view scrape deferred ({exc})", file=sys.stderr)
        view_rows = {}
    for post_id, view_data in view_rows.items():
        key = f"WikiDocs:{blog['slug']}:{post_id}"
        current = result_by_key.get(key, {})
        result_by_key[key] = {
            **current,
            "key": key,
            "platform": "WikiDocs",
            "slug": blog["slug"],
            "blog_name": blog["blog_name"],
            "blog_url": blog["blog_url"],
            "account_masked": blog["account_masked"],
            "post_id": post_id,
            "title": current.get("title") or view_data.get("title") or "(제목 없음)",
            "post_url": current.get("post_url") or view_data.get("post_url") or f"{WIKIDOCS_BLOG}/@{blog['slug']}/{post_id}/",
            "views_total": safe_int(view_data.get("views_total")),
            "views_checked_at": collected_at,
            "first_seen_at": current.get("first_seen_at") or collected_at,
            "last_seen_at": collected_at,
        }

    print(
        f"WikiDocs @{blog['slug']}: {len(result_by_key)} row(s), "
        f"{len(view_rows)} with view metrics, scanned {page} API page(s)"
    )
    return list(result_by_key.values())


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
    _, first_rows, last_page = fetch_tilnote_page(user_id, 1)
    completed_pages = {
        int(page)
        for page in previous_state.get("completed_pages", [])
        if str(page).isdigit() and 1 <= int(page) <= last_page
    }
    completed_pages.add(1)
    all_rows: list[dict[str, Any]] = list(first_rows)
    history_complete = bool(previous_state.get("history_complete"))
    # View counts are mutable. Refresh every Tilnote page on every run instead
    # of only filling missing history pages, otherwise the dashboard can show a
    # tiny subset of posts as the "live" view total during bootstrap.
    pages_to_fetch = list(range(2, last_page + 1))

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
                    if observed_last_page != last_page:
                        print(
                            f"Tilnote page count changed during collection: "
                            f"{last_page} -> {observed_last_page}",
                            flush=True,
                        )
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
    next_history_complete = remaining == 0
    state = {
        "total_pages": last_page,
        "completed_pages": sorted(completed_pages),
        "completed_count": len(completed_pages),
        "remaining_pages": remaining,
        "history_complete": next_history_complete,
        "last_attempt_at": collected_at,
        "last_full_refresh_at": (
            collected_at
            if next_history_complete and not failed_pages
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
    today_override = safe_int(result.pop("_views_today_override", None))
    if current_total is None:
        result["views_total"] = None
        result["views_day_start"] = None
        result["views_today"] = None
        result["views_checked_at"] = ""
        return result

    result["views_total"] = current_total
    if today_override is not None:
        today_override = min(today_override, current_total)
        result["views_day_start"] = current_total - today_override
        result["views_today"] = today_override
        result["views_checked_at"] = result.get("views_checked_at") or previous.get("views_checked_at") or ""
        return result

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

    collected_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    wiki_blogs = [blog for blog in blogs if blog["platform"] == "WikiDocs"]
    try:
        collected_rows.extend(collect_wikidocs_dashboard_snapshot(blogs, collected_at))
    except Exception as exc:
        errors.append(f"WikiDocs dashboard snapshot: {exc}")
        missing = [blog["slug"] for blog in wiki_blogs if not secrets.get(blog["slug"])]
        if missing:
            raise RuntimeError("Missing WikiDocs token(s): " + ", ".join(missing)) from exc
        # Fallback for environments where the primary dashboard snapshot is unavailable.
        with ThreadPoolExecutor(max_workers=1) as pool:
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
                except Exception as source_exc:
                    errors.append(f"{blog['blog_name']}: {source_exc}")

    tilnote_state = dict(existing_doc.get("source_state", {}).get("tilnote", {}))
    if os.environ.get("SKIP_TILNOTE_REFRESH") == "1":
        print("Tilnote refresh skipped by SKIP_TILNOTE_REFRESH=1")
    else:
        tilnote = next(blog for blog in blogs if blog["platform"] == "Tilnote")
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
            "note": "WikiDocs dashboard snapshot plus Tilnote API coverage.",
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
