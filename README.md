# Prodigy Racing Association

Official website for the Prodigy Racing Association (PRA) — a sim racing community hosting competitive leagues across iRacing, Wreckfest, Gran Turismo 7, and Automobilista 2.

## Live Site

<https://pra.phoenixrlm.com/> — served by GitHub Pages on a subdomain of the
league's Phoenix Racing League Manager domain. The old
`ashes-to-light-studios.github.io/Prodigy-Racing-Association/` address redirects here.

## Pages

| File | Purpose |
| --- | --- |
| `index.html` | Landing page — league intro, platforms, community, and links out |
| `announcements.html` | League announcements |
| `calendar.html` | Embedded race calendar |
| `grid-finder.html` | Grid Finder sign-up splash |
| `discord-link.html` | Discord invite splash |

Schedules, standings, results, records, series details, and driver profiles all
live in the [Phoenix Racing League Manager](https://phoenixrlm.com/),
which this site links out to. This repo holds the public-facing site only —
five embed pages that duplicated the app (league stats, points standings,
league records, the records document, and the spreadsheet viewer) were removed
in favour of linking to it.

## Theme

All pages share the Phoenix Racing League Manager's design tokens, so the site
and the stats hub read as one product:

| Token | Value | Use |
| --- | --- | --- |
| `bg-0` | `#0d0d14` | Page background |
| `bg-1` | `#13131e` | Headers, raised bars |
| `bg-surface` | `#1a1a28` | Cards |
| `bg-elevated` | `#20202f` | Nested surfaces |
| `ink-0` / `ink-1` / `ink-2` | `#eeeef5` / `#bfbfd4` / `#9a9ab4` | Text scale |
| `accent-red` | `#e63946` | Primary brand accent |
| `accent-cyan` | `#00b4d8` | Interactive / links |
| `accent-gold` | `#f4a228` | Highlights |

Type is **Plus Jakarta Sans** (loaded from Google Fonts, falling back to
`Segoe UI` / `system-ui`). Cards use a 16px radius, controls 10px. A 2px
red-to-cyan hairline marks primary headers, matching the stats hub's hero.

Grid Finder orange (`#ff3d00`) and Discord blurple (`#5865f2`) are kept as-is
on their own splash pages.

## Deployment

The site is static HTML deployed via GitHub Pages. Every push to `main`
triggers automatic deployment through the workflow in `.github/workflows/pages.yml`.

### Setup

1. Open repository **Settings > Pages**.
2. Under Build and deployment, set Source to **GitHub Actions**.
3. Save.

### Custom domain

The site is served from <https://pra.phoenixrlm.com/>. The stats hub keeps the
apex `phoenixrlm.com`; this is a separate subdomain.

1. At the DNS provider for `phoenixrlm.com`, add a `CNAME` record for `pra`
   pointing at `ashes-to-light-studios.github.io`. Leave the apex and `www`
   records alone — they still point at the Phoenix Racing League Manager.
2. In **Settings > Pages**, set Custom domain to `pra.phoenixrlm.com` and save.
   The `CNAME` file in this repository keeps that setting in sync.
3. Once GitHub has issued the certificate (usually a few minutes), tick
   **Enforce HTTPS**.

GitHub redirects the old `ashes-to-light-studios.github.io/Prodigy-Racing-Association/`
address to the custom domain, so existing links keep working.

### Highlights refresh

The home page's league-highlights block is generated from the stats hub's
public feed (`https://phoenixrlm.com/api/network`). The feed sends no CORS
headers, so the page cannot read it in the browser; instead the Pages workflow
runs `scripts/update_highlights.py` against the built copy of `index.html`,
rewriting only the region between the `highlights:auto` markers. A scheduled
run refreshes it every three hours, and a push refreshes it on every deploy.
If the hub is unreachable the step logs the failure and the page keeps its
last rendered highlights.

The records part of that block is the hub's own embed
(`https://phoenixrlm.com/embed/prodigy-racing-association/records`), rendered
server-side with the hub's game, series and season filters, so record holders
stay current without a rebuild.

Run it locally with:

```sh
python3 scripts/update_highlights.py index.html
```

### Watch band

`scripts/update_watch.py` embeds the newest upload from the YouTube channel
(`@PRANetwork2`) and the latest clip from `twitch.tv/pra_network`. YouTube is
read from the channel's public RSS feed. Twitch has no keyless REST endpoint,
so the script uses the read-only GraphQL query the Twitch web player uses; if
that ever changes the step fails and the previous embeds stay in place.

```sh
python3 scripts/update_watch.py index.html
```

### Updating the Site

1. Edit the HTML files in this repository.
2. Commit and push to `main`.
3. The Pages workflow deploys automatically.
4. Verify at <https://pra.phoenixrlm.com/>.
