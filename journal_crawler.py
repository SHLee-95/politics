import os
import random
import smtplib
import json
import re
from datetime import datetime
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
    # ── International Relations ──────────────────────────────────────────
    {"name": "International Organization",               "issn": "0020-8183",  "field": "ir"},
    {"name": "International Security",                   "issn": "0162-2889",  "field": "ir"},
    {"name": "International Studies Quarterly",          "issn": "0020-8833",  "field": "ir"},
    {"name": "World Politics",                           "issn": "0043-8871",  "field": "ir"},
    {"name": "Journal of Conflict Resolution",           "issn": "0022-0027",  "field": "ir"},
    {"name": "Security Studies",                         "issn": "0963-6412",  "field": "ir"},
    {"name": "Journal of Peace Research",                "issn": "0022-3433",  "field": "ir"},
    {"name": "Review of International Studies",          "issn": "0260-2105",  "field": "ir"},
    {"name": "European Journal of International Relations","issn": "1354-0661","field": "ir"},
    {"name": "Conflict Management and Peace Science",    "issn": "0738-8942",  "field": "ir"},
    {"name": "Journal of Global Security Studies",       "issn": "2057-3170",  "field": "ir"},
    {"name": "Contemporary Security Policy",             "issn": "1352-3260",  "field": "ir"},
    {"name": "International Studies Review",             "issn": "1521-9488",  "field": "ir"},
    {"name": "Foreign Policy Analysis",                  "issn": "1743-8586",  "field": "ir"},
    {"name": "International Interactions",               "issn": "0305-0629",  "field": "ir"},
    {"name": "International Studies Perspectives",       "issn": "1528-3577",  "field": "ir"},
    {"name": "Journal of Strategic Studies",             "issn": "0140-2390",  "field": "ir"},
    {"name": "Armed Forces & Society",                   "issn": "0095-327X",  "field": "ir"},
    {"name": "Global Governance",                        "issn": "1075-2846",  "field": "ir"},
    {"name": "International Political Sociology",        "issn": "1749-5679",  "field": "ir"},

    # ── Comparative Politics ─────────────────────────────────────────────
    {"name": "Comparative Political Studies",            "issn": "0010-4140",  "field": "cp"},
    {"name": "Comparative Politics",                     "issn": "0010-4159",  "field": "cp"},
    {"name": "Journal of Democracy",                     "issn": "1045-5736",  "field": "cp"},
    {"name": "Democratization",                          "issn": "1351-0347",  "field": "cp"},
    {"name": "Party Politics",                           "issn": "1354-0688",  "field": "cp"},
    {"name": "West European Politics",                   "issn": "0140-2382",  "field": "cp"},
    {"name": "Electoral Studies",                        "issn": "0261-3794",  "field": "cp"},
    {"name": "Government and Opposition",                "issn": "0017-257X",  "field": "cp"},
    {"name": "Journal of Elections, Public Opinion and Parties","issn": "1745-7289","field": "cp"},
    {"name": "Politics & Society",                       "issn": "0032-3292",  "field": "cp"},
    {"name": "Political Behavior",                       "issn": "0190-9320",  "field": "cp"},
    {"name": "Legislative Studies Quarterly",            "issn": "0362-9805",  "field": "cp"},
    {"name": "Perspectives on Politics",                 "issn": "1537-5927",  "field": "cp"},
    {"name": "European Journal of Political Research",   "issn": "0304-4130",  "field": "cp"},
    {"name": "Journal of European Public Policy",        "issn": "1350-1763",  "field": "cp"},
    {"name": "Acta Politica",                            "issn": "0001-6810",  "field": "cp"},

    # ── General / Top Journals (both fields) ────────────────────────────
    {"name": "American Political Science Review",        "issn": "0003-0554",  "field": "general"},
    {"name": "American Journal of Political Science",    "issn": "0092-5853",  "field": "general"},
    {"name": "Journal of Politics",                      "issn": "0022-3816",  "field": "general"},
    {"name": "British Journal of Political Science",     "issn": "0007-1234",  "field": "general"},
    {"name": "Annual Review of Political Science",       "issn": "1094-2939",  "field": "general"},
    {"name": "Political Research Quarterly",             "issn": "1065-9129",  "field": "general"},
    {"name": "International Political Science Review",   "issn": "0192-5121",  "field": "general"},
    {"name": "Political Psychology",                     "issn": "0162-895X",  "field": "general"},

    # ── Methods ──────────────────────────────────────────────────────────
    {"name": "Political Analysis",                       "issn": "1047-1987",  "field": "methods"},
    {"name": "Political Science Research and Methods",   "issn": "2049-8470",  "field": "methods"},
    {"name": "Sociological Methods & Research",          "issn": "0049-1241",  "field": "methods"},
    {"name": "Journal of Information Technology & Politics","issn": "1933-1681","field": "methods"},
]

KEYWORDS = [
    "democracy", "democratization", "autocracy", "authoritarianism",
    "election", "voting", "electoral", "civil war", "armed conflict",
    "political violence", "peace", "foreign policy", "diplomacy", "alliance",
    "international trade", "economic sanction", "international organization",
    "multilateralism", "regime", "governance", "state capacity",
    "populism", "polarization", "nationalism", "identity", "ethnicity",
    "human rights", "international norm", "inequality", "protest",
    "social movement", "revolution", "coercion", "hegemony",
    "power transition", "nuclear", "deterrence", "refugee", "migration",
    "climate", "comparative politics", "international relations",
    "causal inference", "regression", "experiment", "survey", "quantitative",
    "qualitative", "measurement", "civil-military", "military",
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
    return re.sub(r"\s+", " ", text).strip()


def keyword_match(paper: dict) -> bool:
    title = (paper.get("title") or [""])[0].lower()
    abstract = paper.get("abstract", "").lower()
    return any(kw.lower() in (title + " " + abstract) for kw in KEYWORDS)


def fetch_papers(seen_dois: set) -> list:
    cr = Crossref()
    collected = []
    for journal in JOURNALS:
        try:
            result = cr.works(
                filter={"issn": journal["issn"]},
                sort="published", order="desc",
                limit=FETCH_PER_JOURNAL,
                select=["DOI","title","author","published","abstract","URL","container-title"],
            )
            items = result.get("message", {}).get("items", [])
        except Exception as e:
            print(f"  [SKIP] {journal['name']}: {e}")
            continue

        candidates = [i for i in items if i.get("DOI","") not in seen_dois and keyword_match(i)]
        sample = random.sample(candidates, min(SAMPLE_PER_JOURNAL, len(candidates)))
        for p in sample:
            p["_journal_name"] = journal["name"]
            p["_field"] = journal.get("field", "general")
        collected.extend(sample)
        print(f"  {journal['name']}: {len(sample)} papers")
    return collected


def format_authors(item: dict) -> str:
    authors = item.get("author", [])
    parts = []
    for a in authors[:3]:
        family = a.get("family", "")
        given = a.get("given", "")
        if family:
            parts.append(f"{family}, {given[:1]}." if given else family)
    if len(authors) > 3:
        parts.append("et al.")
    return "; ".join(parts) if parts else "Unknown"


def format_year(item: dict) -> str:
    dp = item.get("published", {}).get("date-parts", [[None]])
    year = dp[0][0] if dp and dp[0] else None
    return str(year) if year else "n.d."


def build_prompt_paper_list(papers: list) -> str:
    lines = []
    for i, p in enumerate(papers, 1):
        title = (p.get("title") or ["No title"])[0]
        authors = format_authors(p)
        year = format_year(p)
        journal = p.get("_journal_name", "")
        field = p.get("_field", "general")
        abstract = clean_abstract(p.get("abstract", ""))[:200]
        url = p.get("URL", f"https://doi.org/{p.get('DOI','')}")
        lines.append(f"{i}. [{field.upper()}] {title} / {authors} ({year}) / {journal} / {url}\n   Abstract: {abstract}")
    return "\n".join(lines)


def generate_summary(papers: list, language: str = "ko") -> str:
    if not papers:
        return "수집된 논문이 없습니다." if language == "ko" else "No papers collected."

    client = Groq(api_key=GROQ_API_KEY)
    paper_text = build_prompt_paper_list(papers)

    if language == "en":
        prompt = f"""You are an expert in comparative politics and international relations.
Below are today's newly collected academic papers, tagged by field [IR], [CP], [GENERAL], or [METHODS].

{paper_text}

Write a concise daily briefing in EXACTLY this structure — no other sections:

## 🌐 International Relations — Top 3
Pick the 3 most important IR/security/foreign policy papers. For each:
- **Title** (Journal, Year) — [URL]
  Authors: ...
  Core finding: 2–3 sentences on argument and contribution.

## 🗳️ Comparative Politics — Top 3
Pick the 3 most important democracy/elections/parties/authoritarianism papers. For each:
- **Title** (Journal, Year) — [URL]
  Authors: ...
  Core finding: 2–3 sentences on argument and contribution.

## 📐 Methods & Theory — Top 3
Pick the 3 most methodologically or theoretically innovative papers. For each:
- **Title** (Journal, Year) — [URL]
  Authors: ...
  Core finding: 2–3 sentences on method or theoretical contribution.

Be concise and scholarly. Do NOT add any intro, conclusion, or extra sections.
"""
    else:
        prompt = f"""당신은 비교정치학 및 국제정치학 전문 연구자입니다.
아래는 오늘 수집된 최신 학술 논문 목록입니다. 각 논문에는 분야 태그 [IR], [CP], [GENERAL], [METHODS]가 붙어 있습니다.

{paper_text}

다음 구조로 한국어 브리핑을 작성해 주세요. 이 세 섹션 외 다른 섹션은 절대 추가하지 마세요:

## 🌐 국제정치 — 추천 논문 3편
IR/안보/외교/전쟁/국제기구/핵 분야에서 가장 중요한 논문 3편. 각 논문마다:
- **논문 제목** (저널명, 연도) — [URL]
  저자: ...
  핵심 주장: 논문의 핵심 논거와 기여를 2~3문장으로 서술.

## 🗳️ 비교정치 — 추천 논문 3편
민주주의/권위주의/선거/정당/의회/사회운동 분야에서 가장 중요한 논문 3편. 각 논문마다:
- **논문 제목** (저널명, 연도) — [URL]
  저자: ...
  핵심 주장: 논문의 핵심 논거와 기여를 2~3문장으로 서술.

## 📐 방법론 & 이론 — 추천 논문 3편
방법론적으로 또는 이론적으로 가장 혁신적인 논문 3편. 각 논문마다:
- **논문 제목** (저널명, 연도) — [URL]
  저자: ...
  핵심 주장: 방법론적·이론적 기여를 2~3문장으로 서술.

간결하고 학술적으로 작성해 주세요. 도입부, 결론, 추가 섹션은 넣지 마세요.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=2500,
    )
    return response.choices[0].message.content


def markdown_to_html(text: str) -> str:
    lines = text.split("\n")
    html_lines = []
    in_ul = False

    for line in lines:
        if line.startswith("## "):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line[3:])
            html_lines.append(
                f'<h2 style="font-size:15px;font-weight:700;color:#1e293b;'
                f'margin:28px 0 10px;padding-bottom:6px;border-bottom:2px solid #e2e8f0;">'
                f'{content}</h2>'
            )
        elif line.startswith("- "):
            if not in_ul:
                html_lines.append('<ul style="margin:8px 0;padding-left:0;list-style:none;">')
                in_ul = True
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line[2:])
            content = re.sub(r"\*(.*?)\*", r"<em>\1</em>", content)
            content = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" style="color:#2563eb;">\1</a>', content)
            html_lines.append(
                f'<li style="margin-bottom:14px;padding:12px 14px;background:#f8fafc;'
                f'border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;'
                f'color:#334155;line-height:1.65;font-size:13px;">{content}</li>'
            )
        elif line.strip() == "":
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            html_lines.append('<div style="height:6px;"></div>')
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)
            content = re.sub(r"\*(.*?)\*", r"<em>\1</em>", content)
            content = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" style="color:#2563eb;">\1</a>', content)
            if content.strip():
                html_lines.append(
                    f'<p style="margin:3px 0 3px 14px;color:#475569;line-height:1.7;font-size:13px;">{content}</p>'
                )

    if in_ul:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def build_html_email(summary: str, today_str: str, language: str = "ko") -> str:
    summary_html = markdown_to_html(summary)
    badge = (
        "display:inline-block;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);"
        "color:#e2e8f0;font-size:11px;font-weight:600;padding:3px 10px;border-radius:99px;margin:0 3px;"
    )

    if language == "en":
        header_title = "Comparative Politics &amp; IR Briefing"
        sub = "IR · Comparative · Methods — Top 3 each"
        footer_text = "Pol-Sci Journal Bot &nbsp;·&nbsp; Groq (Llama 3.3 70B) &nbsp;·&nbsp; Crossref API"
    else:
        header_title = "비교정치학 · 국제정치학 논문 브리핑"
        sub = "국제정치 · 비교정치 · 방법론 — 각 분야 추천 3편"
        footer_text = "Pol-Sci Journal Bot &nbsp;·&nbsp; Groq (Llama 3.3 70B) &nbsp;·&nbsp; Crossref API"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f7;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- HEADER -->
  <tr><td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);
      border-radius:16px 16px 0 0;padding:32px 36px 28px;text-align:center;">
    <p style="margin:0 0 10px;color:#94a3b8;font-size:10px;font-weight:700;
       letter-spacing:3px;text-transform:uppercase;">Daily Briefing</p>
    <h1 style="margin:0 0 8px;color:#f8fafc;font-size:22px;font-weight:800;line-height:1.3;">
      {header_title}</h1>
    <p style="margin:0 0 14px;color:#94a3b8;font-size:12px;">{sub}</p>
    <p style="margin:0;color:#64748b;font-size:11px;">{today_str}</p>
  </td></tr>

  <!-- BODY -->
  <tr><td style="background:#f8fafc;padding:28px 36px 32px;border-radius:0 0 16px 16px;">
    {summary_html}
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

    report_file = OUTPUT_DIR / f"Report_{today_str}.md"
    if report_file.exists():
        print(f"Today's report already sent ({report_file}). Skipping.")
        return

    print("[1] Loading seen DOIs...")
    seen_dois = load_seen_dois()

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

    print("\n[5] Sending emails...")
    recipients_ko = [s["email"] for s in subscribers if s.get("language", "ko") != "en"]
    recipients_en = [s["email"] for s in subscribers if s.get("language") == "en"]

    if recipients_ko:
        html_ko = build_html_email(summary_ko, today_str, language="ko")
        send_email(f"[정치학 브리핑] {today_str}", html_ko, recipients_ko)

    if recipients_en and summary_en:
        html_en = build_html_email(summary_en, today_str, language="en")
        send_email(f"[Poli-Sci Briefing] {today_str}", html_en, recipients_en)

    print("\n[6] Updating seen DOIs...")
    new_dois = {p.get("DOI", "") for p in papers if p.get("DOI")}
    seen_dois.update(new_dois)
    save_seen_dois(seen_dois)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
