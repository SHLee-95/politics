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
FETCH_PER_JOURNAL = 15
SAMPLE_PER_JOURNAL = 3

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
            f"   - Abstract: {abstract[:400]}...\n"
            f"   - URL: {url}\n"
        )
    return "\n".join(lines)


def generate_summary(papers: list) -> str:
    if not papers:
        return "수집된 논문이 없습니다."

    client = Groq(api_key=GROQ_API_KEY)
    paper_text = build_paper_list_text(papers)
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

## ⭐ 특히 주목할 논문 (TOP 3)
가장 중요하거나 흥미로운 논문 3편을 골라 각각:
- APSA 스타일 완전 인용 (예: Smith, John, and Jane Doe. 2024. "Title." *Journal Name* 12(3): 45–67.)
  저자 정보가 없는 경우 제공된 정보 최대한 활용할 것
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


def build_html_email(summary: str, papers: list, today_str: str) -> str:
    paper_rows = ""
    for p in papers:
        title = (p.get("title") or ["No title"])[0]
        journal = p.get("_journal_name", "")
        authors = format_authors(p)
        year = format_year(p)
        doi = p.get("DOI", "")
        url = p.get("URL", f"https://doi.org/{doi}")
        paper_rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">
            <a href="{url}" style="color:#1a73e8;text-decoration:none;font-weight:bold;">{title}</a><br>
            <small style="color:#666;">{authors} ({year}) — <em>{journal}</em></small>
          </td>
        </tr>"""

    summary_html = summary.replace("\n", "<br>").replace("##", "<strong>").replace("**", "<b>")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;background:#f9f9f9;padding:20px;">
  <div style="background:#1a237e;color:white;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
    <h1 style="margin:0;font-size:22px;">🌏 비교정치학·국제정치학 논문 브리핑</h1>
    <p style="margin:5px 0 0;">{today_str} | {len(papers)}편 수집</p>
  </div>
  <div style="background:white;padding:20px;border:1px solid #ddd;">
    <h2 style="color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:5px;">AI 요약 브리핑</h2>
    <div style="line-height:1.7;color:#333;">{summary_html}</div>
  </div>
  <div style="background:white;padding:20px;border:1px solid #ddd;margin-top:10px;">
    <h2 style="color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:5px;">수집 논문 목록</h2>
    <table style="width:100%;border-collapse:collapse;">{paper_rows}
    </table>
  </div>
  <div style="text-align:center;color:#aaa;font-size:12px;margin-top:15px;">
    Generated by Journal Crawler · Powered by Groq (Llama 3.3 70B)
  </div>
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
