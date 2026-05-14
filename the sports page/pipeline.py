#!/usr/bin/env python3
"""
Sports Gazette Daily Pipeline
Runs every morning via GitHub Actions.
1. Fetches real scores + standings from ESPN public API
2. Calls Claude to write headlines and stories
3. Writes data.json that the site reads
"""

import json
import os
import requests
from datetime import datetime, timezone
import anthropic

# ─── ESPN API HELPERS ─────────────────────────────────────────────────────────

ESPN = "https://site.api.espn.com/apis/site/v2/sports"

def fetch_scores(sport, league):
    """Fetch yesterday's / today's scores from ESPN."""
    try:
        url = f"{ESPN}/{sport}/{league}/scoreboard"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        games = []
        for event in data.get("events", [])[:6]:
            comps = event.get("competitions", [{}])[0]
            competitors = comps.get("competitors", [])
            if len(competitors) < 2:
                continue
            # ESPN always puts away team first
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            status = comps.get("status", {}).get("type", {}).get("shortDetail", "")
            games.append({
                "away_team": away.get("team", {}).get("abbreviation", ""),
                "away_score": int(away.get("score", 0) or 0),
                "home_team": home.get("team", {}).get("abbreviation", ""),
                "home_score": int(home.get("score", 0) or 0),
                "status": status,
            })
        return games
    except Exception as e:
        print(f"  ESPN scores error ({sport}/{league}): {e}")
        return []


def fetch_standings(sport, league):
    """Fetch current standings from ESPN."""
    try:
        url = f"{ESPN}/{sport}/{league}/standings"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        divisions = []
        for group in data.get("children", data.get("standings", {}).get("entries", []))[:2]:
            div_name = group.get("name", group.get("abbreviation", ""))
            entries = group.get("standings", {}).get("entries", [])
            teams = []
            for i, entry in enumerate(entries[:5]):
                team = entry.get("team", {})
                stats = {s["name"]: s["displayValue"] for s in entry.get("stats", [])}
                teams.append({
                    "rank": i + 1,
                    "name": team.get("displayName", team.get("name", "")),
                    "w": stats.get("wins", stats.get("W", "—")),
                    "l": stats.get("losses", stats.get("L", "—")),
                    "pct": stats.get("winPercent", stats.get("PCT", ".000")),
                    "gb": stats.get("gamesBehind", stats.get("GB", "—")),
                })
            if teams:
                divisions.append({"league": div_name, "teams": teams})
        return divisions
    except Exception as e:
        print(f"  ESPN standings error ({sport}/{league}): {e}")
        return []


# ─── COLLECT ALL SPORTS DATA ──────────────────────────────────────────────────

def collect_sports_data():
    print("Fetching scores and standings from ESPN...")
    data = {
        "scores": [],
        "standings": [],
    }

    # Scores
    score_sources = [
        ("basketball", "nba"),
        ("baseball", "mlb"),
        ("football", "nfl"),
        ("hockey", "nhl"),
    ]
    for sport, league in score_sources:
        games = fetch_scores(sport, league)
        if games:
            data["scores"].append({"league": league.upper(), "games": games})
            print(f"  ✓ {league.upper()} scores: {len(games)} games")

    # Standings
    standing_sources = [
        ("basketball", "nba"),
        ("baseball", "mlb"),
    ]
    for sport, league in standing_sources:
        divs = fetch_standings(sport, league)
        data["standings"].extend(divs)
        print(f"  ✓ {league.upper()} standings: {len(divs)} divisions")

    return data


# ─── AI NEWSPAPER WRITING ─────────────────────────────────────────────────────

EDITOR_SYSTEM = """You are the sports editor of The Sports Gazette, a classic American daily newspaper.
Your job is to write the day's sports section using the real scores and standings data you are given.

Write in classic American newspaper style — inverted pyramid, vivid, specific. 
Use real names, scores, and context. Headlines in ALL CAPS, dramatic, punchy.

Respond ONLY with a valid JSON object. No markdown fences, no backticks, no preamble.
Start with { and end with }

Schema:
{
  "headline_story": {
    "sport": "sport name",
    "kicker": "SHORT KICKER IN CAPS",
    "headline": "DRAMATIC HEADLINE IN ALL CAPS",
    "deck": "A second deck that elaborates",
    "byline": "By [Full Name], Sports Writer",
    "body": "Three substantial paragraphs separated by \\n\\n. Inverted pyramid. Real details."
  },
  "secondary_stories": [
    {
      "sport": "sport",
      "kicker": "KICKER",
      "headline": "HEADLINE",
      "deck": "Deck",
      "byline": "By [Name], Staff Reporter",
      "body": "Two paragraphs separated by \\n\\n."
    },
    { ... second story ... },
    { ... third story ... }
  ],
  "column": {
    "section_title": "FROM THE PRESS BOX",
    "headline": "OPINION COLUMN HEADLINE",
    "byline": "By Pat McAllister",
    "body": "Two punchy columnist paragraphs separated by \\n\\n."
  }
}"""


def write_newspaper(sports_data):
    print("\nCalling Claude to write today's newspaper...")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""Here is today's real sports data. Write the complete Sports Gazette sports section.

SCORES:
{json.dumps(sports_data['scores'], indent=2)}

STANDINGS:
{json.dumps(sports_data['standings'], indent=2)}

Pick the most newsworthy game/story as the headline story.
Write three secondary stories covering different sports.
Write a punchy opinion column about a current sports topic.

Generate the complete JSON newspaper now."""

    message = client.messages.create(
        model="claude-sonnet-4-5-20251001",
        max_tokens=4000,
        system=EDITOR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip any accidental markdown fences
    raw = raw.replace("```json", "").replace("```", "").strip()
    # Extract the JSON object
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in Claude response")
    return json.loads(raw[start:end])


# ─── ASSEMBLE FINAL DATA.JSON ─────────────────────────────────────────────────

def build_output(sports_data, written):
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%A, %B %-d, %Y")
    edition_num = (now.timetuple().tm_yday + 142)  # fun edition number

    return {
        "generated_at": now.isoformat(),
        "date": date_str,
        "edition": f"Vol. CXLVII · No. {edition_num}",
        "weather": "Check your local forecast",  # extend: call a weather API
        "headline_story": written.get("headline_story", {}),
        "secondary_stories": written.get("secondary_stories", []),
        "scores": sports_data["scores"],
        "standings": sports_data["standings"],
        "column": written.get("column", {}),
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("=== Sports Gazette Daily Pipeline ===")
    print(f"Running at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n")

    # 1. Fetch sports data
    sports_data = collect_sports_data()

    # 2. Write newspaper content with Claude
    written = write_newspaper(sports_data)
    print("  ✓ AI writing complete")

    # 3. Assemble final output
    output = build_output(sports_data, written)

    # 4. Write to docs/data.json (served by GitHub Pages)
    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ data.json written ({len(json.dumps(output))} bytes)")
    print("✓ Pipeline complete. Today's edition is ready.")


if __name__ == "__main__":
    main()
