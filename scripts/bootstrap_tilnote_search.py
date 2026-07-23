#!/usr/bin/env python3
"""Bootstrap Tilnote history through its public search index.

The normal profile pagination becomes very slow on deep pages. This maintenance
collector fans out over terms found in already-discovered titles/content and
deduplicates search results by public page ID. It never reads credentials.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "posts.json"
CSV_PATH = ROOT / "data" / "posts.csv"
SEARCH_URL = "https://server.tilnote.io/api/pages/public/search"
USER_ID = "67262953c0c5c088c26e4fd0"
USER_AGENT = "Blog-Post-Dashboard/1.0 (+GitHub Actions)"
TOKEN_RE = re.compile(r"[\uac00-\ud7a3]{2,}|[A-Za-z][A-Za-z0-9+.-]{1,}")
STOPWORDS = {
    "가지",
    "제목",
    "없음",
    "위한",
    "통해",
    "대한",
    "하는",
    "있는",
    "없는",
    "그리고",
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text or "")
        if token.lower() not in STOPWORDS and len(token) <= 40
    }


def post_search(term: str, page: int, attempts: int = 2) -> dict[str, Any]:
    for attempt in range(attempts):
        try:
            response = requests.post(
                SEARCH_URL,
                json={"query": term, "page": page, "limit": 50, "authorId": USER_ID},
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            if attempt == attempts - 1:
                raise
            time.sleep(1.5)
    raise RuntimeError("unreachable")


def search_term(term: str) -> tuple[str, list[dict[str, Any]]]:
    first = post_search(term, 1)
    rows = list(first.get("data", []))
    pagination = first.get("pagination", {})
    total = min(int(pagination.get("total", len(rows))), 200)
    page_count = min(4, max(1, math.ceil(total / 50)))
    for page in range(2, page_count + 1):
        rows.extend(post_search(term, page).get("data", []))
    return term, rows


def save_document(document: dict[str, Any]) -> None:
    posts = document["posts"]
    document["total_posts"] = len(posts)
    document["counts"] = {
        key: sum(
            1
            for row in posts
            if f"{row['platform']}:{row['slug']}" == key
        )
        for key in {
            f"{row['platform']}:{row['slug']}" for row in posts
        }
    }
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terms", type=int, default=250, help="maximum terms per round")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    document = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    merged = {row["key"]: row for row in document.get("posts", [])}
    state = document.setdefault("source_state", {}).setdefault("tilnote", {})
    queried = set(state.get("search_terms_completed", []))
    term_counts: Counter[str] = Counter()
    for row in merged.values():
        if row.get("platform") == "Tilnote":
            term_counts.update(tokens(row.get("title", "")))

    for round_number in range(1, args.rounds + 1):
        candidates = [
            term
            for term, _ in sorted(
                term_counts.items(), key=lambda item: (item[1], -len(item[0]), item[0])
            )
            if term not in queried
        ][: args.terms]
        if not candidates:
            print("No new Tilnote search terms remain.")
            break

        before = sum(1 for row in merged.values() if row.get("platform") == "Tilnote")
        failed: list[str] = []
        discovered_terms: Counter[str] = Counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(search_term, term): term for term in candidates}
            processed = 0
            for future in as_completed(futures):
                source_term = futures[future]
                try:
                    term, rows = future.result()
                    queried.add(term)
                    for item in rows:
                        post_id = str(item.get("_id", "")).strip()
                        if not post_id:
                            continue
                        key = f"Tilnote:knarchive:{post_id}"
                        stamp = now()
                        current = merged.get(key, {})
                        merged[key] = {
                            "key": key,
                            "platform": "Tilnote",
                            "slug": "knarchive",
                            "blog_name": "knarchive",
                            "blog_url": "https://tilnote.io/@knarchive",
                            "account_masked": "",
                            "post_id": post_id,
                            "title": " ".join(
                                str(item.get("title") or "(제목 없음)").split()
                            ),
                            "post_url": f"https://tilnote.io/pages/{post_id}",
                            "published_at": str(
                                item.get("publishedAt") or item.get("createdAt") or ""
                            ),
                            "first_seen_at": current.get("first_seen_at") or stamp,
                            "last_seen_at": stamp,
                        }
                        discovered_terms.update(
                            tokens(
                                f"{item.get('title', '')} "
                                f"{item.get('content', '')} "
                                f"{item.get('summary', '')}"
                            )
                        )
                except Exception:
                    failed.append(source_term)
                processed += 1
                if processed % 25 == 0:
                    print(
                        f"Search bootstrap round {round_number}: "
                        f"{processed}/{len(candidates)} terms",
                        flush=True,
                    )

        term_counts.update(discovered_terms)
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
        state["search_terms_completed"] = sorted(queried)
        state["search_terms_discovered"] = len(term_counts)
        state["search_last_attempt_at"] = now()
        state["search_failed_terms"] = failed
        after = sum(1 for row in posts if row.get("platform") == "Tilnote")
        save_document(document)
        print(
            f"Round {round_number}: {after - before} new Tilnote posts, "
            f"{after} total, {len(queried)} terms completed, "
            f"{len(failed)} terms deferred.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
