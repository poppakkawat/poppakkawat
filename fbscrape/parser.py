"""Parse posts out of an mbasic.facebook.com timeline page.

Facebook's mobile markup wraps each post in an ``<article>`` (or a
``<div role="article">``) that carries a ``data-ft`` JSON blob with the
post id. Inside, the rough layout is::

    <article data-ft='{"top_level_post_id": "123", ...}'>
      <header><h3><a>Author Name</a></h3></header>
      ...post body text...
      <footer>
        <abbr>Yesterday at 5:03 PM</abbr>
        <a href="/story.php?story_fbid=123&id=456">Full Story</a>
      </footer>
    </article>

The parser is deliberately tolerant: any field it can't find is left empty
rather than raising. It also surfaces the timeline's "See more posts" pager
link so the scraper can follow pagination.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from .client import absolute_url
from .post import Post

# Hrefs that point at an individual post (its permalink).
_PERMALINK_RE = re.compile(
    r"(story\.php\?|permalink\.php\?|/posts/|story_fbid=|/photo\.php\?)"
)
# Visible text on the timeline's next-page link.
_PAGER_TEXT_RE = re.compile(r"see more posts|show more|see more stories", re.I)

_VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}
_SKIP_TEXT = {"script", "style"}


def _post_id_from_dataft(data_ft: str) -> str:
    """Pull the post id out of a ``data-ft`` attribute value."""
    if not data_ft:
        return ""
    try:
        obj = json.loads(data_ft)
    except (ValueError, TypeError):
        return ""
    for key in ("mf_story_key", "top_level_post_id", "tl_objid"):
        if obj.get(key):
            return str(obj[key])
    return ""


class _TimelineParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.posts: list[Post] = []
        self.pager_url: str = ""

        self._container_tag: str | None = None
        self._nest = 0                  # depth of the open post container
        self._post_id = ""
        self._author_parts: list[str] = []
        self._body_parts: list[str] = []
        self._ts = ""
        self._links: list[str] = []
        self._permalink = ""

        self._in_header = False         # inside <h3> (author)
        self._in_abbr = False           # inside <abbr> (timestamp)
        self._section = "pre"           # pre -> body -> footer
        self._href_stack: list[str] = []  # hrefs of currently-open <a> tags
        self._anchor_text: list[str] = []  # text of the innermost open <a>
        self._pager_pending: str | None = None  # href of the <a> being read
        self._pager_pending_text: list[str] = []

    # -- container detection -------------------------------------------------
    @staticmethod
    def _is_container(tag: str, attrs: dict) -> bool:
        if tag == "article":
            return True
        if tag == "div" and attrs.get("role") == "article":
            return True
        if tag in ("div", "section") and "top_level_post_id" in attrs.get("data-ft", ""):
            return True
        return False

    def handle_starttag(self, tag, attrs):  # noqa: D102
        a = dict(attrs)

        # Track the pager link even when we're between posts.
        if tag == "a" and a.get("href"):
            self._maybe_pager_open(a["href"])

        if self._container_tag is None:
            if self._is_container(tag, a):
                self._open_post(tag, a)
            return

        # We're inside a post container.
        if tag == self._container_tag and tag not in _VOID:
            self._nest += 1

        if tag == "h3":
            self._in_header = True
        elif tag == "abbr":
            self._in_abbr = True
            self._section = "footer"      # timestamp marks the footer
        elif tag == "a":
            href = a.get("href", "")
            self._href_stack.append(href)
            self._anchor_text = []
            if href and _PERMALINK_RE.search(href):
                if not self._permalink:
                    self._permalink = absolute_url(href.split("&refid")[0])
            elif href.startswith(("http://", "https://", "//")):
                self._links.append(absolute_url(href))

    def handle_endtag(self, tag):  # noqa: D102
        if self._container_tag is None:
            self._pager_text_close(tag)
            return

        if tag == "h3":
            self._in_header = False
            if self._section == "pre":
                self._section = "body"
        elif tag == "abbr":
            self._in_abbr = False
        elif tag == "a":
            if self._href_stack:
                self._href_stack.pop()

        self._pager_text_close(tag)

        if tag == self._container_tag and tag not in _VOID:
            self._nest -= 1
            if self._nest <= 0:
                self._close_post()

    def handle_data(self, data):  # noqa: D102
        text = data.strip()
        if not text:
            return
        if self.lasttag in _SKIP_TEXT:
            return

        # Pager-link text accumulates whether or not we're inside a post.
        if self._pager_pending is not None:
            self._pager_pending_text.append(text)

        if self._container_tag is None:
            return
        if self._href_stack:
            self._anchor_text.append(text)
        if self._in_abbr:
            self._ts = (self._ts + " " + text).strip()
        elif self._in_header:
            self._author_parts.append(text)
        elif self._section in ("pre", "body"):
            self._body_parts.append(text)

    # -- pager handling ------------------------------------------------------
    def _maybe_pager_open(self, href: str) -> None:
        self._pager_pending = href
        self._pager_pending_text = []

    def _pager_text_close(self, tag: str) -> None:
        if tag != "a" or self._pager_pending is None:
            return
        text = " ".join(self._pager_pending_text)
        href = self._pager_pending
        self._pager_pending = None
        self._pager_pending_text = []
        if not self.pager_url and (
            _PAGER_TEXT_RE.search(text) or "cursor=" in href
        ):
            # The pager link must not be a single-post permalink.
            if not _PERMALINK_RE.search(href) or "cursor=" in href:
                self.pager_url = absolute_url(href)

    # -- post lifecycle ------------------------------------------------------
    def _open_post(self, tag: str, attrs: dict) -> None:
        self._container_tag = tag
        self._nest = 1
        self._post_id = _post_id_from_dataft(attrs.get("data-ft", ""))
        self._author_parts = []
        self._body_parts = []
        self._ts = ""
        self._links = []
        self._permalink = ""
        self._in_header = False
        self._in_abbr = False
        self._section = "pre"
        self._href_stack = []

    def _close_post(self) -> None:
        body = re.sub(r"\s+\n", "\n", " ".join(self._body_parts)).strip()
        body = re.sub(r"[ \t]{2,}", " ", body)
        post = Post(
            post_id=self._post_id or self._permalink or f"post-{len(self.posts)}",
            author=" ".join(self._author_parts).strip(),
            text=body,
            timestamp=self._ts.strip(),
            permalink=self._permalink,
            links=list(dict.fromkeys(self._links)),  # de-dup, keep order
        )
        # Skip empty shells (e.g. ad/suggested containers with no content).
        if post.text or post.permalink or self._ts:
            self.posts.append(post)
        self._container_tag = None
        self._nest = 0


def parse_timeline(html: str) -> tuple[list[Post], str]:
    """Parse posts and the next-page URL from a timeline HTML page.

    Returns ``(posts, pager_url)`` where ``pager_url`` is ``""`` when there
    is no further page to follow.
    """
    p = _TimelineParser()
    p.feed(html)
    return p.posts, p.pager_url
