"""The normalized Post record produced by the scraper."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Post:
    """A single Facebook post, normalized from mbasic HTML.

    Fields are best-effort: Facebook's markup varies and some values
    (notably ``timestamp``) may be missing or only a human-readable string
    such as "Yesterday at 5:03 PM".
    """

    post_id: str
    author: str = ""
    text: str = ""
    timestamp: str = ""          # raw label as shown by Facebook
    permalink: str = ""          # absolute URL to the post
    links: list[str] = field(default_factory=list)  # outbound links in the post

    def to_dict(self) -> dict:
        return {
            "post_id": self.post_id,
            "author": self.author,
            "text": self.text,
            "timestamp": self.timestamp,
            "permalink": self.permalink,
            "links": list(self.links),
        }
