import os
import json
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SUBSCRIBERS_FILE = Path("subscribers.json")
SEEN_IDS_FILE = Path("seen_formspree_ids.json")
FORM_ID = "mjgjowen"
FORMSPREE_API_KEY = os.environ.get("FORMSPREE_API_KEY", "")
GMAIL_USER = "poliscibot@gmail.com"
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")


def load_subscribers():
    if not SUBSCRIBERS_FILE.exists():
        return []
    with open(SUBSCRIBERS_FILE) as f:
        raw = json.load(f)
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append({"email": item, "language": "ko"})
        elif isinstance(item, dict) and item.get("email"):
            result.append(item)
    return result


def load_seen_ids():
    if not SEEN_IDS_FILE.exists():
        return set()
    with open(SEEN_IDS_FILE) as f:
        return set(json.load(f))


def save_seen_ids(ids: set):
    with open(SEEN_IDS_FILE, "w") as f:
        json.dump(list(ids), f)


def fetch_submissions():
    headers = {"Authorization": f"Bearer {FORMSPREE_API_KEY}"}
    url = f"https://api.formspree.io/api/0/forms/{FORM_ID}/submissions"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("submissions", [])


def send_confirmation(email: str, language: str):
    if language == "en":
        subject = "[Pol-Sci Journal Bot] Subscription confirmed ✅"
        body_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f1f5f9;padding:24px;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table width="520" style="background:#fff;border-radius:16px;overflow:hidden;">
  <tr><td style="background:linear-gradient(135deg,#0f172a,#1e3a5f);padding:28px 32px;text-align:center;">
    <p style="color:#94a3b8;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 6px">Pol-Sci Journal Bot</p>
    <h1 style="color:#f8fafc;font-size:20px;font-weight:700;margin:0">Subscription Confirmed</h1>
  </td></tr>
  <tr><td style="padding:28px 32px;color:#334155;font-size:14px;line-height:1.7;">
    <p>Your subscription has been confirmed!</p>
    <p style="margin-top:12px;">You'll receive daily briefings of the latest comparative politics and international relations research at <strong>{email}</strong> every morning at 9AM Eastern.</p>
    <p style="margin-top:12px;color:#64748b;font-size:13px;">To unsubscribe, reply to any briefing email.</p>
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
  <tr><td style="background:linear-gradient(135deg,#0f172a,#1e3a5f);padding:28px 32px;text-align:center;">
    <p style="color:#94a3b8;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:0 0 6px">Pol-Sci Journal Bot</p>
    <h1 style="color:#f8fafc;font-size:20px;font-weight:700;margin:0">구독 신청 완료</h1>
  </td></tr>
  <tr><td style="padding:28px 32px;color:#334155;font-size:14px;line-height:1.7;">
    <p>구독이 완료되었습니다!</p>
    <p style="margin-top:12px;"><strong>{email}</strong> 으로 매일 오전 9시(Eastern) 비교정치학·국제정치학 최신 논문 브리핑을 보내드립니다.</p>
    <p style="margin-top:12px;color:#64748b;font-size:13px;">구독 취소를 원하시면 브리핑 이메일에 회신해 주세요.</p>
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
        print(f"Confirmation sent to {email}")
    except Exception as e:
        print(f"Failed to send confirmation to {email}: {e}")


def main():
    if not FORMSPREE_API_KEY:
        print("FORMSPREE_API_KEY not set, skipping.")
        return

    submissions = fetch_submissions()
    print(f"Fetched {len(submissions)} total submissions")

    seen_ids = load_seen_ids()
    subscribers = load_subscribers()
    existing_emails = {s["email"] for s in subscribers}
    new_count = 0

    for sub in submissions:
        sid = sub.get("id") or sub.get("_id", "")
        if sid in seen_ids:
            continue

        email = (sub.get("email") or sub.get("_replyto") or "").strip().lower()
        language = (sub.get("language") or "ko").strip().lower()
        if language not in ("ko", "en"):
            language = "ko"

        if not email:
            seen_ids.add(sid)
            continue

        if email not in existing_emails:
            subscribers.append({"email": email, "language": language})
            existing_emails.add(email)
            print(f"Added: {email} [{language}]")
            send_confirmation(email, language)
            new_count += 1
        else:
            print(f"Already exists: {email}")

        seen_ids.add(sid)

    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subscribers, f, indent=2)
    save_seen_ids(seen_ids)
    print(f"Done. {new_count} new subscriber(s) added.")


if __name__ == "__main__":
    main()
