#!/usr/bin/env python3
"""Morning news digest: fetches top headlines via Claude + web search, emails them."""

import os
import json
import logging
import smtplib
import re
import subprocess
import time
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

Search the web and compile a morning news digest with zero bias and zero overlap between sections.

SOURCING GUIDELINES:
- Wire services first (AP, Reuters, AFP) — use these as primary sources wherever possible.
- International neutral outlets: Al Jazeera English, DW (Deutsche Welle), France 24, NHK World, PBS NewsHour, RFI, Euronews, ABC Australia.
- Quality independent/investigative outlets: The Guardian, ProPublica, 404 Media, The Intercept, Der Spiegel (English), South China Morning Post, The Hindu, Haaretz, Kyodo News, The Wire India.
- Tech & AI specialist outlets: Ars Technica, MIT Technology Review, IEEE Spectrum, The Verge, Wired, 404 Media.
- Business/Finance specialist outlets: Financial Times, Nikkei Asia, Reuters, Bloomberg, The Economist.
- Music specialist outlets: Billboard, Pitchfork, The FADER, Stereogum, NME, Consequence.
- AVOID: Fox News, MSNBC, Daily Mail, Breitbart, Infowars, RT, CGTN, Xinhua, Sputnik, or any outlet with an extreme ideological lean.
- NEVER use the same outlet more than once across all sections combined.
- NEVER repeat the same event across sections — every story must cover a genuinely different development.

For each story include a "lean" field using AllSides/Ad Fontes standards:
  "left" | "center-left" | "center" | "center-right" | "right"

Return ONLY valid JSON (no markdown, no code fences) in this exact structure:

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

Use web search for all 5 sections. The 3 top_headlines must be the most globally significant stories of the day. All 5 sections need exactly 3 stories each, all distinct events and distinct sources."""


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
        for _attempt in range(6):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                wait = 60 * (_attempt + 1)
                log.warning(f"Rate limited — waiting {wait}s before retry {_attempt + 1}/6")
                time.sleep(wait)
        else:
            raise RuntimeError("Rate limit exceeded after 6 attempts")

        log.info(f"  stop_reason={response.stop_reason}")

        tool_uses   = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if tool_uses:
            queries = [tu.input.get("query", "") for tu in tool_uses if hasattr(tu, "input")]
            log.info(f"Web searches: {queries}")

        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"Response truncated after {iterations} call(s) — increase max_tokens")

        if response.stop_reason == "end_turn":
            raw_text = " ".join(b.text for b in text_blocks)
            log.info(f"  end_turn: text_blocks={len(text_blocks)}, raw_len={len(raw_text)}, tool_uses={len(tool_uses)}")
            # Strip code fences then extract the JSON object from wherever it sits in the text
            raw_text = re.sub(r"```(?:json)?", "", raw_text)
            m = re.search(r'(\{[\s\S]*\})', raw_text)
            full_text = m.group(1).strip() if m else ""
            log.info(f"  extracted json len={len(full_text)}")
            if full_text:
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
            elif not tool_uses:
                raise RuntimeError("end_turn with no text and no tool_uses — model returned nothing")
            # else: end_turn with tool_uses but no text — fall through to process tool calls

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
        for _attempt in range(6):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                wait = 60 * (_attempt + 1)
                log.warning(f"Rate limited — waiting {wait}s before retry {_attempt + 1}/6")
                time.sleep(wait)
        else:
            raise RuntimeError("X trending rate limit exceeded after 6 attempts")
        tool_uses   = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        log.info(f"  stop_reason={response.stop_reason}, tool_uses={len(tool_uses)}, text_blocks={len(text_blocks)}")

        if response.stop_reason == "max_tokens":
            raise RuntimeError("X trending response truncated — increase max_tokens")

        if response.stop_reason == "end_turn":
            raw_text = " ".join(b.text for b in text_blocks)
            log.info(f"  X end_turn: text_blocks={len(text_blocks)}, raw_len={len(raw_text)}, tool_uses={len(tool_uses)}")
            raw_text = re.sub(r"```(?:json)?", "", raw_text)
            # Extract JSON array or object from the response
            m = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', raw_text)
            full_text = m.group(1).strip() if m else ""
            log.info(f"  X extracted json len={len(full_text)}")
            if full_text:
                data = json.loads(full_text)
                log.info(f"Fetched {len(data)} X trending topics")
                for i, t in enumerate(data, 1):
                    log.info(f"  X {i}: {t['topic']} ({t.get('posts', '')}) [{t.get('category', '')}]")
                return data
            elif not tool_uses:
                raise RuntimeError("X trending: end_turn with no text and no tool_uses — model returned nothing")
            # else: end_turn with tool_uses but no text — fall through to process tool calls

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


def fetch_github_trending(n: int = 10) -> list:
    """Scrape github.com/trending for the top n repos."""
    log.info("Fetching GitHub trending...")
    url = "https://github.com/trending"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log.warning(f"GitHub trending fetch failed: {e}")
        return []

    _SKIP = {"sponsors", "trending", "explore", "marketplace", "orgs",
             "settings", "login", "signup", "features", "about", "contact"}
    _HTML_ENTITIES = {"&amp;": "&", "&lt;": "<", "&gt;": ">",
                      "&quot;": '"', "&#39;": "'", "&apos;": "'"}

    def strip_tags(s):
        s = re.sub(r'<[^>]+>', '', s)
        s = re.sub(r'\s+', ' ', s).strip()
        for ent, ch in _HTML_ENTITIES.items():
            s = s.replace(ent, ch)
        return s

    repos = []
    for art in re.findall(r'<article[^>]*Box-row[^>]*>(.*?)</article>', html, re.DOTALL)[:n]:
        path = None
        for m in re.finditer(r'href="/([^/"?#]+/[^/"?#]+)"', art):
            candidate = m.group(1).strip()
            owner = candidate.split("/")[0]
            if owner not in _SKIP and candidate.count("/") == 1:
                path = candidate
                break
        if not path:
            continue

        # GitHub description is in a <p class="col-9 ..."> element
        desc_m = (re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', art, re.DOTALL)
                  or re.search(r'<p[^>]*>(.*?)</p>', art, re.DOTALL))
        description = strip_tags(desc_m.group(1)) if desc_m else "No description"
        # Strip any leading "Sponsor Star owner / repo" artefact
        description = re.sub(r'^(?:Sponsor\s+)?Star\s+[\w.\-]+\s*/\s*[\w.\-]+\s*', '', description).strip() or "No description"

        today_m = re.search(r'([\d,]+)\s+stars?\s+today', art, re.IGNORECASE)
        stars_today = today_m.group(1) if today_m else "0"

        lang_m = re.search(r'itemprop="programmingLanguage"[^>]*>\s*([^<]+?)\s*<', art)
        language = lang_m.group(1).strip() if lang_m else ""

        repos.append({
            "name":        path,
            "description": description[:140],
            "stars_today": stars_today,
            "language":    language,
            "url":         f"https://github.com/{path}",
        })

    log.info(f"Fetched {len(repos)} GitHub trending repos")
    for i, r in enumerate(repos, 1):
        log.info(f"  GH {i}: {r['name']} ({r['stars_today']} ★ today) [{r['language']}]")
    return repos


def fetch_reddit_trending(n: int = 10) -> list:
    """Fetch top posts from r/popular via Reddit's public JSON API."""
    log.info("Fetching Reddit trending...")
    # Use old.reddit.com — the modern domain blocks non-browser requests
    url = f"https://old.reddit.com/r/popular/hot.json?limit={n}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read())
    except Exception as e:
        log.warning(f"Reddit trending fetch failed: {e}")
        return []

    posts = []
    for child in raw["data"]["children"][:n]:
        d = child["data"]
        # Use d["title"] — the actual post title, NOT d["name"] (the ID like "t3_xxxx")
        title = d.get("title", "")
        title = (title.replace("&amp;", "&").replace("&lt;", "<")
                      .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
        posts.append({
            "title":     title,
            "subreddit": d.get("subreddit_name_prefixed", ""),
            "score":     d.get("score", 0),
            "comments":  d.get("num_comments", 0),
            "url":       d.get("url", ""),
            "permalink": f"https://reddit.com{d.get('permalink', '')}",
        })

    log.info(f"Fetched {len(posts)} Reddit posts")
    for i, p in enumerate(posts, 1):
        log.info(f"  Reddit {i}: {p['title'][:60]} ({p['subreddit']})")
    return posts


def save_news_json(data: dict, hn_hot: list, hn_top: list, x_data: list,
                   github_data: list, reddit_data: list):
    out_path = os.path.join(REPO, "news.json")
    payload = {
        "date": TODAY,
        "data": {
            **data,
            "hacker_news":     hn_hot,
            "hacker_news_top": hn_top,
            "x_trending":      x_data,
            "github_trending": github_data,
            "reddit_trending": reddit_data,
        },
    }
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

    def gh_story_html(item: dict, rank: int) -> str:
        return f"""
        <div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #e8e8e8;">
          <div style="font-size:12px;font-weight:700;color:#31748f;min-width:16px;padding-top:1px;">{rank}</div>
          <div>
            <a href="{item['url']}" style="font-size:13px;font-weight:600;color:#1a1a1a;text-decoration:none;">{item['name']}</a>
            <div style="font-size:11px;color:#555;margin-top:2px;">{item['description']}</div>
            <div style="font-size:11px;color:#999;margin-top:2px;">{item.get('language','') + ' · ' if item.get('language') else ''}★ {item['stars_today']} today</div>
          </div>
        </div>"""

    def reddit_story_html(item: dict, rank: int) -> str:
        return f"""
        <div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #e8e8e8;">
          <div style="font-size:12px;font-weight:700;color:#eb6f92;min-width:16px;padding-top:1px;">{rank}</div>
          <div>
            <a href="{item['permalink']}" style="font-size:13px;font-weight:600;color:#1a1a1a;text-decoration:none;">{item['title']}</a>
            <div style="font-size:11px;color:#999;margin-top:2px;">{item['subreddit']} · {item['score']:,} pts · {item['comments']} comments</div>
          </div>
        </div>"""

    gh_html     = "".join(gh_story_html(r, i+1) for i, r in enumerate(data.get("github_trending", [])))
    reddit_html = "".join(reddit_story_html(p, i+1) for i, p in enumerate(data.get("reddit_trending", [])))

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
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#31748f;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">GitHub Trending</div>
          {gh_html}
        </td></tr>
        <tr><td style="padding:10px 36px;">
          <div style="font-size:11px;font-weight:700;color:#eb6f92;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:12px;">Reddit Popular</div>
          {reddit_html}
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
        log.info("Step 1/10: Fetching news")
        data = fetch_news()

        log.info("Step 2/10: Fetching HN hot (topstories)")
        hn_hot = fetch_hackernews(feed="topstories", n=10)

        log.info("Step 3/10: Fetching HN top (beststories)")
        hn_top = fetch_hackernews(feed="beststories", n=10)

        log.info("Step 4/10: Fetching X trending")
        x_data = fetch_x_trending()

        log.info("Step 5/10: Fetching GitHub trending")
        github_data = fetch_github_trending(n=10)

        log.info("Step 6/10: Fetching Reddit trending")
        reddit_data = fetch_reddit_trending(n=10)

        log.info("Step 7/10: Saving news.json")
        save_news_json(data, hn_hot, hn_top, x_data, github_data, reddit_data)

        log.info("Step 8/10: Pushing to GitHub")
        git_push()

        log.info("Step 9/10: Deploying to Netlify")
        netlify_deploy()

        log.info("Step 10/10: Sending email")
        full_data = {
            **data,
            "hacker_news": hn_hot, "hacker_news_top": hn_top,
            "x_trending": x_data, "github_trending": github_data,
            "reddit_trending": reddit_data,
        }
        html = build_html(full_data)
        send_email(html)

        log.info("All steps completed successfully")

    except Exception:
        log.exception("Run failed with unhandled exception")
        raise

    log.info("=" * 60)
