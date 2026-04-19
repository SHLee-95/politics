import os
import random
import smtplib
import json
import re
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from habanero import Crossref
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = "poliscibot@gmail.com"
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
RECIPIENT_EMAIL = "slee275@buffalo.edu"

OUTPUT_DIR = Path("output md files")
SEEN_DOIS_FILE = Path("seen_dois.json")
SUBSCRIBERS_FILE = Path("subscribers.json")
FETCH_PER_JOURNAL = 10
SAMPLE_PER_JOURNAL = 1

JOURNALS = [
    {"name": "American Political Science Review",        "issn": "0003-0554"},
    {"name": "American Journal of Political Science",    "issn": "0092-5853"},
    {"name": "Journal of Politics",                      "issn": "0022-3816"},
    {"name": "World Politics",                           "issn": "0043-8871"},
    {"name": "International Organization",               "issn": "0020-8183"},
    {"name": "International Security",                   "issn": "0162-2889"},
    {"name": "International Studies Quarterly",          "issn": "0020-8833"},
    {"name": "Comparative Political Studies",            "issn": "0010-4140"},
    {"name": "Comparative Politics",                     "issn": "0010-4159"},
    {"name": "Journal of Conflict Resolution",           "issn": "0022-0027"},
    {"name": "British Journal of Political Science",     "issn": "0007-1234"},
    {"name": "European Journal of Political Research",   "issn": "0304-4130"},
    {"name": "Political Research Quarterly",             "issn": "1065-9129"},
    {"name": "Security Studies",                         "issn": "0963-6412"},
    {"name": "Journal of Peace Research",                "issn": "0022-3433"},
    {"name": "Annual Review of Political Science",       "issn": "1094-2939"},
    {"name": "Global Environmental Politics",            "issn": "1526-3800"},
    {"name": "Review of International Studies",          "issn": "0260-2105"},
    {"name": "Politics & Society",                       "issn": "0032-3292"},
    {"name": "Journal of Democracy",                     "issn": "1045-5736"},
    {"name": "Democratization",                          "issn": "1351-0347"},
    {"name": "Party Politics",                           "issn": "1354-0688"},
    {"name": "European Journal of International Relations", "issn": "1354-0661"},
    {"name": "Conflict Management and Peace Science",    "issn": "0738-8942"},
    {"name": "Journal of Global Security Studies",       "issn": "2057-3170"},
    {"name": "Political Psychology",                     "issn": "0162-895X"},
    {"name": "Perspectives on Politics",                 "issn": "1537-5927"},
    {"name": "Contemporary Security Policy",             "issn": "1352-3260"},
    {"name": "International Studies Review",             "issn": "1521-9488"},
    {"name": "Foreign Policy Analysis",                  "issn": "1743-8586"},
    {"name": "International Interactions",               "issn": "0305-0629"},
    {"name": "International Studies Perspectives",       "issn": "1528-3577"},
    {"name": "International Political Science Review",   "issn": "0192-5121"},
    {"name": "Journal of European Public Policy",        "issn": "1350-1763"},
    {"name": "West European Politics",                   "issn": "0140-2382"},
    {"name": "Political Behavior",                       "issn": "0190-9320"},
    {"name": "Legislative Studies Quarterly",            "issn": "0362-9805"},
]

KEYWORDS = [
    "democracy", "democratization", "autocracy", "authoritarianism",
    "election", "voting", "electoral", "suffrage",
    "political party", "partisan", "party system",
    "civil war", "armed conflict", "political violence", "peace",
    "foreign policy", "diplomacy", "alliance",
    "international trade", "economic sanction", "interdependence",
    "international organization", "multilateralism", "regime",
    "governance", "state capacity", "institution",
    "populism", "polarization",
    "nationalism", "identity", "ethnicity",
    "human rights", "international norm", "international law",
    "inequality", "redistribution",
    "protest", "social movement", "revolution",
    "coercion", "repression",
    "hegemony", "power transition", "great power",
    "nuclear", "deterrence",
    "refugee", "migration",
    "climate", "environmental politics",
    "comparative politics", "international relations",
]


def load_subscribers() -> list:
    if SUBSCRIBERS_FILE.exists():
        with open(SUBSCRIBERS_FILE, "r") as f:
            return json.load(f)
    return [RECIPIENT_EMAIL]


def load_seen_dois() -> set:
    if SEEN_DOIS_FILE.exists():
        with open(SEEN_DOIS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_dois(seen: set):
    with open(SEEN_DOIS_FILE, "w") as f:
        json.dump(list(seen), f, indent=2)


def clean_abstract(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def keyword_match(paper: dict) -> bool:
    title = (paper.get("title") or [""])[0].lower()
    abstract = paper.get("abstract", "").lower()
    combined = title + " " + abstract
    return any(kw.lower() in combined for kw in KEYWORDS)


def fetch_papers(seen_dois: set) -> list:
    cr = Crossref()
    collected = []

    for journal in JOURNALS:
        try:
            result = cr.works(
                filter={"issn": journal["issn"]},
                sort="published",
                order="desc",
                limit=FETCH_PER_JOURNAL,
                select=["DOI", "title", "author", "published", "abstract", "URL", "container-title"],
            )
            items = result.get("message", {}).get("items", [])
        except Exception as e:
            print(f"  [SKIP] {journal['name']}: {e}")
            continue

        candidates = []
        for item in items:
            doi = item.get("DOI", "")
            if doi in seen_dois:
                continue
            if not keyword_match(item):
                continue
            candidates.append(item)

        sample = random.sample(candidates, min(SAMPLE_PER_JOURNAL, len(candidates)))
        for paper in sample:
            paper["_journal_name"] = journal["name"]
        collected.extend(sample)
        print(f"  {journal['name']}: {len(sample)} papers selected")

    return collected


def format_authors(item: dict) -> str:
    authors = item.get("author", [])
    if not authors:
        return "Unknown"
    parts = []
    for a in authors[:3]:
        family = a.get("family", "")
        given = a.get("given", "")
        if family:
            parts.append(f"{family}, {given[:1]}." if given else family)
    if len(authors) > 3:
        parts.append("et al.")
    return "; ".join(parts)


def format_year(item: dict) -> str:
    pub = item.get("published", {})
    dp = pub.get("date-parts", [[None]])
    year = dp[0][0] if dp and dp[0] else None
    return str(year) if year else "n.d."


def build_paper_list_text(papers: list) -> str:
    """Full list for email/markdown."""
    lines = []
    for i, p in enumerate(papers, 1):
        title = (p.get("title") or ["No title"])[0]
        authors = format_authors(p)
        year = format_year(p)
        journal = p.get("_journal_name", "")
        abstract = clean_abstract(p.get("abstract", "No abstract available."))
        doi = p.get("DOI", "")
        url = p.get("URL", f"https://doi.org/{doi}")
        lines.append(
            f"{i}. **{title}**\n"
            f"   - Authors: {authors} ({year})\n"
            f"   - Journal: {journal}\n"
            f"   - Abstract: {abstract[:300]}...\n"
            f"   - URL: {url}\n"
        )
    return "\n".join(lines)


def build_prompt_paper_list(papers: list) -> str:
    """Compact list for AI prompt — titles/authors/journal only to save tokens."""
    lines = []
    for i, p in enumerate(papers, 1):
        title = (p.get("title") or ["No title"])[0]
        authors = format_authors(p)
        year = format_year(p)
        journal = p.get("_journal_name", "")
        lines.append(f"{i}. {title} / {authors} ({year}) / {journal}")
    return "\n".join(lines)


def generate_summary(papers: list) -> str:
    if not papers:
        return "수집된 논문이 없습니다."

    client = Groq(api_key=GROQ_API_KEY)
    paper_text = build_prompt_paper_list(papers)
    today = datetime.now().strftime("%Y년 %m월 %d일")

    prompt = f"""당신은 비교정치학 및 국제정치학 전문 연구자입니다.
아래는 오늘({today}) 수집된 최신 학술 논문 목록입니다.

{paper_text}

다음 구조로 한국어 브리핑을 작성해 주세요:

## 📊 오늘의 수집 현황
- 총 논문 수, 수록 저널 수 등 간단한 통계

## 🔍 주제별 분류
논문들을 2~4개의 주제 클러스터로 묶어 정리 (예: 민주주의·권위주의, 분쟁·안보, 국제정치경제 등)

## 💡 주요 발견 및 연구 동향
- 오늘 논문들에서 발견되는 공통 연구 트렌드나 주목할 만한 발견 3~5가지를 bullet point로

## 🌐 주목할 논문 — 국제정치 (TOP 3)
국제관계, 외교, 안보, 전쟁, 국제기구, 무역, 핵 등 국제정치 분야에서 가장 중요한 논문 3편:
각 논문마다:
- APSA 스타일 완전 인용 (예: Smith, John, and Jane Doe. 2024. "Title." *Journal Name* 12(3): 45–67.)
- 핵심 주장 또는 발견 (2~3문장)
- 이 논문이 중요한 이유

## 🗳️ 주목할 논문 — 비교정치 (TOP 3)
민주주의, 권위주의, 선거, 정당, 국내 제도, 사회운동 등 비교정치 분야에서 가장 중요한 논문 3편:
각 논문마다:
- APSA 스타일 완전 인용 (예: Smith, John, and Jane Doe. 2024. "Title." *Journal Name* 12(3): 45–67.)
- 핵심 주장 또는 발견 (2~3문장)
- 이 논문이 중요한 이유

## 🔮 연구 시사점
이 논문들이 현실 정치나 학계에 갖는 함의 2~3가지

각 섹션은 간결하고 핵심만 담아주세요. 학술적이되 읽기 쉽게 작성해 주세요.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=3000,
    )
    return response.choices[0].message.content


def build_reference_list(papers: list) -> str:
    lines = []
    for p in papers:
        authors_raw = p.get("author", [])
        if authors_raw:
            last = authors_raw[0].get("family", "Unknown")
            initials = "".join(
                f"{n[:1]}." for n in authors_raw[0].get("given", "").split()
            )
            author_str = f"{last}, {initials}"
            if len(authors_raw) > 1:
                others = []
                for a in authors_raw[1:4]:
                    f_ = a.get("family", "")
                    g_ = "".join(f"{n[:1]}." for n in a.get("given", "").split())
                    others.append(f"{f_}, {g_}")
                author_str += ", " + ", ".join(others)
                if len(authors_raw) > 4:
                    author_str += ", et al."
        else:
            author_str = "Unknown"

        year = format_year(p)
        title = (p.get("title") or ["No title"])[0]
        journal = p.get("_journal_name", "")
        doi = p.get("DOI", "")
        url = p.get("URL", f"https://doi.org/{doi}")
        lines.append(f"- {author_str} ({year}). {title}. *{journal}*. {url}")

    return "\n".join(lines)


def save_markdown(papers: list, summary: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    filepath = OUTPUT_DIR / f"Report_{today_str}.md"

    paper_list_md = build_paper_list_text(papers)
    references = build_reference_list(papers)

    content = f"""# 비교정치학·국제정치학 논문 브리핑
**수집일**: {today_str} | **논문 수**: {len(papers)}편

---

{summary}

---

## 📄 수집 논문 목록

{paper_list_md}

---

## 📚 참고문헌 (APA Style)

{references}
"""
    filepath.write_text(content, encoding="utf-8")
    print(f"  Saved: {filepath}")
    return filepath


def markdown_to_html(text: str) -> str:
    lines = text.split("\n")
    html_lines = []
    in_ul = False

    for line in lines:
        # h2
        if line.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line[3:])
            html_lines.append(
                f'<h2 style="font-size:15px;font-weight:700;color:#1e293b;'
                f'margin:24px 0 8px;padding-bottom:6px;border-bottom:1px solid #e2e8f0;">'
                f'{content}</h2>'
            )
        # h3
        elif line.startswith("### "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line[4:])
            html_lines.append(
                f'<h3 style="font-size:13px;font-weight:700;color:#334155;margin:16px 0 4px;">'
                f'{content}</h3>'
            )
        # bullet
        elif line.startswith("- "):
            if not in_ul:
                html_lines.append('<ul style="margin:6px 0 6px 0;padding-left:20px;">')
                in_ul = True
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line[2:])
            content = re.sub(r"\*(.*?)\*", r"<em>\1</em>", content)
            html_lines.append(f'<li style="margin-bottom:5px;color:#475569;line-height:1.6;">{content}</li>')
        # empty line
        elif line.strip() == "":
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append('<div style="height:8px;"></div>')
        # normal paragraph
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)
            content = re.sub(r"\*(.*?)\*", r"<em>\1</em>", content)
            if content.strip():
                html_lines.append(
                    f'<p style="margin:4px 0;color:#475569;line-height:1.7;">{content}</p>'
                )

    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def build_html_email(summary: str, papers: list, today_str: str) -> str:
    summary_html = markdown_to_html(summary)

    paper_cards = ""
    for p in papers:
        title = (p.get("title") or ["No title"])[0]
        journal = p.get("_journal_name", "")
        authors = format_authors(p)
        year = format_year(p)
        doi = p.get("DOI", "")
        url = p.get("URL", f"https://doi.org/{doi}")
        paper_cards += f"""
        <tr>
          <td style="padding:14px 0;border-bottom:1px solid #f1f5f9;">
            <a href="{url}" style="color:#1d4ed8;text-decoration:none;font-size:14px;
               font-weight:600;line-height:1.6;display:block;margin-bottom:5px;">{title}</a>
            <div>
              <span style="color:#64748b;font-size:13px;">{authors} &nbsp;({year})</span>
            </div>
            <div style="margin-top:3px;">
              <span style="display:inline-block;background:#eff6ff;color:#1d4ed8;font-size:11px;
                font-weight:600;padding:2px 8px;border-radius:4px;">{journal}</span>
            </div>
          </td>
        </tr>"""

    badge_style = (
        "display:inline-block;background:#dbeafe;color:#1d4ed8;"
        "font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin-right:6px;"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">

  <!-- HEADER -->
  <tr><td style="background:#0f172a;border-radius:12px 12px 0 0;padding:28px 32px;text-align:center;">
    <p style="margin:0 0 6px;color:#94a3b8;font-size:11px;letter-spacing:2px;text-transform:uppercase;">
      Daily Briefing
    </p>
    <h1 style="margin:0 0 8px;color:#f8fafc;font-size:20px;font-weight:700;line-height:1.3;">
      비교정치학 · 국제정치학 논문 브리핑
    </h1>
    <p style="margin:0;color:#64748b;font-size:12px;">{today_str}</p>
    <div style="margin-top:14px;">
      <span style="{badge_style}">{len(papers)}편 수집</span>
      <span style="{badge_style}">{len(set(p.get('_journal_name','') for p in papers))}개 저널</span>
    </div>
  </td></tr>

  <!-- SUMMARY -->
  <tr><td style="background:#ffffff;padding:28px 32px;">
    <p style="margin:0 0 16px;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;
       color:#94a3b8;font-weight:600;">AI 요약 브리핑</p>
    {summary_html}
  </td></tr>

  <!-- DIVIDER -->
  <tr><td style="background:#ffffff;padding:0 32px;">
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:0;">
  </td></tr>

  <!-- PAPER LIST -->
  <tr><td style="background:#ffffff;padding:24px 32px 28px;border-radius:0 0 12px 12px;">
    <p style="margin:0 0 14px;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;
       color:#94a3b8;font-weight:600;">수집 논문 목록</p>
    <table width="100%" cellpadding="0" cellspacing="0">{paper_cards}
    </table>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="padding:16px 0;text-align:center;">
    <p style="margin:0;color:#94a3b8;font-size:11px;">
      Pol-Sci Journal Bot &nbsp;·&nbsp; Powered by Groq (Llama 3.3 70B) &nbsp;·&nbsp; Crossref API
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_email(subject: str, html_body: str, recipients: list):
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"polibot <{GMAIL_USER}>"
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            server.sendmail(GMAIL_USER, recipient, msg.as_string())
            print(f"  Email sent to {recipient}")


def main():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"\n=== Journal Crawler [{today_str}] ===\n")

    print("[1] Loading seen DOIs...")
    seen_dois = load_seen_dois()
    print(f"  {len(seen_dois)} DOIs already seen")

    print("\n[2] Fetching papers from journals...")
    papers = fetch_papers(seen_dois)
    print(f"\n  Total new papers: {len(papers)}")

    if not papers:
        print("  No new papers found. Exiting.")
        return

    print("\n[3] Generating AI summary with Gemini...")
    summary = generate_summary(papers)

    print("\n[4] Saving markdown report...")
    save_markdown(papers, summary)

    print("\n[5] Sending email...")
    subscribers = load_subscribers()
    html = build_html_email(summary, papers, today_str)
    subject = f"[정치학 브리핑] {today_str} — {len(papers)}편 수집"
    send_email(subject, html, subscribers)

    print("\n[6] Updating seen DOIs...")
    new_dois = {p.get("DOI", "") for p in papers if p.get("DOI")}
    seen_dois.update(new_dois)
    save_seen_dois(seen_dois)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
