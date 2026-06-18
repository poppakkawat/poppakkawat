"""HTTP client for fetching Facebook's mobile (mbasic) HTML pages.

Stdlib only. Sends a desktop-ish User-Agent, optional auth cookies, and
retries transient failures with exponential backoff — mirroring the style
of the sibling ``polytrack`` client.
"""

from __future__ import annotations

import gzip
import time
import urllib.error
import urllib.parse
import urllib.request

MBASIC = "https://mbasic.facebook.com"

# mbasic serves the lightweight markup this scraper understands. A plain,
# non-bot User-Agent keeps that lightweight variant coming back.
USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
)


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched after all retries."""


def normalize_account_url(account: str) -> str:
    """Turn a username, numeric profile id, or URL into an mbasic timeline URL.

    Examples
    --------
    ``"zuck"``                       -> ``https://mbasic.facebook.com/zuck``
    ``"100044... "`` (all digits)    -> ``.../profile.php?id=100044...``
    ``"https://facebook.com/zuck"``  -> ``https://mbasic.facebook.com/zuck``
    """
    account = account.strip()
    if account.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(account)
        path = parsed.path or "/"
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{MBASIC}{path}{query}"
    account = account.lstrip("@/")
    if account.isdigit():
        return f"{MBASIC}/profile.php?id={account}"
    return f"{MBASIC}/{account}"


def absolute_url(href: str) -> str:
    """Resolve an mbasic-relative href to an absolute facebook.com URL."""
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return f"https:{href}"
    return urllib.parse.urljoin(MBASIC + "/", href.lstrip("/"))


class Client:
    """Fetches mbasic pages, optionally authenticated with cookies."""

    def __init__(
        self,
        cookies: str = "",
        timeout: int = 30,
        retries: int = 4,
        delay: float = 1.0,
    ) -> None:
        self.cookies = cookies.strip()
        self.timeout = timeout
        self.retries = retries
        self.delay = delay

    def _headers(self) -> dict:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
        }
        if self.cookies:
            headers["Cookie"] = self.cookies
        return headers

    def get(self, url: str) -> str:
        """GET ``url`` and return decoded HTML, retrying transient errors."""
        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read()
                    if resp.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    charset = resp.headers.get_content_charset() or "utf-8"
                    return raw.decode(charset, errors="replace")
            except urllib.error.HTTPError as e:
                # 4xx (other than 429) won't fix themselves — fail fast.
                if e.code != 429 and 400 <= e.code < 500:
                    raise FetchError(f"HTTP {e.code} for {url}") from e
                last_err = e
            except Exception as e:  # network hiccup, timeout, rate limit
                last_err = e
            if attempt < self.retries - 1:
                time.sleep(self.delay * (2 ** attempt))
        raise FetchError(f"Failed to GET {url}: {last_err}")
