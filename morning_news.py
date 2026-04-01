#!/usr/bin/env python3
"""Morning news digest: fetches top headlines via Claude + web search, emails them."""

import os
import json
import logging
import smtplib
import re
import subprocess
import urllib.request
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

PROMPT = f"""Today is {TODAY}. You are an impartial morning news research assistant.

Search the web and compile a morning news digest. Follow these sourcing guidelines to minimise bias:
- Prioritise wire services and internationally recognised neutral outlets as primary sources: AP, Reuters, AFP, BBC, Bloomberg, Al Jazeera.
- Supplement with other outlets to ensure cross-ideological coverage — never rely on a single outlet or ideological cluster for any section.
- Summarise events using factual, descriptive language. Avoid loaded framing, emotional language, or editorial opinion.
- For politically contested stories, represent the key dispute neutrally without taking a side.

For each story include a "lean" field rating the primary source's general editorial lean using AllSides/Ad Fontes standards:
  "left" | "center-left" | "center" | "center-right" | "right"

Return ONLY valid JSON (no markdown, no code fences) with this exact structure:

{{
  "top_headlines": [
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center-left"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center-right"}}
  ],
  "tech_ai": [
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}}
  ],
  "business_finance": [
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}}
  ],
  "world_news": [
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}}
  ],
  "music": [
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}},
    {{"headline": "...", "summary": "2-3 sentence factual summary.", "source": "Source Name", "lean": "center"}}
  ]
}}

Use web search to find real, current news from today. Include the 3 biggest headlines of the day plus exactly 3 trending stories each from Tech & AI, Business & Finance, World News, and Music (albums, tours, industry, artists — sources: Billboard, Rolling Stone, Pitchfork, NME, Guardian Music)."""


X_TRENDING_PROMPT = f"""Today is {TODAY}. Search the web and find the top 10 currently trending topics on X (formerly Twitter).

Return ONLY a valid JSON array (no markdown, no code fences) of exactly 10 items:
[
  {{"topic": "Topic Name or #Hashtag", "posts": "approximate post count like '892K posts'", "category": "brief category: Politics, Tech, Finance, Sports, Entertainment, World, or Science"}},
  ...
]

Focus on globally significant trends. Exclude spam, bot-amplified content, and purely regional celebrity gossip."""


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
            log.info("── Content ──────────────────────────────────────────")
            for i, h in enumerate(data.get("top_headlines", []), 1):
                log.info(f"  Headline {i}: {h['headline']} ({h['source']})")
                log.info(f"    {h['summary']}")
            for section in ("tech_ai", "business_finance", "world_news"):
                items = data.get(section, [])
                if items:
                    label = section.replace("_", " & ").title()
                    for item in items:
                        log.info(f"  {label}: {item['headline']} ({item['source']})")
                        log.info(f"    {item['summary']}")
            log.info("─────────────────────────────────────────────────────")
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


def fetch_x_trending() -> list:
    log.info("Fetching X trending topics...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": X_TRENDING_PROMPT}]
    iterations = 0

    while True:
        iterations += 1
        log.info(f"X trending API call #{iterations}")
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )
        tool_uses   = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn" or not tool_uses:
            full_text = " ".join(b.text for b in text_blocks)
            full_text = re.sub(r"```(?:json)?", "", full_text).strip()
            data = json.loads(full_text)
            log.info(f"Fetched {len(data)} X trending topics")
            for i, t in enumerate(data, 1):
                log.info(f"  X {i}: {t['topic']} ({t.get('posts', '')}) [{t.get('category', '')}]")
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


def fetch_hackernews(feed: str = "topstories", n: int = 10) -> list:
    """Fetch top n HN stories from a given feed via the official public API.
    feed: 'topstories' (hot) | 'beststories' (top-rated)
    """
    log.info(f"Fetching HN {feed}...")
    with urllib.request.urlopen(
        f"https://hacker-news.firebaseio.com/v0/{feed}.json", timeout=10
    ) as r:
        ids = json.loads(r.read())[:n]

    stories = []
    for id_ in ids:
        try:
            with urllib.request.urlopen(
                f"https://hacker-news.firebaseio.com/v0/item/{id_}.json", timeout=10
            ) as r:
                item = json.loads(r.read())
            if item and item.get("type") == "story" and item.get("title"):
                stories.append({
                    "title":    item["title"],
                    "url":      item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}",
                    "hn_url":   f"https://news.ycombinator.com/item?id={item['id']}",
                    "score":    item.get("score", 0),
                    "by":       item.get("by", ""),
                    "comments": item.get("descendants", 0),
                })
        except Exception as e:
            log.warning(f"Could not fetch HN item {id_}: {e}")

    log.info(f"Fetched {len(stories)} HN {feed} stories")
    for i, s in enumerate(stories, 1):
        log.info(f"  HN {i}: {s['title']} ({s['score']} pts, {s['comments']} comments)")
    return stories


def save_news_json(data: dict, hn_hot: list, hn_top: list, x_data: list):
    out_path = os.path.join(REPO, "news.json")
    payload = {"date": TODAY, "data": {**data, "hacker_news": hn_hot, "hacker_news_top": hn_top, "x_trending": x_data}}
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

    def hn_story_html(item: dict, rank: int) -> str:
        return f"""
        <div style="margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid #e8e8e8;">
          <div style="display:flex;gap:10px;align-items:flex-start;">
            <div style="font-size:13px;font-weight:700;color:#f6993f;min-width:18px;">{rank}</div>
            <div>
              <a href="{item['url']}" style="font-size:14px;font-weight:600;color:#1a1a1a;text-decoration:none;">{item['title']}</a>
              <div style="font-size:11px;color:#999;margin-top:4px;">
                {item['score']} pts &middot; {item['comments']} comments &middot; {item['by']}
                &nbsp;&nbsp;<a href="{item['hn_url']}" style="color:#f6993f;text-decoration:none;">discuss</a>
              </div>
            </div>
          </div>
        </div>"""

    headlines_html = "".join(story_html(h) for h in data["top_headlines"])
    tech_html      = "".join(story_html(h) for h in data["tech_ai"])
    biz_html       = "".join(story_html(h) for h in data["business_finance"])
    world_html     = "".join(story_html(h) for h in data["world_news"])
    music_html     = "".join(story_html(h) for h in data.get("music", []))
    hn_html        = "".join(hn_story_html(s, i+1) for i, s in enumerate(data.get("hacker_news", [])))

    def x_trend_html(item: dict, rank: int) -> str:
        return f"""
        <div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #e8e8e8;">
          <div style="font-size:12px;font-weight:700;color:#56949f;min-width:16px;padding-top:1px;">{rank}</div>
          <div>
            <div style="font-size:13px;font-weight:600;color:#1a1a1a;">{item['topic']}</div>
            <div style="font-size:11px;color:#999;">{item.get('posts','')} &middot; {item.get('category','')}</div>
          </div>
        </div>"""

    x_html = "".join(x_trend_html(t, i+1) for i, t in enumerate(data.get("x_trending", [])))

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
          <div style="font-size:11px;font-weight:700;color:#e63946;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:16px;">Top Headlines</div>
          {headlines_html}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#457b9d;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Tech & AI</div>
          {tech_html}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#2a9d8f;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Business & Finance</div>
          {biz_html}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#e9c46a;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">World News</div>
          {world_html}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#ebbcba;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Music</div>
          {music_html}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#c4a7e7;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">HN Trending</div>
          {hn_html}
        </td></tr>
        <tr><td style="padding:10px 36px 28px;">
          <div style="font-size:11px;font-weight:700;color:#56949f;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Trending on X</div>
          {x_html}
        </td></tr>
        <tr><td style="background:#f9f9f9;padding:16px 36px;border-top:1px solid #eee;">
          <div style="font-size:12px;color:#bbb;text-align:center;">Delivered daily at 9 AM Sydney</div>
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
        log.info("Step 1/8: Fetching news")
        data = fetch_news()

        log.info("Step 2/8: Fetching HN hot (topstories)")
        hn_hot = fetch_hackernews(feed="topstories", n=10)

        log.info("Step 3/8: Fetching HN top (beststories)")
        hn_top = fetch_hackernews(feed="beststories", n=10)

        log.info("Step 4/8: Fetching X trending")
        x_data = fetch_x_trending()

        log.info("Step 5/8: Saving news.json")
        save_news_json(data, hn_hot, hn_top, x_data)

        log.info("Step 6/8: Pushing to GitHub")
        git_push()

        log.info("Step 7/8: Deploying to Netlify")
        netlify_deploy()

        log.info("Step 8/8: Sending email")
        full_data = {**data, "hacker_news": hn_hot, "hacker_news_top": hn_top, "x_trending": x_data}
        html = build_html(full_data)
        send_email(html)

        log.info("All steps completed successfully")

    except Exception:
        log.exception("Run failed with unhandled exception")
        raise

    log.info("=" * 60)
