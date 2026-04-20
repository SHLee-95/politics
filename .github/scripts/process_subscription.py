import os
import re
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SUBSCRIBERS_FILE = Path("subscribers.json")
GMAIL_USER = "poliscibot@gmail.com"
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")

issue_title = os.environ.get("ISSUE_TITLE", "")
issue_body  = os.environ.get("ISSUE_BODY", "")

# 이메일 추출 (제목 우선, 없으면 본문)
email_match = (
    re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", issue_title) or
    re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", issue_body)
)
if not email_match:
    print("No email found.")
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write("email=unknown\n")
    raise SystemExit(0)

email = email_match.group(0).strip().lower()

# 언어 추출 — 제목의 [en] 또는 [ko] 태그
lang_match = re.search(r"\[(en|ko)\]", issue_title, re.IGNORECASE)
language = lang_match.group(1).lower() if lang_match else "ko"
print(f"Email: {email} | Language: {language}")

# subscribers.json 업데이트
if SUBSCRIBERS_FILE.exists():
    with open(SUBSCRIBERS_FILE, "r") as f:
        raw = json.load(f)
    # 기존 문자열 포맷 → 딕셔너리 포맷으로 정규화
    subscribers = []
    for item in raw:
        if isinstance(item, str):
            subscribers.append({"email": item, "language": "ko"})
        elif isinstance(item, dict) and item.get("email"):
            subscribers.append(item)
else:
    subscribers = []

existing_emails = [s["email"] for s in subscribers]
if email not in existing_emails:
    subscribers.append({"email": email, "language": language})
    print(f"Added: {email}")
else:
    for s in subscribers:
        if s["email"] == email:
            s["language"] = language
    print(f"Updated language for existing subscriber: {email}")

with open(SUBSCRIBERS_FILE, "w") as f:
    json.dump(subscribers, f, indent=2)

# GitHub Actions output
with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
    f.write(f"email={email}\n")

# 확인 이메일
if language == "en":
    subject = "[Pol-Sci Journal Bot] Subscription confirmed ✅"
    body_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;padding:24px;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table width="520" style="background:#fff;border-radius:16px;overflow:hidden;">
  <tr><td style="background:#0f172a;padding:28px 32px;text-align:center;">
    <p style="color:#94a3b8;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 6px">Pol-Sci Journal Bot</p>
    <h1 style="color:#f8fafc;font-size:20px;font-weight:700;margin:0">Subscription Confirmed</h1>
  </td></tr>
  <tr><td style="padding:28px 32px;color:#334155;font-size:14px;line-height:1.7;">
    <p>Your subscription has been confirmed!</p>
    <p style="margin-top:12px;">You'll receive daily briefings of the latest comparative politics and international relations research at <strong>{email}</strong> every morning at 9AM Eastern.</p>
    <p style="margin-top:12px;color:#64748b;font-size:13px;">To unsubscribe, reply to any briefing email or leave a comment on the GitHub issue.</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""
else:
    subject = "[Pol-Sci Journal Bot] 구독이 완료되었습니다 ✅"
    body_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;padding:24px;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table width="520" style="background:#fff;border-radius:16px;overflow:hidden;">
  <tr><td style="background:#0f172a;padding:28px 32px;text-align:center;">
    <p style="color:#94a3b8;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 6px">Pol-Sci Journal Bot</p>
    <h1 style="color:#f8fafc;font-size:20px;font-weight:700;margin:0">구독 신청 완료</h1>
  </td></tr>
  <tr><td style="padding:28px 32px;color:#334155;font-size:14px;line-height:1.7;">
    <p>구독이 완료되었습니다!</p>
    <p style="margin-top:12px;"><strong>{email}</strong> 으로 매일 오전 9시(Eastern) 비교정치학·국제정치학 최신 논문 브리핑을 보내드립니다.</p>
    <p style="margin-top:12px;color:#64748b;font-size:13px;">구독 취소를 원하시면 GitHub 이슈에 댓글을 남겨주세요.</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

try:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Pol-Sci Journal Bot <{GMAIL_USER}>"
    msg["To"] = email
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, email, msg.as_string())
    print(f"Confirmation email sent to {email}")
except Exception as e:
    print(f"Failed to send confirmation email: {e}")
