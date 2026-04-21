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
각 섹션에는 먼저 분야 전체를 묶는 짧은 요약 블록을 넣고, 그 뒤에 논문 3편을 출력하세요.
반드시 아래 블록 형식만 사용하세요. 다른 텍스트는 절대 추가하지 마세요.

논문 목록:
{paper_text}

출력 형식 (이 형식을 정확히 따르세요):

[SECTION:IR]
[OVERVIEW]
summary: 오늘 국제정치 분야에서 공통적으로 드러나는 핵심 흐름과 주요 발견을 2-3문장으로 요약
implication: 이 분야 논문 묶음이 갖는 연구 시사점을 1-2문장으로 정리
[/OVERVIEW]
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
[OVERVIEW]
summary: 오늘 비교정치 분야의 핵심 흐름 요약
implication: 연구 시사점 요약
[/OVERVIEW]
[PAPER]
... (비교정치 논문 3편, 동일 형식)
[/PAPER]
[/SECTION]

[SECTION:METHODS]
[OVERVIEW]
summary: 오늘 방법론·이론 분야의 핵심 흐름 요약
implication: 연구 시사점 요약
[/OVERVIEW]
[PAPER]
... (방법론·이론 논문 3편, 동일 형식)
[/PAPER]
[/SECTION]
"""
    else:
        prompt = f"""You are an expert in comparative politics and international relations.
Select the 3 most important papers per section. For each section, first provide a short section-level overview block, then output the 3 paper blocks.
Use only the block format below. No other text.

Papers:
{paper_text}

Format (follow exactly):

[SECTION:IR]
[OVERVIEW]
summary: 2-3 sentence summary of the main pattern or overall finding across today's IR papers
implication: 1-2 sentence statement of the broader research implication for the section
[/OVERVIEW]
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
[OVERVIEW]
summary: overall pattern across today's comparative politics papers
implication: broader research implication
[/OVERVIEW]
[PAPER]
... (3 comparative politics papers, same format)
[/PAPER]
[/SECTION]

[SECTION:METHODS]
[OVERVIEW]
summary: overall pattern across today's methods/theory papers
implication: broader research implication
[/OVERVIEW]
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
    """Parse [SECTION:X]...[/SECTION], [OVERVIEW]...[/OVERVIEW], and [PAPER]...[/PAPER] blocks."""
    sections = {}
    section_pattern = re.findall(r'\[SECTION:(\w+)\](.*?)\[/SECTION\]', raw_text, re.DOTALL)
    for sec_name, sec_body in section_pattern:
        overview = {}
        overview_match = re.search(r'\[OVERVIEW\](.*?)\[/OVERVIEW\]', sec_body, re.DOTALL)
        if overview_match:
            for line in overview_match.group(1).strip().split('\n'):
                if ':' in line:
                    key, _, val = line.partition(':')
                    overview[key.strip()] = val.strip()
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
        sections[sec_name] = {"overview": overview, "papers": papers}
    return sections


def build_html_email(raw_summary, today_str, language="ko"):
    sections = parse_papers(raw_summary)

    try:
        parsed_date = datetime.strptime(today_str, "%Y-%m-%d")
    except ValueError:
        parsed_date = None

    if language == "ko":
        section_configs = [
            ("IR",      "국제정치",        "#1E40AF", "#F0F4FF"),
            ("CP",      "비교정치",        "#065F46", "#F0FBF7"),
            ("METHODS", "방법론 및 이론", "#4C1D95", "#F5F0FD"),
        ]
        font_stack = '-apple-system, BlinkMacSystemFont, \"Noto Sans KR\", \"Malgun Gothic\", sans-serif'
        title_stack = '-apple-system, BlinkMacSystemFont, \"Noto Sans KR\", \"Malgun Gothic\", sans-serif'
        label_arg  = "핵심 주장"
        label_sig  = "의의"
        overview_summary_label = "분야 동향"
        overview_implication_label = "연구 시사점"
        display_date = parsed_date.strftime("%Y년 %m월 %d일") if parsed_date else today_str
        day_of_week = parsed_date.strftime("%A") if parsed_date else ""
        day_map = {"Monday":"월요일","Tuesday":"화요일","Wednesday":"수요일","Thursday":"목요일",
                   "Friday":"금요일","Saturday":"토요일","Sunday":"일요일"}
        display_dow = day_map.get(day_of_week, day_of_week)
        disclaimer_title = "Disclaimer"
        disclaimer_body = (
            "본 브리핑의 논문 선정, 핵심 요약 및 의의 정리는 AI 생성 결과를 포함할 수 있으며, "
            "운영자 또는 기여자의 독립적인 학술적 판단이나 견해 또는 소개된 자료에 대한 지지, 보증, 승인 또는 의견 표명으로 해석될 수 없습니다. "
            "본 브리핑에서 소개되거나 참조된 논문, 학술 자료 및 기타 일체의 정보에 대한 권리는 각 권리자 또는 그 법률대리인에게 있습니다. "
            "본 브리핑은 연구 및 정보 제공 목적으로만 제공되며, 학술적, 법적 또는 정책적 조언으로 해석될 수 없습니다. "
            "제공되는 정보의 정확성, 완전성, 신뢰성 또는 적합성에 대하여 어떠한 명시적 또는 묵시적 보증도 하지 않으며, "
            "그 해석 및 활용에 대한 책임은 전적으로 독자에게 있습니다."
        )
        unsubscribe_text = "구독 해지"
    else:
        section_configs = [
            ("IR",      "International Relations", "#1E40AF", "#F0F4FF"),
            ("CP",      "Comparative Politics",    "#065F46", "#F0FBF7"),
            ("METHODS", "Methods & Theory",        "#4C1D95", "#F5F0FD"),
        ]
        font_stack = '-apple-system, BlinkMacSystemFont, \"Segoe UI\", \"Helvetica Neue\", Arial, sans-serif'
        title_stack = '-apple-system, BlinkMacSystemFont, \"Segoe UI\", \"Helvetica Neue\", Arial, sans-serif'
        label_arg  = "Argument"
        label_sig  = "Significance"
        overview_summary_label = "Overview"
        overview_implication_label = "Implication"
        display_date = parsed_date.strftime("%B %d, %Y") if parsed_date else today_str
        display_dow = parsed_date.strftime("%A") if parsed_date else ""
        disclaimer_title = "Disclaimer"
        disclaimer_body = (
            "Article selection, core summaries, and significance statements in this briefing may include AI-generated output "
            "and cannot be construed as the independent scholarly judgment or views of the operator or contributor, or as "
            "endorsement, warranty, approval, or expression of opinion regarding any referenced material. Rights in articles, "
            "scholarly materials, and any other information introduced or referenced in this briefing remain with the respective "
            "rights holders or their legal representatives. This briefing is provided solely for research and informational purposes "
            "and cannot be construed as academic, legal, or policy advice. No express or implied warranty is made as to the accuracy, "
            "completeness, reliability, or fitness of the information provided, and sole responsibility for its interpretation and use "
            "rests with the reader."
        )
        unsubscribe_text = "Unsubscribe"

    ls = "0" if language == "ko" else ".6px"
    tt = "none" if language == "ko" else "uppercase"

    def label_tag(text, accent):
        return (
            f'<span style="display:inline-block;background:transparent;color:{accent};'
            f'border:1px solid {accent};font-size:11px;font-weight:700;padding:2px 9px;'
            f'border-radius:3px;letter-spacing:{ls};text-transform:{tt};line-height:1.5;'
            f'font-family:{font_stack};">{text}</span>'
        )

    def method_pill(text):
        return (
            f'<span style="display:inline-block;background:#F3F4F6;color:#374151;'
            f'font-size:11.5px;font-weight:500;padding:3px 10px;border-radius:4px;'
            f'letter-spacing:.05px;line-height:1.4;font-family:{font_stack};">'
            f'&#128300; {text}</span>'
        )

    def note_block(label, text, accent):
        return (
            f'<div style="margin-top:13px;">'
            f'<div style="margin-bottom:5px;">{label_tag(label, accent)}</div>'
            f'<div class="body-text" style="color:#1F2937;font-size:15px;line-height:1.9;'
            f'font-family:{font_stack};">{text}</div>'
            f'</div>'
        )

    def extract_title(paper):
        direct = (paper.get("title") or "").strip()
        if direct:
            return direct
        apsa = (paper.get("apsa") or "").strip()
        match = re.search(r'"([^"]+)"', apsa)
        if match:
            return match.group(1).strip()
        return ""

    sections_html = ""
    for sec_key, sec_title, accent, light_bg in section_configs:
        sec_data = sections.get(sec_key, {})
        papers = sec_data.get("papers", [])
        overview = sec_data.get("overview", {})
        if not papers:
            continue

        overview_html = ""
        if overview.get("summary") or overview.get("implication"):
            ov_blocks = ""
            if overview.get("summary"):
                ov_blocks += note_block(overview_summary_label, overview["summary"], accent)
            if overview.get("implication"):
                ov_blocks += note_block(overview_implication_label, overview["implication"], accent)
            overview_html = (
                f'<div style="margin:0 0 26px;padding:16px 20px;'
                f'background:{light_bg};border-left:3px solid {accent};border-radius:0 6px 6px 0;">'
                f'{ov_blocks}'
                f'</div>'
            )

        cards_html = ""
        for idx, p in enumerate(papers):
            apsa         = p.get("apsa", "")
            method       = p.get("method", "")
            argument     = p.get("argument", "")
            significance = p.get("significance", "")
            url          = p.get("url", "#")
            title_text   = extract_title(p)

            apsa_html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', apsa)
            apsa_html = re.sub(
                r'(https?://\S+)',
                r'<a href="\1" style="color:#6B7280;text-decoration:underline;">\1</a>',
                apsa_html
            )

            pill_html = method_pill(method) if method else ""

            blocks = ""
            if argument:
                blocks += note_block(label_arg, argument, accent)
            if significance:
                blocks += note_block(label_sig, significance, accent)

            sep = (
                '<div style="height:1px;background:#E5E7EB;margin:26px 0;"></div>'
                if idx < len(papers) - 1 else ""
            )

            title_html = ""
            if title_text:
                title_html = (
                    f'<h2 class="paper-title" style="margin:0 0 7px;font-size:19px;line-height:1.4;'
                    f'font-weight:700;color:#111827;letter-spacing:-0.01em;font-family:{title_stack};">'
                    f'<a href="{url}" style="color:#111827;text-decoration:none;">{title_text}</a>'
                    f'</h2>'
                )

            cards_html += f"""<div>
  {title_html}
  <p class="citation-text" style="margin:0 0 10px;font-size:13px;color:#6B7280;line-height:1.7;
     font-family:{font_stack};">{apsa_html}</p>
  <div style="margin-bottom:2px;">{pill_html}</div>
  {blocks}
</div>{sep}"""

        sections_html += f"""<div style="margin-bottom:32px;background:#FFFFFF;
  border:1px solid #E5E7EB;border-radius:8px;overflow:hidden;">
  <div style="padding:16px 24px 14px;background:{accent};">
    <span class="section-heading" style="font-size:20px;font-weight:800;color:#FFFFFF;
      letter-spacing:{ls};font-family:{font_stack};">{sec_title}</span>
  </div>
  <div style="padding:24px 24px 20px;">
    {overview_html}
    {cards_html}
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap" rel="stylesheet">
  <style>
    body, table, td, p, a, span {{
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
    }}
    @media only screen and (max-width: 640px) {{
      .email-shell {{ width: 100% !important; }}
      .email-wrap  {{ padding: 10px 0 !important; }}
      .masthead    {{ padding: 22px 18px 18px !important; }}
      .email-body  {{ padding: 16px 12px !important; }}
      .briefing-title  {{ font-size: 24px !important; line-height: 1.2 !important; }}
      .paper-title     {{ font-size: 17px !important; line-height: 1.4 !important; }}
      .section-heading {{ font-size: 10px !important; }}
      .body-text   {{ font-size: 14px !important; line-height: 1.85 !important; }}
      .citation-text {{ font-size: 12px !important; }}
      .footer-text, .disclaimer-text {{ font-size: 11px !important; line-height: 1.65 !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background:#F1F3F5;">
<table width="100%" cellpadding="0" cellspacing="0" class="email-wrap" style="background:#F1F3F5;padding:24px 14px;">
<tr><td align="center">
<table width="660" cellpadding="0" cellspacing="0" class="email-shell" style="max-width:660px;width:100%;">

  <!-- MASTHEAD -->
  <tr><td class="masthead" style="background:#111827;padding:26px 30px 22px;border-radius:8px 8px 0 0;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="vertical-align:middle;">
          <h1 class="briefing-title" style="margin:0 0 3px;font-size:26px;font-weight:800;color:#F9FAFB;
               font-family:{title_stack};letter-spacing:-.025em;line-height:1.2;">
            PoliBot Daily
          </h1>
          <p style="margin:0;font-size:12px;color:#9CA3AF;font-family:{font_stack};letter-spacing:.1px;">
            {display_dow + " · " if display_dow else ""}{display_date}
          </p>
        </td>
        <td style="text-align:right;vertical-align:middle;">
          <p style="margin:0;font-size:10px;font-weight:600;letter-spacing:1.2px;
               text-transform:uppercase;color:#4B5563;font-family:{font_stack};">
            Political Science<br>Journal Briefing
          </p>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- BODY -->
  <tr><td class="email-body" style="background:#F1F3F5;padding:20px 16px 16px;">
    {sections_html}
    <div style="margin-top:4px;padding:14px 18px;background:#FFFFFF;
         border:1px solid #E5E7EB;border-radius:6px;">
      <p style="margin:0 0 5px;font-size:9px;font-weight:700;letter-spacing:1.2px;
           text-transform:uppercase;color:#9CA3AF;font-family:{font_stack};">
        {disclaimer_title}
      </p>
      <p class="disclaimer-text" style="margin:0;font-size:11.5px;line-height:1.7;color:#9CA3AF;
           font-family:{font_stack};">
        {disclaimer_body}
      </p>
    </div>
    <p class="footer-text" style="margin:16px 0 0;text-align:center;font-size:11.5px;
       line-height:1.6;color:#9CA3AF;font-family:{font_stack};">
      PoliBot &nbsp;·&nbsp; Groq Llama 3.3 70B &nbsp;·&nbsp; Crossref API
      &nbsp;·&nbsp;
      <a href="https://shlee-95.github.io/politics/subscribe.html"
         style="color:#6B7280;text-decoration:underline;">{unsubscribe_text}</a>
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
