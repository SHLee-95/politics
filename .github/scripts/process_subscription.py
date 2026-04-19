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
issue_body = os.environ.get("ISSUE_BODY", "")

# 제목에서 먼저 이메일 추출, 없으면 본문에서
email_match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", issue_title) or \
              re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", issue_body)
if not email_match:
    print("No email found in issue body.")
    with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
        f.write("email=unknown\n")
    exit(0)

email = email_match.group(0).strip()
print(f"Found email: {email}")

# subscribers.json 업데이트
if SUBSCRIBERS_FILE.exists():
    with open(SUBSCRIBERS_FILE, "r") as f:
        subscribers = json.load(f)
else:
    subscribers = []

if email not in subscribers:
    subscribers.append(email)
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subscribers, f, indent=2)
    print(f"Added {email} to subscribers.")
else:
    print(f"{email} already subscribed.")

# GitHub Actions output
with open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a") as f:
    f.write(f"email={email}\n")

# 확인 이메일 발송
html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
  <div style="background:#1a237e;color:white;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
    <h1 style="margin:0;font-size:20px;">🌏 구독 신청 완료</h1>
  </div>
  <div style="background:white;padding:20px;border:1px solid #ddd;border-radius:0 0 8px 8px;">
    <p>안녕하세요!</p>
    <p><strong>비교정치학·국제정치학 논문 브리핑</strong> 구독이 완료되었습니다.</p>
    <p>매일 새벽 2시(Eastern)에 최신 논문 요약을 <strong>{email}</strong> 으로 보내드릴게요.</p>
    <hr>
    <p style="color:#666;font-size:12px;">구독 취소를 원하시면 GitHub 이슈에 <code>unsubscribe</code>라고 남겨주세요.</p>
  </div>
</body>
</html>"""

try:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "[polibot] 구독이 완료되었습니다 ✅"
    msg["From"] = f"Pol-Sci Journal Bot <{GMAIL_USER}>"
    msg["To"] = email
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, email, msg.as_string())
    print(f"Confirmation email sent to {email}")
except Exception as e:
    print(f"Failed to send confirmation email: {e}")
