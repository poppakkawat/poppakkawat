# 📰 fbscrape — Single-Account Facebook Post Scraper

A small, **zero-dependency** tool that scrapes recent posts from a **single**
Facebook account and saves them as Markdown or JSON. It reads the lightweight
mobile site (`mbasic.facebook.com`), parses each post's author, text,
timestamp, permalink, and outbound links, and follows the timeline's
"See more posts" pager.

> This is a standalone project that happens to live in the same repository as
> `polytrack`; the two share no code.

> **Use responsibly.** One account at a time, for archiving public posts you're
> allowed to read (e.g. your own profile or a public Page). Facebook's Terms of
> Service restrict automated access — respect them, privacy, and rate limits.

## Quick start

Run from the repository root:

```bash
# 25 most recent posts, Markdown to stdout
python3 -m fbscrape zuck

# By numeric profile id, more posts, save to a file
python3 -m fbscrape 100044000000000 --limit 50 --out posts.md

# Also dump raw posts as JSON
python3 -m fbscrape zuck --json posts.json

# JSON only, to stdout
python3 -m fbscrape https://facebook.com/zuck --format json
```

The `account` argument accepts a **username**, a **numeric profile id**, or a
**full profile/page URL**.

## Authenticated scraping (cookies)

Many timelines only render when you're logged in. Provide your own session
cookies via `--cookies` (a raw `name=value; ...` header, or a path to a file —
including a Netscape `cookies.txt` export), or the `FB_COOKIES` env var:

```bash
FB_COOKIES="c_user=...; xs=..." python3 -m fbscrape zuck
python3 -m fbscrape zuck --cookies cookies.txt
```

Without cookies, only fully public content is visible, and Facebook may reject
the request outright (the tool reports this clearly).

## Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--limit` | 25 | Max posts to collect |
| `--max-pages` | 10 | Max timeline pages to follow |
| `--cookies` | — | Cookie string or file (falls back to `FB_COOKIES`) |
| `--page-delay` | 1.5 | Seconds between page fetches (be polite) |
| `--format` | markdown | `markdown` or `json` for stdout/`--out` |
| `--out` | — | Write the report to a file instead of stdout |
| `--json` | — | Also write raw posts as JSON to this path |
| `--quiet` | off | Suppress progress on stderr |

## Layout

```
fbscrape/
  client.py     # mbasic HTTP fetch: User-Agent, cookies, backoff retries
  parser.py     # tolerant HTML parser → Post records + pager URL
  scraper.py    # orchestration: paginate, de-dup, honor --limit
  post.py       # the normalized Post dataclass
  report.py     # Markdown / JSON rendering
  cli.py        # command-line interface
  tests/
    test_fbscrape.py        # offline tests against a saved HTML fixture
    fixtures/timeline.html
```

Run the tests from the repo root with `python3 fbscrape/tests/test_fbscrape.py`
(or `pytest fbscrape/tests`).

## Notes & limits

- Facebook's markup changes often; the parser is **best-effort** and leaves
  fields empty rather than failing. Timestamps are the human-readable labels
  Facebook shows ("Yesterday at 5:03 PM"), not normalized dates.
- This scrapes one account's **timeline**; it does not crawl comments,
  reactions, or friends. Respect Facebook's ToS and applicable laws.
