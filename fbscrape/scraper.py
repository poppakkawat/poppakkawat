"""Orchestrate scraping a single account's timeline, following pagination."""

from __future__ import annotations

import sys
import time

from .client import Client, normalize_account_url
from .parser import parse_timeline
from .post import Post


def scrape_account(
    account: str,
    *,
    limit: int = 25,
    max_pages: int = 10,
    cookies: str = "",
    page_delay: float = 1.5,
    client: Client | None = None,
    verbose: bool = True,
) -> list[Post]:
    """Scrape up to ``limit`` posts from a single Facebook ``account``.

    ``account`` may be a username, a numeric profile id, or a full URL.
    Pagination follows the timeline's "See more posts" link up to
    ``max_pages`` times. A polite ``page_delay`` (seconds) is inserted
    between page fetches.

    Returns posts newest-first (timeline order), de-duplicated by id.
    """
    client = client or Client(cookies=cookies)
    url = normalize_account_url(account)

    posts: list[Post] = []
    seen: set[str] = set()
    for page in range(max_pages):
        if verbose:
            print(f"[fbscrape] fetching page {page + 1}: {url}", file=sys.stderr)
        html = client.get(url)
        page_posts, pager_url = parse_timeline(html)

        new_count = 0
        for post in page_posts:
            if post.post_id in seen:
                continue
            seen.add(post.post_id)
            posts.append(post)
            new_count += 1
            if len(posts) >= limit:
                break

        if verbose:
            print(f"[fbscrape]   parsed {len(page_posts)} post(s), "
                  f"{new_count} new (total {len(posts)})", file=sys.stderr)

        if len(posts) >= limit or not pager_url or new_count == 0:
            break
        url = pager_url
        if page_delay:
            time.sleep(page_delay)

    return posts[:limit]
