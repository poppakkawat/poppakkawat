"""Tests for the fbscrape parser, client helpers, and scraper.

Run with:  python -m pytest fbscrape/tests/test_fbscrape.py
or simply: python fbscrape/tests/test_fbscrape.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fbscrape.client import Client, normalize_account_url, absolute_url
from fbscrape.parser import parse_timeline
from fbscrape.report import to_json, to_markdown
from fbscrape.scraper import scrape_account

FIXTURE = (Path(__file__).parent / "fixtures" / "timeline.html").read_text(
    encoding="utf-8"
)


def test_normalize_account_url():
    assert normalize_account_url("zuck") == "https://mbasic.facebook.com/zuck"
    assert normalize_account_url("@zuck") == "https://mbasic.facebook.com/zuck"
    assert normalize_account_url("100044") == \
        "https://mbasic.facebook.com/profile.php?id=100044"
    assert normalize_account_url("https://facebook.com/zuck") == \
        "https://mbasic.facebook.com/zuck"
    assert normalize_account_url("https://www.facebook.com/profile.php?id=7") == \
        "https://mbasic.facebook.com/profile.php?id=7"


def test_absolute_url():
    assert absolute_url("/story.php?x=1") == \
        "https://mbasic.facebook.com/story.php?x=1"
    assert absolute_url("https://example.com") == "https://example.com"
    assert absolute_url("") == ""


def test_parse_timeline_finds_all_posts():
    posts, pager = parse_timeline(FIXTURE)
    assert len(posts) == 3
    ids = [p.post_id for p in posts]
    assert ids == ["111", "222", "333"]


def test_parse_post_fields():
    posts, _ = parse_timeline(FIXTURE)
    first = posts[0]
    assert first.author == "Mark Zuckerberg"
    assert "Shipped a new thing today" in first.text
    assert "&" not in first.text or "amp;" not in first.text  # entity decoded
    assert first.timestamp == "Yesterday at 5:03 PM"
    assert first.permalink == \
        "https://mbasic.facebook.com/story.php?story_fbid=111&id=4"
    assert "https://example.com/launch" in first.links


def test_parse_outbound_links():
    posts, _ = parse_timeline(FIXTURE)
    third = posts[2]
    assert third.links == ["https://a.test/x", "https://b.test/y"]
    assert third.permalink.endswith("permalink.php?story_fbid=333&id=4")


def test_parse_finds_pager():
    _, pager = parse_timeline(FIXTURE)
    assert "cursor=ABC123" in pager
    assert pager.startswith("https://mbasic.facebook.com/")


def test_no_footer_boilerplate_in_body():
    posts, _ = parse_timeline(FIXTURE)
    # "Like" / "Full Story" live in the footer and must not pollute the body.
    assert "Like" not in posts[0].text
    assert "Full Story" not in posts[0].text


class _FakeClient(Client):
    """Serves the fixture once, then an empty page, ignoring the network."""

    def __init__(self, pages):
        super().__init__()
        self._pages = list(pages)

    def get(self, url):  # noqa: D102
        return self._pages.pop(0) if self._pages else "<html></html>"


def test_scrape_account_respects_limit():
    client = _FakeClient([FIXTURE])
    posts = scrape_account(
        "zuck", limit=2, client=client, page_delay=0, verbose=False
    )
    assert len(posts) == 2


def test_scrape_account_dedups_across_pages():
    # Same page twice: ids repeat, so no growth beyond the 3 unique posts.
    client = _FakeClient([FIXTURE, FIXTURE])
    posts = scrape_account(
        "zuck", limit=99, client=client, page_delay=0, verbose=False
    )
    assert len(posts) == 3


def test_report_renderers():
    posts, _ = parse_timeline(FIXTURE)
    md = to_markdown("zuck", posts)
    assert "# Facebook posts — zuck" in md
    assert "Mark Zuckerberg" in md
    js = to_json("zuck", posts)
    assert '"account": "zuck"' in js
    assert '"count": 3' in js


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_all())
