"""Render scraped posts as Markdown or JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .post import Post


def to_json(account: str, posts: list[Post]) -> str:
    payload = {
        "account": account,
        "scraped_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(posts),
        "posts": [p.to_dict() for p in posts],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def to_markdown(account: str, posts: list[Post]) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Facebook posts — {account}",
        "",
        f"_Scraped {day} · {len(posts)} post(s)_",
        "",
    ]
    if not posts:
        lines.append("_No posts found. The account may be private, empty, or "
                     "require a logged-in session (pass --cookies)._")
        return "\n".join(lines)

    for i, p in enumerate(posts, 1):
        header = f"## {i}."
        if p.timestamp:
            header += f" {p.timestamp}"
        lines.append(header)
        if p.author:
            lines.append(f"**{p.author}**")
            lines.append("")
        lines.append(p.text or "_(no text)_")
        lines.append("")
        if p.links:
            lines.append("Links: " + ", ".join(f"<{u}>" for u in p.links))
            lines.append("")
        if p.permalink:
            lines.append(f"[Permalink]({p.permalink})")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
