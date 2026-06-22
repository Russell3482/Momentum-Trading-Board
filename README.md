# Momentum Trading Agent

Local momentum / VCP trading dashboard for the core semiconductor watchlist.

## Local Update

```bash
python3 -m pip install -r requirements.txt
python3 scripts/generate_report.py --mode premarket
python3 scripts/build_site.py
python3 -m http.server 8766 --directory site
```

Open `http://localhost:8766/`.

## Publish

The GitHub Pages workflow publishes the generated `site/` directory.

