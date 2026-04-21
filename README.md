# Political Science Journal Briefing Bot

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

## Attribution / Notices

- This repository builds on earlier source materials, workflow ideas, or implementation patterns provided by a third party.
- This project uses article metadata retrieved through Crossref.
- Digest summaries are generated with the Groq API using Llama 3.3-70B.
- Subscription handling is powered by Formspree, and the subscription site is served via GitHub Pages.
- Journal titles, article titles, abstracts, and other third-party materials referenced by this project remain the property of their respective owners.
- No claim of copyright or commercial rights is made over third-party articles, abstracts, titles, or other scholarly materials referenced or summarized in this repository.
- Generated summaries may contain errors or omissions and should be checked against the original sources before research or professional use.
- No open source license is granted for this repository unless a separate license file is added in the future.
- Except as otherwise noted, rights in the original code, text, and repository-specific materials remain with their respective rights holders.
- Product names, service names, and trademarks mentioned in this repository belong to their respective owners.

## Disclaimer

- Third-party source materials, linked resources, metadata, and referenced content are provided for research and informational purposes only.
- Such third-party materials cannot be construed as reflecting the independent scholarly judgment or views of the repository maintainer or contributor, or as endorsement, warranty, approval, or expression of opinion regarding the referenced material.
- Inclusion, adaptation, or reference does not by itself imply authorship, ownership, approval, partnership, or affiliation.
- Article selection, core summaries, significance statements, and similar evaluative outputs may include AI-generated content and cannot be construed as the independent scholarly judgment or views of the repository maintainer or contributor.
- This repository is provided solely for research and informational purposes and cannot be construed as academic, legal, or policy advice.
- No express or implied warranty is made as to the accuracy, completeness, reliability, fitness, or non-infringement of the information provided, and sole responsibility for its interpretation and use rests with the reader.

## Project Role

Sang Hun Lee maintains and operates this repository and contributed to its direction, prompting, adaptation, editing, review, and deployment.  
The present repository reflects subsequent adaptation of third-party source materials and workflow patterns for this project.  
This repository also includes material produced or revised with AI assistance, including OpenAI Codex and Anthropic Claude.

[slee275@buffalo.edu](mailto:slee275@buffalo.edu) | [shlee-95.github.io](https://shlee-95.github.io)
