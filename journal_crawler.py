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
    {"name": "International Organization",                  "issn": "0020-8183",  "field": "ir"},
    {"name": "International Security",                      "issn": "0162-2889",  "field": "ir"},
    {"name": "International Studies Quarterly",             "issn": "0020-8833",  "field": "ir"},
    {"name": "World Politics",                              "issn": "0043-8871",  "field": "ir"},
    {"name": "Journal of Conflict Resolution",              "issn": "0022-0027",  "field": "ir"},
    {"name": "Security Studies",                            "issn": "0963-6412",  "field": "ir"},
    {"name": "Journal of Peace Research",                   "issn": "0022-3433",  "field": "ir"},
    {"name": "Review of International Studies",             "issn": "0260-2105",  "field": "ir"},
    {"name": "European Journal of International Relations", "issn": "1354-0661",  "field": "ir"},
    {"name": "Conflict Management and Peace Science",       "issn": "0738-8942",  "field": "ir"},
    {"name": "Journal of Global Security Studies",          "issn": "2057-3170",  "field": "ir"},
    {"name": "Contemporary Security Policy",                "issn": "1352-3260",  "field": "ir"},
    {"name": "Foreign Policy Analysis",                     "issn": "1743-8586",  "field": "ir"},
    {"name": "International Interactions",                  "issn": "0305-0629",  "field": "ir"},
    {"name": "Journal of Strategic Studies",                "issn": "0140-2390",  "field": "ir"},
    {"name": "Armed Forces & Society",                      "issn": "0095-327X",  "field": "ir"},
    {"name": "Global Governance",                           "issn": "1075-2846",  "field": "ir"},
    {"name": "International Political Sociology",           "issn": "1749-5679",  "field": "ir"},
    {"name": "International Studies Review",                "issn": "1521-9488",  "field": "ir"},
    {"name": "International Studies Perspectives",          "issn": "1528-3577",  "field": "ir"},

    {"name": "Comparative Political Studies",               "issn": "0010-4140",  "field": "cp"},
    {"name": "Comparative Politics",                        "issn": "0010-4159",  "field": "cp"},
    {"name": "Journal of Democracy",                        "issn": "1045-5736",  "field": "cp"},
    {"name": "Democratization",                             "issn": "1351-0347",  "field": "cp"},
    {"name": "Party Politics",                              "issn": "1354-0688",  "field": "cp"},
    {"name": "West European Politics",                      "issn": "0140-2382",  "field": "cp"},
    {"name": "Electoral Studies",                           "issn": "0261-3794",  "field": "cp"},
    {"name": "Government and Opposition",                   "issn": "0017-257X",  "field": "cp"},
    {"name": "Journal of Elections, Public Opinion and Parties", "issn": "1745-7289", "field": "cp"},
    {"name": "Politics & Society",                          "issn": "0032-3292",  "field": "cp"},
    {"name": "Political Behavior",                          "issn": "0190-9320",  "field": "cp"},
    {"name": "Legislative Studies Quarterly",               "issn": "0362-9805",  "field": "cp"},
    {"name": "Perspectives on Politics",                    "issn": "1537-5927",  "field": "cp"},
    {"name": "European Journal of Political Research",      "issn": "0304-4130",  "field": "cp"},
    {"name": "Journal of European Public Policy",           "issn": "1350-1763",  "field": "cp"},
    {"name": "Acta Politica",                               "issn": "0001-6810",  "field": "cp"},

    {"name": "American Political Science Review",           "issn": "0003-0554",  "field": "general"},
    {"name": "American Journal of Political Science",       "issn": "0092-5853",  "field": "general"},
    {"name": "Journal of Politics",                         "issn": "0022-3816",  "field": "general"},
    {"name": "British Journal of Political Science",        "issn": "0007-1234",  "field": "general"},
    {"name": "Annual Review of Political Science",          "issn": "1094-2939",  "field": "general"},
    {"name": "Political Research Quarterly",                "issn": "1065-9129",  "field": "general"},
    {"name": "International Political Science Review",      "issn": "0192-5121",  "field": "general"},
    {"name": "Political Psychology",                        "issn": "0162-895X",  "field": "general"},

    {"name": "Political Analysis",                          "issn": "1047-1987",  "field": "methods"},
    {"name": "Political Science Research and Methods",      "issn": "2049-8470",  "field": "methods"},
    {"name": "Sociological Methods & Research",             "issn": "0049-1241",  "field": "methods"},
    {"name": "Journal of Information Technology & Politics","issn": "1933-1681",  "field": "methods"},
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
    "causal inference", "regression", "experiment", "survey", "measurement",
    "civil-military", "military",
]


def load_subscribers():
    if SUBSCRIBERS_FILE.exists():
        with open(SUBSCRIBERS_FILE) as f:
            raw = json.load(f)
        result = []
        for item in raw:
            if isinstance(item, str):
                result.append({"email": item, "language": "ko"})
            elif isinstance(item, dict) and item.get("email"):
                result.append(item)
        return result
    return [{"email": RECIPIENT_EMAIL, "language": "ko"}]


def load_seen_dois():
    if SEEN_DOIS_FILE.exists():
        with open(SEEN_DOIS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_dois(seen):
    with open(SEEN_DOIS_FILE, "w") as f:
        json.dump(list(seen), f, indent=2)


def clean_abstract(text):
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def keyword_match(paper):
    title = (paper.get("title") or [""])[0].lower()
    abstract = paper.get("abstract", "").lower()
    return any(kw.lower() in (title + " " + abstract) for kw in KEYWORDS)


def fetch_papers(seen_dois):
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


def format_authors(item):
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


def format_year(item):
    dp = item.get("published", {}).get("date-parts", [[None]])
    year = dp[0][0] if dp and dp[0] else None
    return str(year) if year else "n.d."


def build_prompt_paper_list(papers):
    lines = []
    for i, p in enumerate(papers, 1):
        title = (p.get("title") or ["No title"])[0]
        authors = format_authors(p)
        year = format_year(p)
        journal = p.get("_journal_name", "")
        field = p.get("_field", "general")
        abstract = clean_abstract(p.get("abstract", ""))[:300]
        url = p.get("URL", f"https://doi.org/{p.get('DOI','')}")
        lines.append(
            f"{i}. [{field.upper()}] {title}\n"
            f"   Authors: {authors} ({year}) | Journal: {journal} | URL: {url}\n"
            f"   Abstract: {abstract}"
        )
    return "\n\n".join(lines)


def generate_summary(papers, language="ko"):
    if not papers:
        return "수집된 논문이 없습니다." if language == "ko" else "No papers collected."

    client = Groq(api_key=GROQ_API_KEY)
    paper_text = build_prompt_paper_list(papers)

    if language == "ko":
        prompt = f"""당신은 비교정치학·국제정치학 전문 연구자입니다.
아래 논문 목록에서 분야별로 가장 중요한 논문 3편씩 선정해 브리핑하세요.
각 논문은 반드시 아래 [PAPER] 블록 형식으로만 출력하세요. 다른 텍스트는 절대 추가하지 마세요.

논문 목록:
{paper_text}

출력 형식 (이 형식을 정확히 따르세요):

[SECTION:IR]
[PAPER]
apsa: 저자 성, 이름. 연도. "논문 제목." *저널명*. URL
method: 방법론 한 단어 또는 짧은 구 (예: 패널 회귀분석, QCA, 서베이실험, 형식모형)
argument: 논문의 핵심 주장을 2-3문장으로. 무엇을 주장하며 어떤 증거로 뒷받침하는가.
significance: 이론적·정책적 의의 1-2문장. 기존 문헌과 어떻게 다른가.
url: URL
[/PAPER]
[PAPER]
... (2번째 IR 논문)
[/PAPER]
[PAPER]
... (3번째 IR 논문)
[/PAPER]
[/SECTION]

[SECTION:CP]
[PAPER]
... (비교정치 논문 3편, 동일 형식)
[/PAPER]
[/SECTION]

[SECTION:METHODS]
[PAPER]
... (방법론·이론 논문 3편, 동일 형식)
[/PAPER]
[/SECTION]
"""
    else:
        prompt = f"""You are an expert in comparative politics and international relations.
Select the 3 most important papers per section and output them in [PAPER] block format only. No other text.

Papers:
{paper_text}

Format (follow exactly):

[SECTION:IR]
[PAPER]
apsa: Last, First. Year. "Title." *Journal Name*. URL
method: One short phrase (e.g., panel regression, QCA, survey experiment, formal model)
argument: Core argument in 2-3 sentences. What is claimed and how is it supported?
significance: Theoretical and/or policy significance in 1-2 sentences. How does it advance the literature?
url: URL
[/PAPER]
[PAPER]
... (2nd IR paper)
[/PAPER]
[PAPER]
... (3rd IR paper)
[/PAPER]
[/SECTION]

[SECTION:CP]
[PAPER]
... (3 comparative politics papers, same format)
[/PAPER]
[/SECTION]

[SECTION:METHODS]
[PAPER]
... (3 methods/theory papers, same format)
[/PAPER]
[/SECTION]
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3000,
    )
    return response.choices[0].message.content


def parse_papers(raw_text):
    """Parse [SECTION:X]...[/SECTION] and [PAPER]...[/PAPER] blocks."""
    sections = {}
    section_pattern = re.findall(r'\[SECTION:(\w+)\](.*?)\[/SECTION\]', raw_text, re.DOTALL)
    for sec_name, sec_body in section_pattern:
        papers = []
        paper_blocks = re.findall(r'\[PAPER\](.*?)\[/PAPER\]', sec_body, re.DOTALL)
        for block in paper_blocks:
            paper = {}
            for line in block.strip().split('\n'):
                if ':' in line:
                    key, _, val = line.partition(':')
                    paper[key.strip()] = val.strip()
            if paper.get('title') or paper.get('apsa'):
                papers.append(paper)
        sections[sec_name] = papers
    return sections


def build_html_email(raw_summary, today_str, language="ko"):
    sections = parse_papers(raw_summary)

    if language == "ko":
        section_configs = [
            ("IR",      "International Relations",  "#8B1A1A", "#FFF5F5", "#8B1A1A"),
            ("CP",      "Comparative Politics",     "#1A3A6B", "#F0F5FF", "#1A3A6B"),
            ("METHODS", "Methods & Theory",         "#14532D", "#F0FDF4", "#14532D"),
        ]
        label_arg  = "핵심 주장"
        label_sig  = "의의"
    else:
        section_configs = [
            ("IR",      "International Relations",  "#8B1A1A", "#FFF5F5", "#8B1A1A"),
            ("CP",      "Comparative Politics",     "#1A3A6B", "#F0F5FF", "#1A3A6B"),
            ("METHODS", "Methods & Theory",         "#14532D", "#F0FDF4", "#14532D"),
        ]
        label_arg  = "Argument"
        label_sig  = "Significance"

    def method_pill(text, accent, light_bg):
        return (
            f'<span style="display:inline-block;background:{light_bg};color:{accent};'
            f'border:1px solid {accent};font-size:10px;font-weight:700;'
            f'padding:2px 9px;border-radius:3px;letter-spacing:.3px;">{text}</span>'
        )

    def label_td(text, accent):
        return (
            f'<td style="padding:5px 10px 5px 0;vertical-align:top;'
            f'width:60px;white-space:nowrap;">'
            f'<span style="font-size:9.5px;font-weight:800;color:{accent};'
            f'text-transform:uppercase;letter-spacing:1.2px;">{text}</span></td>'
        )

    def value_td(text):
        return (
            f'<td style="padding:5px 0;color:#000000;font-size:12.5px;line-height:1.75;">'
            f'{text}</td>'
        )

    sections_html = ""
    for sec_key, sec_title, accent, light_bg, _ in section_configs:
        papers = sections.get(sec_key, [])
        if not papers:
            continue

        cards_html = ""
        for idx, p in enumerate(papers):
            apsa       = p.get("apsa", "")
            method     = p.get("method", "")
            argument   = p.get("argument", "")
            significance = p.get("significance", "")
            url        = p.get("url", "#")

            # Format APSA citation: italicise *journal*
            apsa_html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', apsa)
            # Make the URL a link if present in the APSA string
            apsa_html = re.sub(
                r'(https?://\S+)',
                r'<a href="\1" style="color:#000000;text-decoration:underline;">\1</a>',
                apsa_html
            )

            pill_html = method_pill(method, accent, light_bg) if method else ""

            rows = ""
            if argument:
                rows += f"<tr>{label_td(label_arg, accent)}{value_td(argument)}</tr>"
            if significance:
                rows += f"<tr>{label_td(label_sig, '#555555')}{value_td(significance)}</tr>"

            border = "border-bottom:1px solid #E8E8E8;" if idx < len(papers) - 1 else ""

            cards_html += f"""<div style="padding:18px 0;{border}">
  <p style="margin:0 0 9px;font-size:12.5px;color:#000000;line-height:1.65;">{apsa_html}</p>
  <div style="margin-bottom:11px;">{pill_html}</div>
  <table cellpadding="0" cellspacing="0" width="100%">{rows}</table>
</div>"""

        sections_html += f"""<div style="margin-bottom:28px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">
    <tr>
      <td style="border-left:3px solid {accent};padding:0 0 0 10px;">
        <span style="font-size:11px;font-weight:800;color:{accent};
          text-transform:uppercase;letter-spacing:1.5px;">{sec_title}</span>
      </td>
    </tr>
  </table>
  <div style="background:#FFFFFF;padding:0 16px;border:1px solid #DEDEDE;border-radius:4px;">
    {cards_html}
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#E8E4DF;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#E8E4DF;padding:24px 16px;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;">

  <!-- MASTHEAD -->
  <tr><td style="background:#FFFFFF;border-top:3px solid #000000;padding:18px 24px 14px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <h1 style="margin:0 0 2px;font-size:26px;font-weight:800;color:#000000;
               font-family:Georgia,'Times New Roman',serif;letter-spacing:-.3px;">
            PoliBot's Daily Briefing
          </h1>
          <p style="margin:0;font-size:10px;color:#000000;letter-spacing:2px;
               text-transform:uppercase;font-family:-apple-system,Helvetica,sans-serif;">
            Comparative Politics &amp; International Relations
          </p>
        </td>
        <td style="text-align:right;vertical-align:middle;">
          <p style="margin:0;font-size:11px;color:#000000;
               font-family:-apple-system,Helvetica,sans-serif;">{today_str}</p>
        </td>
      </tr>
    </table>
    <div style="height:1px;background:#000000;margin-top:12px;"></div>
  </td></tr>

  <!-- BODY -->
  <tr><td style="background:#F8F7F5;padding:22px 24px 18px;
       border:1px solid #D5D0CA;border-top:none;">
    {sections_html}
    <p style="margin:16px 0 0;padding-top:12px;border-top:1px solid #CCCCCC;
       text-align:center;font-size:10px;color:#555555;
       font-family:-apple-system,Helvetica,sans-serif;">
      PoliBot &nbsp;·&nbsp; Groq Llama 3.3 70B &nbsp;·&nbsp; Crossref API &nbsp;·&nbsp;
      <a href="https://shlee-95.github.io/politics/subscribe.html"
         style="color:#000000;text-decoration:underline;">Unsubscribe</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_email(subject, html_body, recipients):
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
    seen_dois.update(p.get("DOI","") for p in papers if p.get("DOI"))
    save_seen_dois(seen_dois)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
