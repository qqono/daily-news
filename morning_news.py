#!/usr/bin/env python3
"""Morning news digest: fetches top headlines via Claude + web search, emails them."""

import os
import json
import logging
import smtplib
import re
import subprocess
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import anthropic

# ── Logging setup ────────────────────────────────────────────────────────────
REPO = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(REPO, "morning_news.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
load_dotenv(os.path.join(REPO, ".env"), override=True)

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_ADDRESS     = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL   = os.environ["RECIPIENT_EMAIL"]

TODAY = datetime.now().strftime("%A, %d %B %Y")

PROMPT = f"""Today is {TODAY}. You are a morning news research assistant.

Search the web and compile a morning news digest. Return ONLY valid JSON (no markdown, no code fences) with this exact structure:

{{
  "top_headlines": [
    {{"headline": "...", "summary": "2-3 sentence summary.", "source": "Source Name"}},
    {{"headline": "...", "summary": "2-3 sentence summary.", "source": "Source Name"}},
    {{"headline": "...", "summary": "2-3 sentence summary.", "source": "Source Name"}}
  ],
  "tech_ai": {{"headline": "...", "summary": "2-3 sentence summary.", "source": "Source Name"}},
  "business_finance": {{"headline": "...", "summary": "2-3 sentence summary.", "source": "Source Name"}},
  "world_news": {{"headline": "...", "summary": "2-3 sentence summary.", "source": "Source Name"}}
}}

Use web search to find real, current news from today. Include the 3 biggest headlines of the day plus 1 trending topic each from Tech & AI, Business & Finance, and World News."""


# ── Core functions ────────────────────────────────────────────────────────────
def fetch_news() -> dict:
    log.info("Connecting to Anthropic API...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": PROMPT}]
    iterations = 0

    while True:
        iterations += 1
        log.info(f"API call #{iterations} (model: claude-sonnet-4-6)")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        tool_uses   = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if tool_uses:
            queries = [tu.input.get("query", "") for tu in tool_uses if hasattr(tu, "input")]
            log.info(f"Web searches: {queries}")

        if response.stop_reason == "end_turn" or not tool_uses:
            full_text = " ".join(b.text for b in text_blocks)
            full_text = re.sub(r"```(?:json)?", "", full_text).strip()
            data = json.loads(full_text)
            log.info(f"News fetched after {iterations} API call(s)")
            return data

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": tu.input.get("query", "") if hasattr(tu, "input") else "",
            })
        messages.append({"role": "user", "content": tool_results})


def save_news_json(data: dict):
    out_path = os.path.join(REPO, "news.json")
    payload = {"date": TODAY, "data": data}
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)
    log.info(f"news.json written to {out_path}")


def git_push():
    cmds = [
        ["git", "add", "news.json"],
        ["git", "commit", "-m", f"news: {TODAY}"],
        ["git", "push"],
    ]
    for cmd in cmds:
        log.info(f"$ {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        output = (result.stdout + result.stderr).strip()
        if output:
            for line in output.splitlines():
                log.info(f"  {line}")
        if result.returncode != 0:
            log.error(f"git command failed (exit {result.returncode})")


def netlify_deploy():
    cmd = ["npx", "netlify-cli", "deploy", "--prod", "--dir", "."]
    log.info(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    for line in (result.stdout + result.stderr).strip().splitlines():
        log.info(f"  {line}")
    if result.returncode != 0:
        log.error(f"netlify deploy failed (exit {result.returncode})")
    else:
        log.info("Netlify deploy complete")


def build_html(data: dict) -> str:
    def story_html(item: dict) -> str:
        return f"""
        <div style="margin-bottom:18px;padding-bottom:18px;border-bottom:1px solid #e8e8e8;">
          <div style="font-size:16px;font-weight:600;color:#1a1a1a;margin-bottom:6px;">{item['headline']}</div>
          <div style="font-size:14px;color:#444;line-height:1.6;">{item['summary']}</div>
          <div style="font-size:12px;color:#999;margin-top:6px;">— {item['source']}</div>
        </div>"""

    headlines_html = "".join(story_html(h) for h in data["top_headlines"])

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:30px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08);">
        <tr><td style="background:#1a1a2e;padding:28px 36px;">
          <div style="font-size:22px;font-weight:700;color:#fff;">Your Morning News</div>
          <div style="font-size:13px;color:#aab;margin-top:4px;">{TODAY}</div>
        </td></tr>
        <tr><td style="padding:28px 36px 10px;">
          <div style="font-size:11px;font-weight:700;color:#e63946;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:16px;">Top 3 Headlines</div>
          {headlines_html}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#457b9d;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Tech & AI</div>
          {story_html(data['tech_ai'])}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#2a9d8f;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Business & Finance</div>
          {story_html(data['business_finance'])}
        </td></tr>
        <tr><td style="padding:10px 36px 28px;">
          <div style="font-size:11px;font-weight:700;color:#e9c46a;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">World News</div>
          {story_html(data['world_news'])}
        </td></tr>
        <tr><td style="background:#f9f9f9;padding:16px 36px;border-top:1px solid #eee;">
          <div style="font-size:12px;color:#bbb;text-align:center;">Compiled by Claude · Delivered daily at 9 AM Sydney</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_email(html: str):
    log.info(f"Sending email to {RECIPIENT_EMAIL}...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Morning News — {TODAY}"
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)
    log.info("Email sent")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=" * 60)
    log.info(f"Morning news run started — {TODAY}")
    log.info("=" * 60)

    try:
        log.info("Step 1/5: Fetching news")
        data = fetch_news()

        log.info("Step 2/5: Saving news.json")
        save_news_json(data)

        log.info("Step 3/5: Pushing to GitHub")
        git_push()

        log.info("Step 4/5: Deploying to Netlify")
        netlify_deploy()

        log.info("Step 5/5: Sending email")
        html = build_html(data)
        send_email(html)

        log.info("All steps completed successfully")

    except Exception:
        log.exception("Run failed with unhandled exception")
        raise

    log.info("=" * 60)
