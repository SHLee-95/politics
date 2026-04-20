import os
import json
import imaplib
import email
import smtplib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

SUBSCRIBERS_FILE = Path("subscribers.json")
SEEN_IDS_FILE = Path("seen_formspree_ids.json")
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


def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
    return body


def fetch_formspree_submissions():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL_USER, GMAIL_PASSWORD)
    mail.select("inbox")

    _, message_ids = mail.search(None, '(FROM "formspree.io" UNSEEN)')
    ids = message_ids[0].split()
    print(f"Found {len(ids)} unread Formspree notification(s)")

    submissions = []
    for msg_id in ids:
        _, msg_data = mail.fetch(msg_id, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        body = get_email_body(msg)

        # strip HTML tags if body is HTML
        body_clean = re.sub(r"<[^>]+>", " ", body)

        email_match = re.search(
            r"email[\s:]+([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
            body_clean, re.IGNORECASE
        )
        lang_match = re.search(
            r"language[\s:]+(ko|en)", body_clean, re.IGNORECASE
        )

        if email_match:
            submissions.append({
                "id": msg_id.decode(),
                "email": email_match.group(1).strip().lower(),
                "language": lang_match.group(1).lower() if lang_match else "ko",
            })
            mail.store(msg_id, "+FLAGS", "\\Seen")
        else:
            print(f"Could not parse email from Formspree notification (msg {msg_id})")

    mail.close()
    mail.logout()
    return submissions


def send_confirmation(recipient: str, language: str):
    if language == "en":
        subject = "[Pol-Sci Journal Bot] Subscription confirmed"
        body_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#0f172a;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a;padding:40px 16px;">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;">

  <!-- Header -->
  <tr><td style="background-color:#0f172a;padding:32px 40px 24px;text-align:center;">
    <p style="color:#64748b;font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;margin:0 0 10px 0;font-family:Arial,sans-serif;">Pol-Sci Journal Bot</p>
    <div style="display:inline-block;background-color:#166534;border-radius:50%;width:56px;height:56px;line-height:56px;text-align:center;font-size:28px;margin-bottom:16px;">✓</div>
    <h1 style="color:#f8fafc;font-size:22px;font-weight:700;margin:0;font-family:Arial,sans-serif;">Subscription Confirmed</h1>
  </td></tr>

  <!-- Divider -->
  <tr><td style="background-color:#1e3a5f;height:4px;font-size:0;line-height:0;">&nbsp;</td></tr>

  <!-- Body -->
  <tr><td style="padding:32px 40px;background-color:#ffffff;">
    <p style="color:#0f172a;font-size:15px;font-weight:600;margin:0 0 12px 0;font-family:Arial,sans-serif;">Welcome aboard!</p>
    <p style="color:#334155;font-size:14px;line-height:1.8;margin:0 0 16px 0;font-family:Arial,sans-serif;">
      You'll receive daily briefings of the latest <strong style="color:#0f172a;">comparative politics</strong> and <strong style="color:#0f172a;">international relations</strong> research every morning at <strong style="color:#0f172a;">9 AM Eastern</strong>.
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border-radius:10px;margin:20px 0;">
      <tr><td style="padding:16px 20px;">
        <p style="color:#64748b;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin:0 0 4px 0;font-family:Arial,sans-serif;">Delivering to</p>
        <p style="color:#0f172a;font-size:14px;font-weight:600;margin:0;font-family:Arial,sans-serif;">{recipient}</p>
      </td></tr>
    </table>
    <p style="color:#94a3b8;font-size:12px;margin:0;font-family:Arial,sans-serif;">To unsubscribe, reply to any briefing email.</p>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
    <p style="color:#94a3b8;font-size:11px;margin:0;font-family:Arial,sans-serif;">Pol-Sci Journal Bot · Comparative Politics & IR · Daily at 9AM ET</p>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""
    else:
        subject = "[Pol-Sci Journal Bot] 구독이 완료되었습니다"
        body_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#0f172a;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a;padding:40px 16px;">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;">

  <!-- Header -->
  <tr><td style="background-color:#0f172a;padding:32px 40px 24px;text-align:center;">
    <p style="color:#64748b;font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;margin:0 0 10px 0;font-family:Arial,sans-serif;">Pol-Sci Journal Bot</p>
    <div style="display:inline-block;background-color:#166534;border-radius:50%;width:56px;height:56px;line-height:56px;text-align:center;font-size:28px;margin-bottom:16px;">✓</div>
    <h1 style="color:#f8fafc;font-size:22px;font-weight:700;margin:0;font-family:Arial,sans-serif;">구독 신청 완료</h1>
  </td></tr>

  <!-- Divider -->
  <tr><td style="background-color:#1e3a5f;height:4px;font-size:0;line-height:0;">&nbsp;</td></tr>

  <!-- Body -->
  <tr><td style="padding:32px 40px;background-color:#ffffff;">
    <p style="color:#0f172a;font-size:15px;font-weight:600;margin:0 0 12px 0;font-family:Arial,sans-serif;">구독해 주셔서 감사합니다!</p>
    <p style="color:#334155;font-size:14px;line-height:1.8;margin:0 0 16px 0;font-family:Arial,sans-serif;">
      매일 오전 <strong style="color:#0f172a;">9시(Eastern)</strong> <strong style="color:#0f172a;">비교정치학 · 국제정치학</strong> 최신 논문 브리핑을 보내드립니다.
    </p>
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;border-radius:10px;margin:20px 0;">
      <tr><td style="padding:16px 20px;">
        <p style="color:#64748b;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin:0 0 4px 0;font-family:Arial,sans-serif;">수신 이메일</p>
        <p style="color:#0f172a;font-size:14px;font-weight:600;margin:0;font-family:Arial,sans-serif;">{recipient}</p>
      </td></tr>
    </table>
    <p style="color:#94a3b8;font-size:12px;margin:0;font-family:Arial,sans-serif;">구독 취소를 원하시면 브리핑 이메일에 회신해 주세요.</p>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background-color:#f1f5f9;padding:16px 40px;text-align:center;">
    <p style="color:#94a3b8;font-size:11px;margin:0;font-family:Arial,sans-serif;">Pol-Sci Journal Bot · 비교정치학 & 국제정치학 · 매일 오전 9시 ET</p>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Pol-Sci Journal Bot <{GMAIL_USER}>"
        msg["To"] = recipient
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, recipient, msg.as_string())
        print(f"Confirmation sent to {recipient}")
    except Exception as e:
        print(f"Failed to send confirmation to {recipient}: {e}")


def main():
    submissions = fetch_formspree_submissions()
    seen_ids = load_seen_ids()
    subscribers = load_subscribers()
    existing_emails = {s["email"] for s in subscribers}
    new_count = 0

    for sub in submissions:
        sid = sub["id"]
        if sid in seen_ids:
            continue

        subscriber_email = sub["email"]
        language = sub["language"]

        if subscriber_email not in existing_emails:
            subscribers.append({"email": subscriber_email, "language": language})
            existing_emails.add(subscriber_email)
            print(f"Added: {subscriber_email} [{language}]")
            send_confirmation(subscriber_email, language)
            new_count += 1
        else:
            print(f"Already exists: {subscriber_email}")

        seen_ids.add(sid)

    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subscribers, f, indent=2)
    save_seen_ids(seen_ids)
    print(f"Done. {new_count} new subscriber(s) added.")


if __name__ == "__main__":
    main()
