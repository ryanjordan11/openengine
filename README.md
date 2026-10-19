# Open Engine — Free AEO Website Scanner

> Most websites are invisible to AI. Is yours?

[![Live](https://img.shields.io/badge/live-openengine-39ff14?style=for-the-badge)](https://github.com/ryanjordan11/openengine)
[![Python](https://img.shields.io/badge/python-3.11+-white?style=for-the-badge)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.1-silver?style=for-the-badge)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/license-MIT-white?style=for-the-badge)](LICENSE)

**Open Engine** is a free, open-source Answer Engine Optimization (AEO) scanner. It grades any website on a 26-point rubric covering structured data, AI crawler access, llms.txt, MCP server cards, feeds, freshness signals, and the full Google I/O 2026 AI Mode / generative-UI / information-agent checks. No API keys. No sign-up. No cloud.

## ✨ Features

- **26-point AEO rubric** — Foundations, Structured Data, Agents & Discovery, Site Health
- **Google I/O 2026 ready** — AI Mode, generative UI, MCP, information agents, full 2026 crawler fleet (incl. Google-Agent)
- **Terminal-style live scan feed** — watch checks run in real time
- **Animated score dial** + category bars + rotating glow
- **3D signal core** (Three.js) with mouse parallax
- **Broken internal link checker**
- **Page speed audit** (TTFB, render-blocking, resource count)
- **Competitor comparison** — scan two domains side by side
- **Scan history** stored locally in SQLite
- **Printable PDF report** (Ctrl/Cmd+P)
- **Zero dependencies on AI** — pure HTTP + HTML parsing

## 🚀 Quick start

```bash
git clone https://github.com/ryanjordan11/openengine.git
cd openengine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8000

## 🛠️ Stack

Python · Flask · BeautifulSoup4 · requests · Three.js · Vanilla JS/CSS

## 📸 Screenshots

> Add screenshots to `/docs` and reference them here.

## 🤝 Contributing

PRs welcome. Open an issue first for big changes.

## ⭐ Star this repo

If Open Engine helped you, a star means a lot.

## License

MIT
