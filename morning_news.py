#!/usr/bin/env python3
"""Morning news digest: fetches top headlines via Claude + web search, emails them."""

import os
import json
import smtplib
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import anthropic

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]

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


def fetch_news() -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": PROMPT}]

    # Agentic loop to handle web_search tool calls
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        # Collect tool uses and text
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn" or not tool_uses:
            # Extract JSON from the final text response
            full_text = " ".join(b.text for b in text_blocks)
            # Strip markdown code fences if present
            full_text = re.sub(r"```(?:json)?", "", full_text).strip()
            return json.loads(full_text)

        # Append assistant message and tool results, then continue
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": tu.input.get("query", "") if hasattr(tu, "input") else "",
            })
        messages.append({"role": "user", "content": tool_results})


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

        <!-- Header -->
        <tr><td style="background:#1a1a2e;padding:28px 36px;">
          <div style="font-size:22px;font-weight:700;color:#fff;">Your Morning News</div>
          <div style="font-size:13px;color:#aab;margin-top:4px;">{TODAY}</div>
        </td></tr>

        <!-- Top Headlines -->
        <tr><td style="padding:28px 36px 10px;">
          <div style="font-size:11px;font-weight:700;color:#e63946;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:16px;">Top 3 Headlines</div>
          {headlines_html}
        </td></tr>

        <!-- Tech & AI -->
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#457b9d;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Tech & AI</div>
          {story_html(data['tech_ai'])}
        </td></tr>

        <!-- Business & Finance -->
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#2a9d8f;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Business & Finance</div>
          {story_html(data['business_finance'])}
        </td></tr>

        <!-- World News -->
        <tr><td style="padding:10px 36px 28px;">
          <div style="font-size:11px;font-weight:700;color:#e9c46a;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">World News</div>
          {story_html(data['world_news'])}
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#f9f9f9;padding:16px 36px;border-top:1px solid #eee;">
          <div style="font-size:12px;color:#bbb;text-align:center;">Compiled by Claude · Delivered daily at 9 AM Sydney</div>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_email(html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Morning News — {TODAY}"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def save_news_json(data: dict):
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news.json")
    payload = {"date": TODAY, "data": data}
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)


def git_push():
    import subprocess
    repo = os.path.dirname(os.path.abspath(__file__))
    cmds = [
        ["git", "add", "news.json"],
        ["git", "commit", "-m", f"news: {TODAY}"],
        ["git", "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
        print(result.stdout.strip() or result.stderr.strip())


def netlify_deploy():
    import subprocess
    repo = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        ["npx", "netlify-cli", "deploy", "--prod", "--dir", "."],
        cwd=repo, capture_output=True, text=True
    )
    print(result.stdout.strip() or result.stderr.strip())


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching news...")
    data = fetch_news()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Saving news.json...")
    save_news_json(data)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Pushing to GitHub...")
    git_push()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Deploying to Netlify...")
    netlify_deploy()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Building email...")
    html = build_html(data)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Sending to {RECIPIENT_EMAIL}...")
    send_email(html)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done.")
