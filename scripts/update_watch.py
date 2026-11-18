#!/usr/bin/env python3
"""Refresh the Watch band with the newest YouTube upload and Twitch clip.

Both sources are read at build time in .github/workflows/pages.yml:

* YouTube's public channel feed lists recent uploads, no API key needed.
* Twitch has no keyless REST endpoint, so this uses the same read-only GraphQL
  query the Twitch web player uses, with Twitch's public web client id.

The page itself stays static: the embeds are plain iframes. If either source
changes shape or is unreachable the script exits non-zero and the workflow
publishes the previous markup.

    python3 scripts/update_watch.py _site/index.html
"""

from __future__ import annotations

import html
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

YT_CHANNEL_ID = "UCdDGdIWnfcB3t5cy9pjGsIw"  # PRA Network 2
YT_CHANNEL_HANDLE = "PRANetwork2"
YT_FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={YT_CHANNEL_ID}"

TWITCH_LOGIN = "pra_network"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Twitch's public web client id
TWITCH_GQL = "https://gql.twitch.tv/gql"
TWITCH_QUERY = (
    "query($login:String!){user(login:$login){displayName "
    "clips(first:20){edges{node{slug title viewCount createdAt durationSeconds}}}}}"
)
# Twitch only plays a clip on domains listed as parents. The first is the live
# site; the others keep the local preview working.
TWITCH_PARENTS = ("pra.phoenixrlm.com", "localhost", "127.0.0.1")

START = "<!-- watch:auto:start -->"
END = "<!-- watch:auto:end -->"
USER_AGENT = "pra-website-watch/1.0"


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def human_date(iso: str) -> str:
    try:
        day = datetime.strptime(iso[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return esc(iso)
    return day.strftime("%b %d, %Y").replace(" 0", " ")


def fetch_youtube() -> dict:
    request = urllib.request.Request(YT_FEED, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise ValueError("YouTube feed has no uploads")

    video_id = entry.findtext("yt:videoId", namespaces=ns)
    if not video_id:
        raise ValueError("YouTube entry has no video id")

    return {
        "id": video_id,
        "title": entry.findtext("atom:title", namespaces=ns) or "",
        "date": entry.findtext("atom:published", namespaces=ns) or "",
    }


def fetch_twitch_clip() -> dict:
    payload = json.dumps(
        {"query": TWITCH_QUERY, "variables": {"login": TWITCH_LOGIN}}
    ).encode()
    request = urllib.request.Request(
        TWITCH_GQL,
        data=payload,
        headers={"Client-ID": TWITCH_CLIENT_ID, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)

    user = (data.get("data") or {}).get("user") or {}
    edges = (user.get("clips") or {}).get("edges") or []
    clips = [edge["node"] for edge in edges if edge.get("node", {}).get("slug")]
    if not clips:
        raise ValueError("no Twitch clips found")

    return max(clips, key=lambda clip: str(clip.get("createdAt", "")))


def render(youtube: dict, clip: dict) -> str:
    parents = "&amp;".join(f"parent={parent}" for parent in TWITCH_PARENTS)
    clip_url = f"https://clips.twitch.tv/embed?clip={esc(clip['slug'])}&amp;{parents}"
    youtube_url = f"https://www.youtube.com/embed/{esc(youtube['id'])}"

    seconds = int(clip.get("durationSeconds") or 0)
    clip_meta = f"{seconds}s · clipped {human_date(clip.get('createdAt', ''))}"

    return f"""      <div class="watch-grid">
        <article class="watch-card">
          <div class="watch-frame">
            <iframe src="{youtube_url}" title="YouTube: {esc(youtube['title'])}"
                    loading="lazy" allowfullscreen
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"></iframe>
          </div>
          <div class="watch-body">
            <span class="watch-tag">▶ YouTube · latest upload</span>
            <h3>{esc(youtube['title'])}</h3>
            <p class="watch-meta">{human_date(youtube['date'])}</p>
            <a class="hl-link" href="https://www.youtube.com/@{esc(YT_CHANNEL_HANDLE)}" target="_blank" rel="noopener">PRA Network 2 on YouTube →</a>
          </div>
        </article>

        <article class="watch-card">
          <div class="watch-frame">
            <iframe src="{clip_url}" title="Twitch clip: {esc(clip.get('title', ''))}"
                    loading="lazy" allowfullscreen></iframe>
          </div>
          <div class="watch-body">
            <span class="watch-tag watch-tag-twitch">🎮 Twitch · latest clip</span>
            <h3>{esc(clip.get('title', ''))}</h3>
            <p class="watch-meta">{esc(clip_meta)}</p>
            <a class="hl-link" href="https://www.twitch.tv/{esc(TWITCH_LOGIN)}" target="_blank" rel="noopener">pra_network on Twitch →</a>
          </div>
        </article>
      </div>"""


def main(argv: list[str]) -> int:
    target = Path(argv[1] if len(argv) > 1 else "index.html")

    try:
        youtube = fetch_youtube()
        clip = fetch_twitch_clip()
        block = render(youtube, clip)
    except Exception as exc:  # network, XML, JSON or shape problem
        print(f"watch: refresh failed: {exc}", file=sys.stderr)
        return 1

    source = target.read_text(encoding="utf-8")
    if START not in source or END not in source:
        print(f"watch: markers not found in {target}", file=sys.stderr)
        return 1

    head, rest = source.split(START, 1)
    _, tail = rest.split(END, 1)
    target.write_text(f"{head}{START}\n{block}\n      {END}{tail}", encoding="utf-8")
    print(f"watch: refreshed {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
