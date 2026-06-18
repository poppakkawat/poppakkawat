"""Command-line entry point for fbscrape.

Usage examples:
    python -m fbscrape zuck                       # 25 posts, Markdown to stdout
    python -m fbscrape zuck --limit 50 --json out.json
    python -m fbscrape 100044... --cookies cookies.txt --out posts.md
    FB_COOKIES="c_user=...; xs=..." python -m fbscrape someprofile

``--cookies`` accepts either a path to a file containing the Cookie header
(or a Netscape cookies.txt export) or the raw cookie string itself. Cookies
let you scrape timelines that require a logged-in session — use your own.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .client import Client, FetchError
from .report import to_json, to_markdown
from .scraper import scrape_account


def load_cookies(value: str | None) -> str:
    """Resolve the cookie string from a flag value or the FB_COOKIES env var.

    ``value`` may be a path to a file or the raw cookie header. Files in
    Netscape ``cookies.txt`` format are converted to a ``name=value; ...``
    header.
    """
    if not value:
        return os.environ.get("FB_COOKIES", "").strip()
    p = Path(value)
    if not p.exists():
        return value.strip()  # treat the value itself as the cookie string
    text = p.read_text(encoding="utf-8").strip()
    if "\t" in text and "# " in text or text.startswith("# Netscape"):
        return _parse_netscape(text)
    # A file holding a raw "name=value; name2=value2" header.
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _parse_netscape(text: str) -> str:
    pairs: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 7:
            pairs.append(f"{fields[5]}={fields[6]}")
    return "; ".join(pairs)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="fbscrape",
        description="Scrape recent posts from a single public Facebook account.",
    )
    p.add_argument("account",
                   help="Username, numeric profile id, or profile/page URL")
    p.add_argument("--limit", type=int, default=25,
                   help="Max posts to collect (default: 25)")
    p.add_argument("--max-pages", type=int, default=10,
                   help="Max timeline pages to follow (default: 10)")
    p.add_argument("--cookies", type=str, default=None,
                   help="Cookie string, or path to a cookie/cookies.txt file "
                        "(falls back to the FB_COOKIES env var)")
    p.add_argument("--page-delay", type=float, default=1.5,
                   help="Seconds to wait between page fetches (default: 1.5)")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown",
                   help="Output format for stdout/--out (default: markdown)")
    p.add_argument("--out", type=str, default=None,
                   help="Write the report to this path instead of stdout")
    p.add_argument("--json", dest="json_out", type=str, default=None,
                   help="Also write raw posts as JSON to this path")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress progress messages on stderr")
    args = p.parse_args(argv)

    cookies = load_cookies(args.cookies)
    if not cookies and not args.quiet:
        print("[fbscrape] no cookies provided; only fully public timelines "
              "will be visible.", file=sys.stderr)

    try:
        posts = scrape_account(
            args.account,
            limit=args.limit,
            max_pages=args.max_pages,
            cookies=cookies,
            page_delay=args.page_delay,
            verbose=not args.quiet,
        )
    except FetchError as e:
        print(f"[fbscrape] error: {e}", file=sys.stderr)
        return 1

    body = (to_json(args.account, posts) if args.format == "json"
            else to_markdown(args.account, posts))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body + ("\n" if not body.endswith("\n") else ""),
                            encoding="utf-8")
        if not args.quiet:
            print(f"[fbscrape] wrote {len(posts)} post(s) → {out_path}",
                  file=sys.stderr)
    else:
        print(body)

    if args.json_out:
        Path(args.json_out).write_text(
            to_json(args.account, posts) + "\n", encoding="utf-8")
        if not args.quiet:
            print(f"[fbscrape] wrote JSON → {args.json_out}", file=sys.stderr)

    if not posts:
        return 2  # ran fine, but nothing found
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
