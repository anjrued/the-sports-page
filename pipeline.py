#!/usr/bin/env python3
"""
The Sports Page — Daily Pipeline
Fetches real scores/standings from ESPN, writes AI stories for each section.
"""

import json, os, requests
from datetime import datetime, timezone
import anthropic

ESPN = "https://site.api.espn.com/apis/site/v2/sports"

# ── ESPN HELPERS ──────────────────────────────────────────────────────────────

def fetch_scores(sport, league, limit=10):
    try:
        r = requests.get(f"{ESPN}/{sport}/{league}/scoreboard", timeout=10)
        r.raise_for_status()
        games = []
        for event in r.json().get("events", [])[:limit]:
            comp = event.get("competitions", [{}])[0]
            teams = comp.get("competitors", [])
            if len(teams) < 2: continue
            home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
            away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])
            status = comp.get("status", {}).get("type", {}).get("shortDetail", "")
            games.append({
                "away": away.get("team", {}).get("abbreviation", ""),
                "away_score": int(away.get("score", 0) or 0),
                "home": home.get("team", {}).get("abbreviation", ""),
                "home_score": int(home.get("score", 0) or 0),
                "status": status,
            })
        return games
    except Exception as e:
        print(f"  scores error {sport}/{league}: {e}")
        return []

def fetch_standings(sport, league, max_divs=6):
    try:
        r = requests.get(f"{ESPN}/{sport}/{league}/standings", timeout=10)
        r.raise_for_status()
        divs = []
        for group in r.json().get("children", [])[:max_divs]:
            label = group.get("name", group.get("abbreviation", ""))
            teams = []
            for i, entry in enumerate(group.get("standings", {}).get("entries", [])[:6]):
                tm = entry.get("team", {})
                stats = {s["name"]: s["displayValue"] for s in entry.get("stats", [])}
                teams.append({
                    "rank": i + 1,
                    "name": tm.get("displayName", ""),
                    "w":    stats.get("wins",        stats.get("W",   "—")),
                    "l":    stats.get("losses",      stats.get("L",   "—")),
                    "pct":  stats.get("winPercent",  stats.get("PCT", ".000")),
                    "gb":   stats.get("gamesBehind", stats.get("GB",  "—")),
                })
            if teams:
                divs.append({"label": label, "teams": teams})
        return divs
    except Exception as e:
        print(f"  standings error {sport}/{league}: {e}")
        return []

def fetch_schedule(sport, league, limit=13):
    try:
        r = requests.get(f"{ESPN}/{sport}/{league}/scoreboard", timeout=10)
        r.raise_for_status()
        games = []
        for event in r.json().get("events", [])[:limit]:
            comp = event.get("competitions", [{}])[0]
            teams = comp.get("competitors", [])
            if len(teams) < 2: continue
            home = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
            away = next((t for t in teams if t.get("homeAway") == "away"), teams[1])
            status = comp.get("status", {}).get("type", {}).get("shortDetail", "TBD")
            home_pitcher = home.get("probables", [{}])[0].get("displayName", "") if home.get("probables") else ""
            away_pitcher = away.get("probables", [{}])[0].get("displayName", "") if away.get("probables") else ""
            game = {
                "time": status,
                "away": away.get("team", {}).get("displayName", ""),
                "home": home.get("team", {}).get("displayName", ""),
            }
            if away_pitcher: game["asp"] = away_pitcher
            if home_pitcher: game["hsp"] = home_pitcher
            games.append(game)
        return games
    except Exception as e:
        print(f"  schedule error {sport}/{league}: {e}")
        return []

# ── AI WRITING ────────────────────────────────────────────────────────────────

SYS = """You are the sports editor of The Sports Page, a classic American daily newspaper.
Write vivid newspaper journalism — inverted pyramid, specific, real player names.
No em-dashes. No first person. Respond ONLY with a valid JSON object starting with { and ending with }. No markdown, no backticks."""

def claude_call(client, prompt, max_tokens=1200):
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=SYS,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip().replace("```json","").replace("```","").strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    return json.loads(raw[start:end])

def write_front(client, mlb, nba, nhl):
    return claude_call(client, f"""Write today's front page for The Sports Page newspaper.

Top scores:
MLB: {json.dumps(mlb[:4])}
NBA: {json.dumps(nba[:4])}
NHL: {json.dumps(nhl[:4])}

Return this exact JSON:
{{
  "headline": {{
    "kicker": "SPORT NAME",
    "headline": "BIGGEST STORY OF THE DAY IN ALL CAPS",
    "deck": "Elaborating deck under 20 words",
    "byline": "By [First Last], Sports Writer",
    "body": "Three vivid paragraphs separated by \\n\\n."
  }},
  "secondary": [
    {{"kicker": "SPORT", "headline": "HEADLINE", "deck": "Deck", "byline": "By [Name]", "body": "Two paragraphs separated by \\n\\n."}},
    {{"kicker": "SPORT", "headline": "HEADLINE", "deck": "Deck", "byline": "By [Name]", "body": "Two paragraphs separated by \\n\\n."}},
    {{"kicker": "SPORT", "headline": "HEADLINE", "deck": "Deck", "byline": "By [Name]", "body": "Two paragraphs separated by \\n\\n."}}
  ],
  "column": {{
    "tag": "FROM THE PRESS BOX",
    "headline": "OPINION HEADLINE IN ALL CAPS",
    "byline": "By Pat McAllister",
    "body": "Two punchy opinionated paragraphs separated by \\n\\n."
  }}
}}""", max_tokens=2000)

def write_section(client, sport_label, scores, standings):
    return claude_call(client, f"""Write a feature story for the {sport_label} section of today's Sports Page.

Recent scores: {json.dumps(scores[:5])}
Standings: {json.dumps(standings[:2] if standings else [])}

Return:
{{
  "kicker": "{sport_label.upper()}",
  "headline": "ALL CAPS HEADLINE",
  "deck": "Deck elaborating headline",
  "byline": "By [First Last], {sport_label} Writer",
  "body": "Three paragraphs separated by \\n\\n."
}}""")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=== The Sports Page Daily Pipeline ===")
    now = datetime.now(timezone.utc)
    print(f"Running at {now.strftime('%Y-%m-%d %H:%M UTC')}\n")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Fetch all data
    print("Fetching from ESPN...")
    mlb_scores    = fetch_scores("baseball",    "mlb",   10)
    mlb_standings = fetch_standings("baseball", "mlb",    6)
    mlb_schedule  = fetch_schedule("baseball",  "mlb",   13)
    print(f"  MLB: {len(mlb_scores)} scores, {len(mlb_standings)} divs, {len(mlb_schedule)} sched")

    nba_scores    = fetch_scores("basketball",    "nba",  6)
    nba_standings = fetch_standings("basketball", "nba",  2)
    nba_schedule  = fetch_schedule("basketball",  "nba",  4)
    print(f"  NBA: {len(nba_scores)} scores, {len(nba_standings)} divs")

    nhl_scores    = fetch_scores("hockey",    "nhl",  6)
    nhl_standings = fetch_standings("hockey", "nhl",  2)
    nhl_schedule  = fetch_schedule("hockey",  "nhl",  4)
    print(f"  NHL: {len(nhl_scores)} scores, {len(nhl_standings)} divs")

    nfl_standings = fetch_standings("football", "nfl", 8)
    print(f"  NFL: {len(nfl_standings)} divs")

    # Write AI stories
    print("\nWriting stories with Claude...")
    front      = write_front(client, mlb_scores, nba_scores, nhl_scores)
    print("  Front page done")
    mlb_story  = write_section(client, "Baseball",   mlb_scores, mlb_standings)
    print("  MLB done")
    nba_story  = write_section(client, "Basketball", nba_scores, nba_standings)
    print("  NBA done")
    nhl_story  = write_section(client, "Hockey",     nhl_scores, nhl_standings)
    print("  NHL done")
    nfl_story  = write_section(client, "Football",   [],         nfl_standings)
    print("  NFL done")

    # Assemble output
    date_str = now.strftime("%A, %B %-d, %Y")
    output = {
        "date":    date_str,
        "edition": f"Vol. CXLVIII · No. {now.timetuple().tm_yday + 133}",
        "weather": "Check your local forecast",
        "front": {
            "headline":  front.get("headline", {}),
            "secondary": front.get("secondary", []),
            "column":    front.get("column", {}),
            "scores": {
                "mlb": mlb_scores[:8],
                "nba": nba_scores[:4],
                "nhl": nhl_scores[:4],
            }
        },
        "mlb": {"story": mlb_story, "schedule": mlb_schedule, "scores": mlb_scores, "standings": mlb_standings},
        "nba": {"story": nba_story, "schedule": nba_schedule, "scores": nba_scores, "standings": nba_standings},
        "nhl": {"story": nhl_story, "schedule": nhl_schedule, "scores": nhl_scores, "standings": nhl_standings},
        "nfl": {"story": nfl_story, "standings": nfl_standings},
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ docs/data.json written ({len(json.dumps(output))} bytes)")
    print("✓ Done.")

if __name__ == "__main__":
    main()
