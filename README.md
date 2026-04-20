# Politics Journal Crawler

An automated tool that monitors comparative politics and international relations journals for new publications and delivers bilingual (English/Korean) digests to subscribers.

## Features

- Crawls major IR and comparative politics journals for new DOIs
- Summarizes articles using Groq API (Llama 3.3-70b)
- Delivers bilingual (English/Korean) email digests via Formspree
- Subscriber management through GitHub Pages
- Fully automated via GitHub Actions

## Stack

- **Python** — journal crawling and digest generation (`journal_crawler.py`)
- **Groq API** (Llama 3.3-70b) — article summarization
- **Formspree** — email delivery and subscriber management
- **GitHub Actions** — automated scheduling
- **GitHub Pages** — subscription interface

## Project Structure

```
├── journal_crawler.py       # Main crawler and digest generator
├── requirements.txt         # Python dependencies
├── seen_dois.json           # Tracks already-processed DOIs
├── subscribers.json         # Subscriber list
├── index.html               # Landing page (GitHub Pages)
├── subscribe.html           # Subscription form
├── subscribe_success.html   # Post-subscription confirmation
└── .github/
    └── workflows/           # GitHub Actions automation
```

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Add the following secrets to your repository (`Settings > Secrets`):
   - `GROQ_API_KEY` — Groq API key for summarization
   - `FORMSPREE_API_KEY` — Formspree API key for email delivery
4. GitHub Actions handles automated runs on schedule

## Subscription

Subscribe to receive journal digests at the GitHub Pages site:
`https://shlee-95.github.io/politics`

## Author

Sang Hun Lee — PhD Student, Political Science, University at Buffalo  
[slee275@buffalo.edu](mailto:slee275@buffalo.edu) | [shlee-95.github.io](https://shlee-95.github.io)
