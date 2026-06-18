"""fbscrape — scrape recent posts from a single public Facebook account.

A zero-dependency (stdlib only) scraper that reads an account's timeline
from Facebook's lightweight mobile site (mbasic.facebook.com), parses the
posts out of the HTML, and writes them as Markdown or JSON.

Scope & etiquette
-----------------
This tool targets ONE account at a time and is meant for archiving public
posts (e.g. your own profile, or a public Page you have permission to read).
Facebook's Terms of Service restrict automated access; respect them, the
account's privacy, and rate limits. Many timelines require a logged-in
session — pass cookies via ``--cookies`` / ``FB_COOKIES`` for those.
"""

__version__ = "0.1.0"
