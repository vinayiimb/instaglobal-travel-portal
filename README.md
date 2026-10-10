# Insta Global Travel: website redesign + flight portal

Redesign of [instaglobaltravel.com](https://www.instaglobaltravel.com): 94 pages (visa destinations, services, company pages) generated from the live site's own data, plus a flight search portal.

- `build.py` builds the static site into `site/` from `data/` and `assets/`.
- `server.mjs` serves the site and the flight API (zero dependencies, Node 18+): Google Flights fares via SerpApi, booking hand-off to the airline or travel site, optional Groq "plain-English" search.
- `video/make_video.py` renders the explainer video (Kokoro voice, ffmpeg).

## Run locally

```sh
cp .env.example .env      # add SERPAPI_KEY (and optionally GROQ_API_KEY)
python3 build.py
node server.mjs           # http://localhost:8765
node server.mjs --selftest
```

GitHub Pages hosts the static pages only; live flight prices need `server.mjs` running on a Node host, because the API key must stay on the server.
