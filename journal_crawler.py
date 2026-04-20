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
SAMPLE_PER_JOURNAL = 2

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
            raw = json.load(f)
        result = []
        for item in raw:
            if isinstance(item, str):
                result.append({"email": item, "language": "ko"})
            elif isinstance(item, dict) and item.get("email"):
                result.append(item)
        return result
    return [{"email": RECIPIENT_EMAIL, "language": "ko"}]


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


def generate_summary(papers: list, language: str = "ko") -> str:
    if not papers:
        return "수집된 논문이 없습니다." if language == "ko" else "No papers collected."

    client = Groq(api_key=GROQ_API_KEY)
    paper_text = build_prompt_paper_list(papers)

    if language == "en":
        today = datetime.now().strftime("%B %d, %Y")
        prompt = f"""You are an expert researcher in comparative politics and international relations.
Below are today's ({today}) newly collected academic papers.

{paper_text}

Write a concise English briefing in this exact structure:

## 📊 Today's Collection
- Brief stats: total papers, number of journals

## 🔍 Thematic Clusters
Group papers into 2–4 themes (e.g., Democracy & Authoritarianism, Conflict & Security, IPE)

## 💡 Key Trends
- 3–5 bullet points on notable shared findings or research trends today

## 🌐 Featured — International Relations (TOP 3)
Pick the 3 most important IR papers (foreign policy, security, war, IO, trade, nuclear):
For each:
- Full APSA citation (e.g., Smith, John. 2024. "Title." *Journal* URL)
- Core argument or finding (2–3 sentences)
- Why it matters

## 🗳️ Featured — Comparative Politics (TOP 3)
Pick the 3 most important CP papers (democracy, elections, parties, authoritarianism):
For each:
- Full APSA citation
- Core argument or finding (2–3 sentences)
- Why it matters

## 🔮 Implications
2–3 implications for real-world politics or the field.

Keep it concise, evidence-based, and readable.
"""
    else:
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
- APSA 스타일 완전 인용 (예: Smith, John. 2024. "Title." *Journal Name* URL)
- 핵심 주장 또는 발견 (2~3문장)
- 이 논문이 중요한 이유

## 🗳️ 주목할 논문 — 비교정치 (TOP 3)
민주주의, 권위주의, 선거, 정당, 국내 제도, 사회운동 등 비교정치 분야에서 가장 중요한 논문 3편:
각 논문마다:
- APSA 스타일 완전 인용 (예: Smith, John. 2024. "Title." *Journal Name* URL)
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


def format_apsa_citation(item: dict) -> str:
    authors_raw = item.get("author", [])
    if authors_raw:
        names = []
        for a in authors_raw[:6]:
            family = (a.get("family") or "").strip()
            given = (a.get("given") or "").strip()
            if family and given:
                names.append(f"{family}, {given}")
            elif family:
                names.append(family)
        if not names:
            author_text = "Unknown"
        elif len(names) == 1:
            author_text = names[0]
        elif len(names) == 2:
            author_text = f"{names[0]}, and {names[1]}"
        else:
            author_text = ", ".join(names[:-1]) + f", and {names[-1]}"
        if len(authors_raw) > 6:
            author_text += ", et al."
    else:
        author_text = "Unknown"

    year = format_year(item)
    title = (item.get("title") or ["No title"])[0].strip()
    journal = (item.get("_journal_name") or "").strip()
    doi = item.get("DOI", "")
    url = item.get("URL", f"https://doi.org/{doi}")
    return f'{author_text}. {year}. "{title}." *{journal}*. {url}'


def build_reference_list(papers: list) -> str:
    return "\n".join(f"- {format_apsa_citation(p)}" for p in papers)


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


def build_html_email(summary: str, papers: list, today_str: str, language: str = "ko") -> str:
    summary_html = markdown_to_html(summary)
    journal_count = len(set(p.get("_journal_name", "") for p in papers))

    if language == "en":
        header_label = "Daily Briefing"
        header_title = "Comparative Politics &amp; IR Briefing"
        badge_papers = f"{len(papers)} papers"
        badge_journals = f"{journal_count} journals"
        section_summary = "AI Summary"
        section_papers = "Paper List"
        footer_text = "Pol-Sci Journal Bot &nbsp;·&nbsp; Groq (Llama 3.3 70B) &nbsp;·&nbsp; Crossref API"
    else:
        header_label = "Daily Briefing"
        header_title = "비교정치학 · 국제정치학 논문 브리핑"
        badge_papers = f"{len(papers)}편"
        badge_journals = f"{journal_count}개 저널"
        section_summary = "AI 요약 브리핑"
        section_papers = "수집 논문 목록"
        footer_text = "Pol-Sci Journal Bot &nbsp;·&nbsp; Groq (Llama 3.3 70B) &nbsp;·&nbsp; Crossref API"

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
          <td style="padding:14px 0 14px;border-bottom:1px solid #f1f5f9;">
            <a href="{url}" style="font-size:14px;font-weight:700;color:#0f172a;
               text-decoration:none;line-height:1.55;display:block;margin-bottom:6px;">{title}</a>
            <span style="font-size:12px;color:#64748b;">{authors} ({year})</span>
            &nbsp;
            <span style="display:inline-block;background:#f0fdf4;color:#15803d;font-size:11px;
              font-weight:600;padding:1px 7px;border-radius:4px;vertical-align:middle;">{journal}</span>
          </td>
        </tr>"""

    badge = (
        "display:inline-block;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);"
        "color:#e2e8f0;font-size:11px;font-weight:600;padding:3px 10px;border-radius:99px;margin:0 3px;"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f7;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);
      border-radius:16px 16px 0 0;padding:32px 36px 28px;text-align:center;">
    <p style="margin:0 0 10px;color:#94a3b8;font-size:10px;font-weight:700;
       letter-spacing:3px;text-transform:uppercase;">{header_label}</p>
    <h1 style="margin:0 0 10px;color:#f8fafc;font-size:22px;font-weight:800;line-height:1.3;">
      {header_title}
    </h1>
    <p style="margin:0 0 16px;color:#64748b;font-size:12px;">{today_str}</p>
    <div>
      <span style="{badge}">{badge_papers}</span>
      <span style="{badge}">{badge_journals}</span>
    </div>
  </td></tr>

  <!-- SUMMARY LABEL -->
  <tr><td style="background:#f8fafc;padding:20px 36px 0;">
    <p style="margin:0;font-size:10px;font-weight:700;letter-spacing:2px;
       text-transform:uppercase;color:#94a3b8;">{section_summary}</p>
  </td></tr>

  <!-- SUMMARY BODY -->
  <tr><td style="background:#f8fafc;padding:14px 36px 28px;">
    {summary_html}
  </td></tr>

  <!-- PAPER LIST SECTION -->
  <tr><td style="background:#ffffff;border-top:1px solid #e2e8f0;
      border-radius:0 0 16px 16px;padding:24px 36px 28px;">
    <p style="margin:0 0 14px;font-size:10px;font-weight:700;letter-spacing:2px;
       text-transform:uppercase;color:#94a3b8;">{section_papers}</p>
    <table width="100%" cellpadding="0" cellspacing="0">{paper_cards}
    </table>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="padding:18px 0;text-align:center;">
    <p style="margin:0;color:#94a3b8;font-size:11px;">{footer_text}</p>
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
            msg["From"] = f"Pol-Sci Journal Bot <{GMAIL_USER}>"
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

    print("\n[3] Loading subscribers...")
    subscribers = load_subscribers()
    has_en = any(s.get("language") == "en" for s in subscribers)

    print("\n[4] Generating AI summary...")
    summary_ko = generate_summary(papers, language="ko")
    summary_en = generate_summary(papers, language="en") if has_en else None

    print("\n[5] Saving markdown report...")
    save_markdown(papers, summary_ko)

    print("\n[6] Sending emails...")
    recipients_ko = [s["email"] for s in subscribers if s.get("language", "ko") != "en"]
    recipients_en = [s["email"] for s in subscribers if s.get("language") == "en"]

    if recipients_ko:
        html_ko = build_html_email(summary_ko, papers, today_str, language="ko")
        send_email(f"[정치학 브리핑] {today_str} — {len(papers)}편 수집", html_ko, recipients_ko)

    if recipients_en and summary_en:
        html_en = build_html_email(summary_en, papers, today_str, language="en")
        send_email(f"[Poli-Sci Briefing] {today_str} — {len(papers)} papers", html_en, recipients_en)

    print("\n[6] Updating seen DOIs...")
    new_dois = {p.get("DOI", "") for p in papers if p.get("DOI")}
    seen_dois.update(new_dois)
    save_seen_dois(seen_dois)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
