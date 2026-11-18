#!/usr/bin/env python3
"""Regenerate the league-highlights block on the home page.

The Phoenix Racing League Manager serves the network feed as JSON, but without
CORS headers, so the page cannot fetch it in the browser. Instead this runs at
build time in .github/workflows/pages.yml against the deployed copy of
index.html: the published page stays plain HTML, and a scheduled workflow run
refreshes it from the hub.

Only the block between the highlight markers in index.html is rewritten; every
other byte of the page is left alone. If the feed is unreachable or malformed
the script exits non-zero and the workflow publishes the previous content.

    python3 scripts/update_highlights.py _site/index.html
"""

from __future__ import annotations

import html
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEED_URL = "https://phoenixrlm.com/api/network"
LEAGUE_URL = "https://phoenixrlm.com/prodigy-racing-association"
NETWORK_URL = "https://phoenixrlm.com/network"
SCHEDULE_URL = f"{LEAGUE_URL}/schedule"

START = "<!-- highlights:auto:start -->"
END = "<!-- highlights:auto:end -->"

RESULTS_SHOWN = 3
UPCOMING_SHOWN = 3
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def fetch_feed(url: str = FEED_URL) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": "pra-website-highlights/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def human_date(iso: str, weekday: bool = False) -> str:
    try:
        day = datetime.strptime(iso, "%Y-%m-%d")
    except (TypeError, ValueError):
        return esc(iso)
    formatted = day.strftime("%A, %B %d, %Y") if weekday else day.strftime("%b %d, %Y")
    return formatted.replace(" 0", " ")


def short_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")
    except (TypeError, ValueError):
        return esc(iso)


def link(href: str, label: str) -> str:
    return (
        f'<a class="hl-link" href="{esc(href)}" target="_blank" rel="noopener">'
        f"{esc(label)}</a>"
    )


def podium_note(entry: dict) -> str:
    """Pick the most readable detail: laps led, else a gap, else the gain."""
    pos = entry.get("pos")
    start = entry.get("start")
    led = entry.get("laps_led") or 0
    interval = str(entry.get("interval") or "").strip()

    if led:
        return f"{led} led"
    # iRacing reports gaps as negative offsets; swapping the sign would read as
    # a gain, so only show the unambiguous positive format.
    if interval and not interval.startswith("-"):
        return interval
    if start and pos and start > pos:
        return f"P{start} → P{pos}"
    return f"from P{start}" if start else ""


def render_driver_of_the_week(driver: dict) -> str:
    name = driver.get("name") or "TBA"
    finish = driver.get("finish")
    start = driver.get("start")
    track = driver.get("track") or driver.get("race_name") or ""

    line = f"P{finish} from P{start} at {track}" if finish and start else track
    sub = " · ".join(
        part
        for part in (
            driver.get("series_name"),
            driver.get("season_name"),
            human_date(driver.get("date", "")),
        )
        if part
    )

    chips = "".join(
        f'<li>{esc(reason.get("emoji", ""))} {esc(reason.get("text", ""))}</li>'.replace(
            "  ", " "
        )
        for reason in (driver.get("reasons") or [])[:3]
        if reason.get("text")
    )

    return f"""        <article class="hl-card float-up">
          <span class="hl-tag hl-tag-gold">⭐ Driver of the Week</span>
          <h3>{esc(name)}</h3>
          <p class="hl-line">{esc(line)}</p>
          <p class="hl-sub">{esc(sub)}</p>
          <ul class="hl-chips">{chips}</ul>
          {link(NETWORK_URL, "Why this drive won →")}
        </article>"""


def render_next_race(race: dict) -> str:
    track = race.get("track") or race.get("name") or "TBA"
    name = race.get("name") or ""
    sub = " · ".join(
        part
        for part in (
            race.get("series_name"),
            race.get("season_name"),
            human_date(race.get("date", ""), weekday=True),
        )
        if part
    )
    line = name if name and name != track else ""

    return f"""        <article class="hl-card float-up" style="animation-delay:60ms">
          <span class="hl-tag">🏎️ Next on the grid</span>
          <h3>{esc(track)}</h3>
          <p class="hl-line">{esc(line)}</p>
          <p class="hl-sub">{esc(sub)}</p>
          {link(LEAGUE_URL, "League dashboard →")}
        </article>"""


def render_upcoming(races: list[dict], next_race: dict) -> str:
    next_id = (next_race or {}).get("id")
    later = [race for race in races if race.get("id") != next_id][:UPCOMING_SHOWN]

    if not later:
        items = '<li><span class="up-name">No further rounds scheduled</span></li>'
    else:
        items = "".join(
            f'<li><span class="up-date">{short_date(race.get("date", ""))}</span>'
            f'<span class="up-name">{esc(race.get("track") or race.get("name") or "")}</span>'
            f'<span class="up-series">{esc(race.get("series_name", ""))}</span></li>'
            for race in later
        )

    return f"""        <article class="hl-card float-up" style="animation-delay:120ms">
          <span class="hl-tag hl-tag-red">📅 Coming up</span>
          <h3>Next on the calendar</h3>
          <ul class="hl-upcoming">{items}</ul>
          {link(SCHEDULE_URL, "Full schedule →")}
        </article>"""


def render_result(race: dict) -> str:
    meta = " · ".join(
        part
        for part in (
            race.get("series_name"),
            f'{race.get("field")} starters' if race.get("field") else "",
            f'{race.get("laps")} laps' if race.get("laps") else "",
            f'SoF {race.get("strength_of_field")}' if race.get("strength_of_field") else "",
        )
        if part
    )

    podium = "".join(
        f'<li><span aria-hidden="true">{MEDALS.get(entry.get("pos"), "")}</span>'
        f'<span class="p-name">{esc(entry.get("name") or "")}</span>'
        f'<span class="p-note">{esc(podium_note(entry))}</span></li>'
        for entry in (race.get("podium") or [])[:3]
    )

    awards = " · ".join(
        f'{esc(award.get("emoji", ""))} {esc(award.get("title", ""))} '
        f'<strong>{esc(award.get("name", ""))}</strong>'.replace("  ", " ")
        for award in (race.get("awards") or [])[:3]
    )

    return f"""        <article class="result-card float-up">
          <div class="result-head">
            <h3>{esc(race.get("track") or race.get("race_name") or "")}</h3>
            <span class="result-date">{short_date(race.get("date", ""))}</span>
          </div>
          <p class="result-meta">{esc(meta)}</p>
          <ol class="podium">{podium}</ol>
          <p class="awards">{awards}</p>
          {link(NETWORK_URL, "Full results →")}
        </article>"""


def render_block(feed: dict, generated_at: datetime) -> str:
    driver = feed.get("driverOfTheWeek") or {}
    next_race = feed.get("nextRace") or {}
    upcoming = feed.get("upcoming") or []
    results = (feed.get("feed") or [])[:RESULTS_SHOWN]

    cards = render_driver_of_the_week(driver) if driver else ""
    cards += "\n" + render_next_race(next_race) if next_race else ""
    cards += "\n" + render_upcoming(upcoming, next_race)

    result_cards = "\n".join(render_result(race) for race in results)
    stamp = generated_at.strftime("%B %d, %Y at %H:%M UTC").replace(" 0", " ")

    return f"""      <div class="hl-grid">
{cards}
      </div>

      <h3 class="hl-subhead">Latest results</h3>

      <div class="result-grid">
{result_cards}
      </div>

      <div class="hl-foot">
        <p class="hl-updated">Refreshed from the Stats Hub · {stamp}</p>
        <div class="band-cta">
          <a class="btn btn-primary" href="{esc(LEAGUE_URL)}/standings" target="_blank" rel="noopener">🏆 Standings &amp; points</a>
          <a class="btn btn-ghost" href="{esc(NETWORK_URL)}" target="_blank" rel="noopener">📡 Network highlights</a>
        </div>
      </div>"""


def main(argv: list[str]) -> int:
    target = Path(argv[1] if len(argv) > 1 else "index.html")

    try:
        feed = fetch_feed()
        if not feed.get("driverOfTheWeek") and not feed.get("feed"):
            raise ValueError("feed returned no highlights")
        block = render_block(feed, datetime.now(timezone.utc))
    except Exception as exc:  # network, JSON or shape problem
        print(f"highlights: refresh failed: {exc}", file=sys.stderr)
        return 1

    source = target.read_text(encoding="utf-8")
    if START not in source or END not in source:
        print(f"highlights: markers not found in {target}", file=sys.stderr)
        return 1

    head, rest = source.split(START, 1)
    _, tail = rest.split(END, 1)
    target.write_text(f"{head}{START}\n{block}\n      {END}{tail}", encoding="utf-8")
    print(f"highlights: refreshed {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
