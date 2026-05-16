#!/usr/bin/env python3
"""
The Sports Page — Daily Pipeline
MLB, NBA, NHL: real data from official free APIs (no API keys needed)
NFL: AI-generated offseason content + ESPN standings
Claude writes all stories and headlines
"""

import json, os, re, time
from datetime import datetime, timezone, date, timedelta
import requests
import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM = """You are the sports editor of The Sports Page, a classic American daily newspaper.
Write vivid newspaper journalism — inverted pyramid, specific, real player names.
No em-dashes. No first person.
Use ONLY the byline provided in the JSON template — do not invent other author names.
Respond ONLY with a valid JSON object. First char { last char }. No markdown, no backticks."""

def fetch_sport_news(sport_path, limit=5):
    """Fetch latest news headlines from ESPN for a sport."""
    data = api_get(
        f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/news",
        {"limit": limit}
    )
    if not data:
        return ""
    headlines = []
    for article in data.get("articles", [])[:limit]:
        headline = article.get("headline","")
        desc = article.get("description","") or article.get("summary","")
        if headline:
            entry = f"- {headline}"
            if desc:
                entry += f": {desc[:120]}"
            headlines.append(entry)
    return chr(10).join(headlines)


# ── STAFF BYLINES ──────────────────────────────────────────────────────────────
WRITERS = {
    "mlb":   "Jack Mercer",        # Baseball writer
    "nba":   "Marcus Webb",        # Basketball writer
    "nhl":   "Dan Callahan",       # Hockey writer
    "nfl":   "Ray Torino",         # Football writer
    "front": "Frank Dolan",        # Managing editor / front page
    "desk":  "The Sports Page Desk", # Generic desk byline
}


# ── SHARED HELPERS ────────────────────────────────────────────────────────────

def api_get(url, params=None, headers=None, timeout=20):
    """GET with retry and error handling."""
    h = {"User-Agent": "TheSportsPage/1.0 (personal project)"}
    if headers:
        h.update(headers)
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                print(f"    API error ({url.split('/')[-1]}): {e}")
                return None
            time.sleep(2)
    return None

def claude_call(client, prompt, max_tokens=3000):
    """Single Claude call, parse JSON response."""
    r = client.messages.create(
        model=MODEL, max_tokens=max_tokens, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )
    texts = [b for b in r.content if b.type == "text"]
    if not texts:
        raise ValueError(f"No text (stop={r.stop_reason})")
    raw = texts[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    s, e = raw.find('{'), raw.rfind('}') + 1
    if s == -1 or e == 0:
        raise ValueError(f"No JSON found: {raw[:200]}")
    try:
        return json.loads(raw[s:e])
    except json.JSONDecodeError as err:
        # Attempt recovery from truncated response
        trimmed = raw[s:s + err.pos].rstrip().rstrip(',')
        opens  = trimmed.count('{') - trimmed.count('}')
        arrays = trimmed.count('[') - trimmed.count(']')
        return json.loads(trimmed + ']' * max(0, arrays) + '}' * max(0, opens))

def season_ids():
    """Compute current season strings from today's date."""
    today = date.today()
    yr = today.year
    # NBA/NHL seasons span two calendar years; they start in Oct
    if today.month >= 9:
        nba = f"{yr}-{str(yr+1)[2:]}"
        nhl = f"{yr}{yr+1}"
    else:
        nba = f"{yr-1}-{str(yr)[2:]}"
        nhl = f"{yr-1}{yr}"
    return str(yr), nba, nhl   # mlb_season, nba_season, nhl_season_id

# ══════════════════════════════════════════════════════════════════════════════
# MLB  (statsapi.mlb.com — official, free, no key)
# ══════════════════════════════════════════════════════════════════════════════
MLB = "https://statsapi.mlb.com/api/v1"

def mlb_games_on(game_date):
    """Return list of completed game objects for a given date."""
    data = api_get(f"{MLB}/schedule", {
        "sportId": 1,
        "date": game_date,
    })
    games = []
    if not data:
        print(f"      mlb_games_on: API returned None for {game_date}")
        return games
    dates = data.get("dates", [])
    print(f"      mlb_games_on: {len(dates)} date(s) returned for {game_date}")
    for d in dates:
        raw_games = d.get("games", [])
        states = [g.get("status", {}).get("abstractGameState","?") for g in raw_games]
        print(f"      mlb_games_on: {len(raw_games)} games, states={states}")
        for g in raw_games:
            if g.get("status", {}).get("abstractGameState") == "Final":
                games.append(g)
    return games

def mlb_today(today_date):
    """Return today's scheduled games with probable pitchers."""
    data = api_get(f"{MLB}/schedule", {
        "sportId": 1,
        "date": today_date,
        "hydrate": "probablePitcher(note,stats),team",
    })
    if not data:
        return []
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            games.append(g)
    return games

def mlb_linescore(game_pk):
    return api_get(f"{MLB}/game/{game_pk}/linescore")

def mlb_boxscore(game_pk):
    return api_get(f"{MLB}/game/{game_pk}/boxscore")

def mlb_standings(season):
    return api_get(f"{MLB}/standings", {
        "leagueId": "103,104",
        "season": season,
        "standingsTypes": "regularSeason",
        "hydrate": "team,record,streak",
    })

def mlb_leaders_for(season, league_id, category, limit=8):
    data = api_get(f"{MLB}/stats/leaders", {
        "leaderCategories": category,
        "season": season,
        "leagueId": league_id,
        "sportId": 1,
        "limit": limit,
        "playerPool": "Qualified",
        "statGroup": "hitting" if category in ["battingAverage","homeRuns","rbi","hits","stolenBases","onBasePercentage","sluggingPercentage"] else "pitching",
    })
    if not data:
        return []
    for group in data.get("leagueLeaders", []):
        if group.get("leaderCategory") == category:
            return group.get("leaders", [])
    return []

# ── MLB formatters ────────────────────────────────────────────────────────────

def fmt_mlb_linescore(ls, away_name, home_name):
    if not ls:
        return None
    innings = ls.get("innings", [])
    away_scores, home_scores = [], []
    for inn in innings:
        away_scores.append(inn.get("away", {}).get("runs", 0))
        home_scores.append(inn.get("home", {}).get("runs", 0))
    # "x" for unplayed bottom of last inning
    if len(away_scores) > len(home_scores):
        home_scores.append("x")
    t = ls.get("teams", {})
    return {
        "away": {"name": away_name, "scores": away_scores,
                 "r": t.get("away", {}).get("runs", 0),
                 "h": t.get("away", {}).get("hits", 0),
                 "e": t.get("away", {}).get("errors", 0)},
        "home": {"name": home_name, "scores": home_scores,
                 "r": t.get("home", {}).get("runs", 0),
                 "h": t.get("home", {}).get("hits", 0),
                 "e": t.get("home", {}).get("errors", 0)},
    }

def fmt_mlb_pitching(box, side):
    team_data  = box.get("teams", {}).get(side, {})
    team_name  = team_data.get("team", {}).get("name", side)
    players    = team_data.get("players", {})
    # Use the ordered pitchers list — IDs in appearance order
    ordered_ids = team_data.get("pitchers", [])
    pitchers = []
    for pid in ordered_ids:
        p = players.get(f"ID{pid}", players.get(str(pid), {}))
        if not p:
            continue
        stats = p.get("stats", {}).get("pitching", {})
        if not stats or not stats.get("inningsPitched"):
            continue
        last = p.get("person", {}).get("fullName", "").split()[-1]
        ss   = p.get("seasonStats", {}).get("pitching", {})
        dec  = ""
        sw   = ss.get("wins",  stats.get("wins",  0))
        sl   = ss.get("losses",stats.get("losses",0))
        if stats.get("wins"):     dec = f"W, {sw}-{sl}"
        elif stats.get("losses"): dec = f"L, {sw}-{sl}"
        elif stats.get("saves"):  dec = f"SV, {ss.get('saves',stats.get('saves',0))}"
        elif stats.get("holds"):  dec = "H"
        era = ss.get("era", stats.get("era","—"))
        pitchers.append({
            "name": f"{last}{' ('+dec+')' if dec else ''}",
            "ip":  stats.get("inningsPitched","0.0"),
            "h":   stats.get("hits",0),
            "r":   stats.get("runs",0),
            "er":  stats.get("earnedRuns",0),
            "bb":  stats.get("baseOnBalls",0),
            "so":  stats.get("strikeOuts",0),
            "np":  stats.get("numberOfPitches",0),
            "era": era,
        })
    return {"team": team_name, "pitchers": pitchers}

def fmt_mlb_batting(box, side):
    team_data = box.get("teams", {}).get(side, {})
    team_name = team_data.get("team", {}).get("name", side)
    batters = []
    for pid, p in team_data.get("players", {}).items():
        order = p.get("battingOrder")
        if not order:
            continue
        game_s   = p.get("stats", {}).get("batting", {})
        season_s = p.get("seasonStats", {}).get("batting", {})
        if not game_s:
            continue
        pos = p.get("position", {}).get("abbreviation", "").lower()
        last = p.get("person", {}).get("fullName", "").split()[-1]
        prefix = "" if int(order) % 100 == 0 else "a-"
        avg = season_s.get("avg", game_s.get("avg", ".000"))
        batters.append({
            "_o":  int(order),
            "name": f"{prefix}{last} {pos}",
            "ab":  game_s.get("atBats", 0),
            "r":   game_s.get("runs", 0),
            "h":   game_s.get("hits", 0),
            "bi":  game_s.get("rbi", 0),
            "bb":  game_s.get("baseOnBalls", 0),
            "so":  game_s.get("strikeOuts", 0),
            "avg": avg,
            # Store for notes computation — hidden from display
            "_hr": game_s.get("homeRuns", 0),
            "_2b": game_s.get("doubles", 0),
            "_3b": game_s.get("triples", 0),
            "_sb": game_s.get("stolenBases", 0),
            "_lob": game_s.get("leftOnBase", 0),
            "_full": last,
            "_season_hr": season_s.get("homeRuns", 0),
        })
    batters.sort(key=lambda x: x["_o"])
    for b in batters:
        del b["_o"]
    ts = team_data.get("teamStats", {}).get("batting", {})
    totals = {"ab": ts.get("atBats",0), "r": ts.get("runs",0),
              "h": ts.get("hits",0),   "bi": ts.get("rbi",0),
              "bb": ts.get("baseOnBalls",0), "so": ts.get("strikeOuts",0)}
    return {"team": team_name, "players": batters, "totals": totals}

def compute_batting_notes(batting, existing_notes):
    """Compute HR/2B/3B/SB/LOB notes — all collected across both teams before output."""
    try:
        all_hrs  = []
        all_2b   = []
        all_3b   = []
        all_sb   = []
        lob_entries = []

        for team_data in batting:
            players   = team_data.get("players", [])
            team_name = team_data.get("team","").split()[-1]

            for p in players:
                if p.get("_hr", 0) > 0:
                    all_hrs.append(f"{p['_full']} ({p.get('_season_hr', 0)})")
                if p.get("_2b", 0) > 0:
                    all_2b.append(p["_full"])
                if p.get("_3b", 0) > 0:
                    all_3b.append(p["_full"])
                if p.get("_sb", 0) > 0:
                    all_sb.append(p["_full"])

            lob = sum(p.get("_lob", 0) for p in players)
            if lob > 0:
                lob_entries.append(f"{team_name} {lob}")

        extra = []
        if all_hrs:  extra.append(f"HR: {', '.join(all_hrs)}")
        if all_2b:   extra.append(f"2B: {', '.join(all_2b)}")
        if all_3b:   extra.append(f"3B: {', '.join(all_3b)}")
        if all_sb:   extra.append(f"SB: {', '.join(all_sb)}")
        if lob_entries: extra.append(f"LOB: {', '.join(lob_entries)}")

        if extra:
            sep = "  " if existing_notes else ""
            return existing_notes + sep + "  ".join(extra)
    except Exception as e:
        print(f"      Notes compute error: {e}")
    return existing_notes

def fmt_mlb_notes_from_content(content, existing_notes):
    """Unused — kept for compatibility."""
    return existing_notes

def fmt_mlb_notes(box):
    """Pull game notes from multiple fields in the MLB boxscore API response."""
    notes = []
    seen = set()

    # Field 1: top-level info array (WP, LP, SV, HBP, T, Att, Umpires)
    info_want  = {"WP","LP","SV","HBP","HBP","T","Att"}
    for item in box.get("info", []):
        lbl = item.get("label","").strip()
        val = item.get("value","").strip()
        if lbl in info_want and val and lbl not in seen:
            notes.append(f"{lbl}: {val}")
            seen.add(lbl)

    # Field 2: teams.[side].note — contains HR, 2B, 3B, SB, LOB, GIDP etc.
    # Can be a string or a list of dicts depending on API version
    for side in ["away","home"]:
        team_note = box.get("teams",{}).get(side,{}).get("note","")
        if isinstance(team_note, list):
            # List of dicts with label/value keys
            for entry in team_note:
                lbl = entry.get("label","").strip()
                val = entry.get("value","").strip()
                if lbl and val:
                    item = f"{lbl}: {val}"
                    if item not in seen:
                        notes.append(item)
                        seen.add(item)
        elif isinstance(team_note, str) and team_note:
            for item in team_note.split(". "):
                item = item.strip().rstrip(".")
                if item and ":" in item and item not in seen:
                    notes.append(item)
                    seen.add(item)

    # Field 3: top-level notes array (some games use this)
    for note in box.get("notes", []):
        val = note.get("label","") or note.get("value","")
        if val and val not in seen:
            notes.append(val)
            seen.add(val)

    # Debug: if no notes found, log available keys
    if not notes:
        info_labels = [i.get("label","") for i in box.get("info",[])]
        print(f"      Notes debug: info labels={info_labels[:8]}")
        for side in ["away","home"]:
            tn = box.get("teams",{}).get(side,{}).get("note","")
            if tn:
                print(f"      Notes debug: {side}.note type={type(tn).__name__} val={str(tn)[:100]}")

    return "  ".join(notes) if notes else ""

def fmt_mlb_schedule(games, mlb_season='2026'):
    sched = []
    for g in games:
        away = g.get("teams",{}).get("away",{})
        home = g.get("teams",{}).get("home",{})
        gd = g.get("gameDate","")
        time_str = "TBD"
        try:
            dt = datetime.strptime(gd, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            et = dt + timedelta(hours=-4)  # EDT
            time_str = et.strftime("%-I:%M %p ET")
        except Exception:
            pass
        ap = away.get("probablePitcher",{})
        hp = home.get("probablePitcher",{})
        def pp(p):
            if not p: return ""
            parts = p.get("fullName","").split()
            last = parts[-1] if parts else ""
            pid  = p.get("id","")
            era  = ""; rec = ""
            # Try stats embedded in probable pitcher object
            for s in p.get("stats",[]):
                sp = s.get("stats",{})
                if sp.get("era"): era = str(sp["era"])
                w = sp.get("wins",""); l = sp.get("losses","")
                if w != "" and l != "": rec = f"{w}-{l}"
            # Fallback: fetch season stats directly if not embedded
            if (not era or not rec) and pid:
                time.sleep(0.2)  # prevent rate limiting on rapid pitcher lookups
                sdata = api_get(f"{MLB}/people/{pid}/stats",
                                {"stats":"season","season":mlb_season,"group":"pitching"})
                if sdata:
                    for sg in sdata.get("stats",[]):
                        for split in sg.get("splits",[]):
                            sp = split.get("stat",{})
                            if sp.get("era") and not era: era = str(sp["era"])
                            w = sp.get("wins",""); l = sp.get("losses","")
                            if w != "" and l != "" and not rec: rec = f"{w}-{l}"
            if rec and era: return f"{last} ({rec}, {era})"
            elif rec: return f"{last} ({rec})"
            elif era: return f"{last} ({era})"
            return last
        entry = {
            "time": time_str,
            "away": away.get("team",{}).get("name",""),
            "home": home.get("team",{}).get("name",""),
        }
        if ap: entry["asp"] = pp(ap)
        if hp: entry["hsp"] = pp(hp)
        sched.append(entry)
    return sched

def fmt_mlb_standings(raw):
    """Convert MLB Stats API standings response to site format.
    Uses division ID as primary key — immune to name changes."""
    # Division ID → short label
    DIV_ID_MAP = {
        200: "AL West",  201: "AL East",  202: "AL Central",
        203: "NL West",  204: "NL East",  205: "NL Central",
    }
    DIV_ORDER = ["AL East","AL Central","AL West","NL East","NL Central","NL West"]

    if not raw:
        print("    MLB Standings: API returned nothing")
        return []

    records = raw.get("records", [])
    print(f"    MLB Standings: {len(records)} records from API")

    if not records:
        # Print top-level keys so we can debug
        print(f"    MLB Standings raw keys: {list(raw.keys())}")
        return []

    divs = {}
    for rec in records:
        # --- Determine division label ---
        div_obj  = rec.get("division", {})
        div_id   = div_obj.get("id")
        div_name = div_obj.get("name", "")
        print(f"      div id={div_id} name='{div_name}'")

        if div_id and div_id in DIV_ID_MAP:
            label = DIV_ID_MAP[div_id]
        else:
            # Fallback: normalise name
            label = (div_name
                     .replace("American League ","AL ")
                     .replace("National League ","NL ")
                     .replace(" Division","")
                     .strip())
            if not label:
                print(f"      Skipping — could not determine division")
                continue

        # --- Build team rows ---
        teams = []
        for i, tr in enumerate(rec.get("teamRecords", [])):
            split_list = tr.get("records", {}).get("splitRecords", [])
            splits = {}
            for s in split_list:
                key = s.get("type") or s.get("splitType","")
                splits[key] = s
            ho = splits.get("home", {})
            aw = splits.get("away", {})
            lt = splits.get("lastTen", splits.get("last10", {}))

            gb_raw = str(tr.get("gamesBack", tr.get("gamesBehind","—")))
            gb = "-" if gb_raw in ["0.0","0","0.00","-.--","—",""] else gb_raw

            streak_obj = tr.get("streak", {})
            strk = streak_obj.get("streakCode","")
            if not strk and streak_obj:
                stype = "W" if streak_obj.get("streakType","")=="wins" else "L"
                snum  = str(streak_obj.get("streakNumber",""))
                strk  = stype + snum

            pct = tr.get("winningPercentage", tr.get("pct",".000"))
            if pct and not str(pct).startswith("."):
                try: pct = f"{float(pct):.3f}"
                except: pass

            teams.append({
                "rank": i+1,
                "name": tr.get("team",{}).get("name",""),
                "w":   tr.get("wins",0),
                "l":   tr.get("losses",0),
                "pct": str(pct),
                "gb":  gb,
                "l10": f"{lt.get('wins',0)}-{lt.get('losses',0)}",
                "strk": strk,
                "home": f"{ho.get('wins',0)}-{ho.get('losses',0)}",
                "away": f"{aw.get('wins',0)}-{aw.get('losses',0)}",
            })

        if teams:
            divs[label] = {"label": label, "teams": teams}
            print(f"        → {label}: {len(teams)} teams OK")
        else:
            print(f"        → {label}: no teamRecords found")

    result = [divs[d] for d in DIV_ORDER if d in divs]
    if not result and divs:
        print(f"    MLB Standings fallback — using {list(divs.keys())}")
        result = list(divs.values())

    print(f"    MLB Standings final: {len(result)} divisions")
    return result

def fmt_mlb_leaders_side(season, league_id, label):
    cat_map = [
        ("battingAverage", "Batting Average", ["Player","Team","Avg"]),
        ("homeRuns",        "Home Runs",       ["Player","Team","HR"]),
        ("rbi",             "RBI",             ["Player","Team","RBI"]),
        ("hits",            "Hits",            ["Player","Team","H"]),
        ("stolenBases",     "Stolen Bases",    ["Player","Team","SB"]),
        ("earnedRunAverage","ERA",             ["Pitcher","Team","ERA"]),
        ("strikeouts",      "Strikeouts",      ["Pitcher","Team","K"]),
        ("saves",           "Saves",           ["Pitcher","Team","SV"]),
    ]
    cats = []
    for api_cat, display, cols in cat_map:
        leaders = mlb_leaders_for(season, league_id, api_cat, limit=8)
        rows = []
        for ldr in leaders:
            name = ldr.get("person",{}).get("fullName","")
            team = ldr.get("team",{}).get("name","").split()[-1]
            val  = ldr.get("value","")
            rows.append([name, team, val])
        if rows:
            cats.append({"cat": display, "cols": cols, "rows": rows})
        time.sleep(0.3)  # be gentle with the API
    return {"label": label, "cats": cats}

# ── MLB section builder ───────────────────────────────────────────────────────

def build_mlb(client, today_str, yesterday_str, mlb_season):
    print("  MLB: fetching data...")
    yesterday_games = mlb_games_on(yesterday_str)
    # If no Final games yet, keep empty — scheduled 7AM UTC run always catches them
    if not yesterday_games:
        print(f"    No Final games for {yesterday_str} — games may still be in progress")
    today_games_raw = mlb_today(today_str)
    standings_raw   = mlb_standings(mlb_season)
    print(f"    {len(yesterday_games)} games yesterday, {len(today_games_raw)} today")

    # Schedule

    # All box scores — full batting for first 3, linescore-only for rest
    box_scores = []
    for i, game in enumerate(yesterday_games[:15]):
        pk        = game.get("gamePk")
        away_name = game.get("teams",{}).get("away",{}).get("team",{}).get("name","")
        home_name = game.get("teams",{}).get("home",{}).get("team",{}).get("name","")
        time.sleep(0.3)
        ls_raw    = mlb_linescore(pk)
        ls        = fmt_mlb_linescore(ls_raw, away_name, home_name)
        if not ls:
            print(f"      SKIP game {pk} ({away_name} @ {home_name}): linescore None={ls_raw is None}")
            continue
        ar, hr = ls["away"]["r"], ls["home"]["r"]
        winner = away_name if ar > hr else home_name
        loser  = home_name if ar > hr else away_name
        title  = f"{winner} {max(ar,hr)}, {loser} {min(ar,hr)}"
        print(f"      Game {i+1}: {title}")

        batting, pitching, notes = [], [], ""
        time.sleep(0.5)
        box_raw = mlb_boxscore(pk)
        if box_raw:
            batting  = [fmt_mlb_batting(box_raw,"away"), fmt_mlb_batting(box_raw,"home")]
            pitching = [fmt_mlb_pitching(box_raw,"away"), fmt_mlb_pitching(box_raw,"home")]
            notes    = fmt_mlb_notes(box_raw)
            notes    = compute_batting_notes(batting, notes)
            n_batters = sum(len(t.get("players",[])) for t in batting)
            print(f"        Batters: {n_batters} | Notes: {bool(notes)}")
        else:
            print(f"        Box score: FAILED for {pk}")

        box_scores.append({"title": title, "linescore": ls,
                            "batting": batting,
                            "pitching": pitching,
                            "notes": notes})
        time.sleep(0.2)


    # Schedule (built after box scores to avoid rate limiting box score API calls)
    schedule = fmt_mlb_schedule(today_games_raw, mlb_season)

    # Standings
    standings = fmt_mlb_standings(standings_raw)

    # Leaders (AL=103, NL=104)
    print("    Fetching MLB leaders...")
    leaders = {
        "left":  fmt_mlb_leaders_side(mlb_season, 103, "American League"),
        "right": fmt_mlb_leaders_side(mlb_season, 104, "National League"),
    }

    # Claude writes story
    print("    Writing MLB story...")
    scores_txt = "; ".join(b["title"] for b in box_scores[:6])
    mlb_news = fetch_sport_news("baseball/mlb")
    mlb_news_ctx = (chr(10) + "Major MLB news today (use only if genuinely significant):" + chr(10) + mlb_news) if mlb_news else ""
    if scores_txt:
        mlb_story_prompt = f"""Write the lead baseball story for The Sports Page dated {today_str}.
Yesterday\'s MLB results ({yesterday_str}): {scores_txt}{mlb_news_ctx}
Only lead with breaking news if it is genuinely major — a star player death, season-ending injury to a franchise player, blockbuster trade, or league suspension. Routine injuries, minor trades, and lineup moves should be ignored. Otherwise always lead with the best game story.
Return JSON: {{"kicker":"BASEBALL","headline":"HEADLINE ALL CAPS","deck":"Under 20 words","byline":"By Jack Mercer","body":"Three vivid paragraphs separated by \\n\\n."}}"""
    else:
        mlb_story_prompt = f"""Write a baseball story for The Sports Page dated {today_str}.
No games yesterday.{mlb_news_ctx}
If there is breaking news lead with that, otherwise write a standings or preview piece.
Return JSON: {{"kicker":"BASEBALL","headline":"HEADLINE ALL CAPS","deck":"Under 20 words","byline":"By Jack Mercer","body":"Three vivid paragraphs separated by \\n\\n."}}"""
    story = claude_call(client, mlb_story_prompt)

    return {"story": story, "schedule": schedule,
            "boxScores": box_scores, "standings": standings, "leaders": leaders}

# ══════════════════════════════════════════════════════════════════════════════
# NBA  (stats.nba.com via nba_api — official, free, no key)
# ══════════════════════════════════════════════════════════════════════════════


def espn_nba_scores(game_date):
    """ESPN fallback for NBA scores when nba_api times out."""
    data = api_get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                   {"dates": game_date.replace("-","")})
    games = []
    if not data: return games
    for event in data.get("events",[]):
        comps = event.get("competitions",[{}])[0]
        teams = comps.get("competitors",[])
        if len(teams) < 2: continue
        home = next((t for t in teams if t.get("homeAway")=="home"), teams[0])
        away = next((t for t in teams if t.get("homeAway")=="away"), teams[1])
        status = comps.get("status",{}).get("type",{}).get("shortDetail","Final")
        games.append({
            "game_id": event.get("id",""),
            "away": away.get("team",{}).get("displayName",""),
            "home": home.get("team",{}).get("displayName",""),
            "away_score": int(away.get("score",0) or 0),
            "home_score": int(home.get("score",0) or 0),
            "status": status,
        })
    return games

def espn_nba_schedule(game_date):
    """ESPN fallback for today's NBA schedule."""
    data = api_get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                   {"dates": game_date.replace("-","")})
    games = []
    if not data: return games
    for event in data.get("events",[]):
        comps = event.get("competitions",[{}])[0]
        teams = comps.get("competitors",[])
        if len(teams) < 2: continue
        home = next((t for t in teams if t.get("homeAway")=="home"), teams[0])
        away = next((t for t in teams if t.get("homeAway")=="away"), teams[1])
        status = comps.get("status",{}).get("type",{}).get("shortDetail","TBD")
        note = event.get("season",{}).get("slug","")
        entry = {
            "time": status,
            "away": away.get("team",{}).get("displayName",""),
            "home": home.get("team",{}).get("displayName",""),
        }
        if note: entry["note"] = note
        games.append(entry)
    return games

def build_nba(client, today_str, yesterday_str, nba_season):
    print("  NBA: fetching data...")
    try:
        from nba_api.stats.endpoints import (
            scoreboardv3, boxscoretraditionalv3,
            leaguestandingsv3, leagueleaders
        )
    except ImportError:
        print("    nba_api not installed, using fallback")
        return nba_fallback(client)

    NBA_HEADERS = {
        "Host": "stats.nba.com",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://stats.nba.com",
    }

    def nba_get(endpoint_cls, **kwargs):
        for attempt in range(3):
            try:
                time.sleep(1.5)
                obj = endpoint_cls(timeout=60, **kwargs)
                obj._endpoint_headers = NBA_HEADERS
                return obj
            except Exception as e:
                if attempt == 2:
                    print(f"    NBA API error: {e}")
                    return None
                time.sleep(3)
        return None

    # Yesterday's scores
    board = nba_get(scoreboardv3.ScoreboardV3, game_date=yesterday_str, league_id="00")
    yesterday_games = []
    if not board:
        print('    nba_api failed, using ESPN fallback for NBA scores')
        yesterday_games = espn_nba_scores(yesterday_str)
    if board:
        try:
            # Try multiple V3 attribute names
            df = None
            for attr in ['score_board','games','game_header','scoreboard']:
                if hasattr(board, attr):
                    try:
                        df = getattr(board, attr).get_data_frame()
                        break
                    except Exception:
                        continue
            if df is None:
                raise ValueError("No valid ScoreboardV3 attribute found")
            # Handle both V2-style and V3-style column names
            for _, g in df.iterrows():
                game_id = str(g.get("gameId", g.get("GAME_ID","")))
                away = g.get("awayTeamCity","") + " " + g.get("awayTeamName","")
                if not away.strip():
                    away = g.get("VISITOR_TEAM_CITY","") + " " + g.get("VISITOR_TEAM_NICKNAME","")
                home = g.get("homeTeamCity","") + " " + g.get("homeTeamName","")
                if not home.strip():
                    home = g.get("HOME_TEAM_CITY","") + " " + g.get("HOME_TEAM_NICKNAME","")
                away_score = int(g.get("awayTeamScore", g.get("PTS_AWAY",0)) or 0)
                home_score = int(g.get("homeTeamScore", g.get("PTS_HOME",0)) or 0)
                status = g.get("gameStatusText", g.get("GAME_STATUS_TEXT","Final"))
                yesterday_games.append({
                    "game_id": game_id,
                    "away": away.strip(),
                    "home": home.strip(),
                    "away_score": away_score,
                    "home_score": home_score,
                    "status": status,
                })
        except Exception as e:
            print(f"    NBA scoreboard parse error: {e}")
            yesterday_games = espn_nba_scores(yesterday_str)

    # Today's schedule
    today_board = nba_get(scoreboardv3.ScoreboardV3, game_date=today_str, league_id="00")
    schedule = []
    if not today_board:
        schedule = espn_nba_schedule(today_str)
    if today_board:
        try:
            df = None
            for attr in ['score_board','games','game_header','scoreboard']:
                if hasattr(today_board, attr):
                    try:
                        df = getattr(today_board, attr).get_data_frame()
                        break
                    except Exception:
                        continue
            if df is None:
                raise ValueError("No valid ScoreboardV3 attribute")
            for _, g in df.iterrows():
                away = g.get("awayTeamCity","") + " " + g.get("awayTeamName","")
                home = g.get("homeTeamCity","") + " " + g.get("homeTeamName","")
                time_et = g.get("gameStatusText", g.get("GAME_STATUS_TEXT","TBD"))
                entry = {"time": time_et, "away": away.strip(), "home": home.strip()}
                series = g.get("seriesText","") or g.get("seriesStatusText","")
                if series:
                    entry["note"] = str(series)
                schedule.append(entry)
        except Exception as e:
            print(f"    NBA today schedule parse error: {e}")
            schedule = espn_nba_schedule(today_str)

    # Box scores
    box_scores = []
    for i, g in enumerate(yesterday_games):
        gid = g["game_id"]
        ar, hr = g["away_score"], g["home_score"]
        winner = g["away"] if ar > hr else g["home"]
        loser  = g["home"] if ar > hr else g["away"]
        title  = f"{winner} {max(ar,hr)}, {loser} {min(ar,hr)}"
        status = g["status"]

        # Linescore from scoreboard
        ls = {
            "away": {"name": g["away"], "scores": [], "r": ar},
            "home": {"name": g["home"], "scores": [], "r": hr},
        }

        batting = []
        box = nba_get(boxscoretraditionalv3.BoxScoreTraditionalV3, game_id=gid)
        if True:  # Full box for all games
            if box:
                try:
                    pl = box.player_stats.get_data_frame()
                    tm = box.team_stats.get_data_frame()

                    # Quarter scores from team stats
                    # Determine away/home by matching team abbrev from scores already built
                    away_abbr = g.get("away","").split()[-1] if g.get("away","").split() else ""
                    for _, row in tm.iterrows():
                        team_abbr = str(row.get("TEAM_ABBREVIATION",""))
                        side_key = "away" if team_abbr and away_abbr and team_abbr in g.get("away","") else "home"
                        ls[side_key]["scores"] = [
                            int(row.get("PTS_QTR1",0) or 0),
                            int(row.get("PTS_QTR2",0) or 0),
                            int(row.get("PTS_QTR3",0) or 0),
                            int(row.get("PTS_QTR4",0) or 0),
                        ]
                        ot = int(row.get("PTS_OT1",0) or 0)
                        if ot: ls[side_key]["scores"].append(ot)

                    for team_id in pl["TEAM_ID"].unique():
                        team_rows = pl[pl["TEAM_ID"]==team_id].copy()
                        team_name = team_rows.iloc[0].get("TEAM_CITY","") + " " + \
                                    team_rows.iloc[0].get("TEAM_NICKNAME","")
                        players = []
                        totals_r = tm[tm["TEAM_ID"]==team_id]
                        for _, p in team_rows.iterrows():
                            min_val = str(p.get("MIN","0:00")).split(":")[0]
                            players.append({
                                "name": p.get("PLAYER_NAME","").split()[-1] + " " +
                                        str(p.get("START_POSITION","")).lower(),
                                "min": min_val,
                                "fg":  f"{p.get('FGM',0)}-{p.get('FGA',0)}",
                                "tp":  f"{p.get('FG3M',0)}-{p.get('FG3A',0)}",
                                "ft":  f"{p.get('FTM',0)}-{p.get('FTA',0)}",
                                "reb": str(int(p.get("REB",0) or 0)),
                                "ast": str(int(p.get("AST",0) or 0)),
                                "pts": str(int(p.get("PTS",0) or 0)),
                            })
                        totals = {}
                        if not totals_r.empty:
                            t = totals_r.iloc[0]
                            totals = {
                                "fg": f"{t.get('FGM',0)}-{t.get('FGA',0)}",
                                "tp": f"{t.get('FG3M',0)}-{t.get('FG3A',0)}",
                                "ft": f"{t.get('FTM',0)}-{t.get('FTA',0)}",
                                "reb": str(int(t.get("REB",0) or 0)),
                                "ast": str(int(t.get("AST",0) or 0)),
                                "pts": str(int(t.get("PTS",0) or 0)),
                            }
                        batting.append({"team": team_name, "players": players, "totals": totals})
                except Exception as e:
                    print(f"    NBA box parse error: {e}")

        box_scores.append({
            "title": title, "linescore": ls,
            "batting": batting, "notes": status
        })

    # Standings
    standings = []
    std = nba_get(leaguestandingsv3.LeagueStandingsV3,
                  season=nba_season, season_type="Regular Season")
    if std:
        try:
            df = std.standings.get_data_frame()
            east = {"label": "Eastern Conference — Playoffs", "teams": []}
            west = {"label": "Western Conference — Playoffs", "teams": []}
            for _, row in df.iterrows():
                conf = row.get("Conference","")
                team = {
                    "rank": int(row.get("PlayoffRank", row.get("ConferenceRank",0)) or 0),
                    "name": row.get("TeamCity","") + " " + row.get("TeamName",""),
                    "w":    int(row.get("WINS",0) or 0),
                    "l":    int(row.get("LOSSES",0) or 0),
                    "pct":  f".{str(round(float(row.get('WinPCT',0))*1000)).zfill(3)}",
                    "gb":   str(row.get("ConferenceGamesBack","—")),
                    "note": str(row.get("ClinchedIndicator","")).strip(),
                }
                if conf == "East":
                    east["teams"].append(team)
                else:
                    west["teams"].append(team)
            east["teams"].sort(key=lambda x: x["rank"])
            west["teams"].sort(key=lambda x: x["rank"])
            standings = [east, west]
        except Exception as e:
            print(f"    NBA standings parse error: {e}")

    # Leaders
    leaders = {"left": nba_leaders_side(client, nba_season, "East", "Eastern Conference"),
               "right": nba_leaders_side(client, nba_season, "West", "Western Conference")}

    # Story
    print("    Writing NBA story...")
    scores_txt = "; ".join(
        f"{g['away'].split()[-1]}s {g['away_score']}, {g['home'].split()[-1]}s {g['home_score']}"
        for g in yesterday_games[:4]
    )
    nba_news = fetch_sport_news("basketball/nba")
    nba_news_ctx = f"\nBreaking NBA news today:\n{nba_news}" if nba_news else ""
    if scores_txt:
        nba_prompt = f"Write the lead basketball story for The Sports Page dated {today_str}. Yesterday\'s NBA results: {scores_txt}.{nba_news_ctx} Only reference breaking news if it is genuinely major (death, season-ending injury to a star, blockbuster trade). Routine news should be ignored — always prefer a compelling game story. Return JSON: {{\"kicker\":\"NBA PLAYOFFS\",\"headline\":\"HEADLINE ALL CAPS\",\"deck\":\"Under 20 words\",\"byline\":\"By Marcus Webb\",\"body\":\"Three vivid paragraphs separated by \\\\n\\\\n.\"}}"
    else:
        nba_prompt = f"Write an NBA story for The Sports Page dated {today_str}. No games yesterday.{nba_news_ctx} Lead with breaking news if available, otherwise write a playoff preview. Return JSON: {{\"kicker\":\"NBA PLAYOFFS\",\"headline\":\"HEADLINE ALL CAPS\",\"deck\":\"Under 20 words\",\"byline\":\"By Marcus Webb\",\"body\":\"Three vivid paragraphs separated by \\\\n\\\\n.\"}}"
    story = claude_call(client, nba_prompt)

    return {"story": story, "schedule": schedule,
            "boxScores": box_scores, "standings": standings, "leaders": leaders}

def nba_leaders_side(client, season, conf_filter, label):
    """Get NBA leaders for one conference via nba_api, filtered by conference."""
    try:
        from nba_api.stats.endpoints import leagueleaders
        cats_config = [
            ("PTS", "Scoring (PPG)",  ["Player","Team","G","Pts","PPG"]),
            ("REB", "Rebounds (RPG)", ["Player","Team","G","Reb","RPG"]),
            ("AST", "Assists (APG)",  ["Player","Team","G","Ast","APG"]),
        ]
        # ESPN conference IDs for filtering team abbreviations
        # East teams vs West teams — use conference param if available
        east_teams = {"ATL","BOS","BKN","CHA","CHI","CLE","DET","IND",
                      "MIA","MIL","NYK","ORL","PHI","TOR","WAS"}
        west_teams = {"DAL","DEN","GSW","HOU","LAC","LAL","MEM","MIN",
                      "NOP","OKC","PHX","POR","SAC","SAS","UTA"}

        cats = []
        for stat, display, cols in cats_config:
            time.sleep(0.6)
            obj = leagueleaders.LeagueLeaders(
                season=season,
                stat_category_abbreviation=stat,
                per_mode48="PerGame",
                season_type_all_star="Playoffs",
            )
            df = obj.league_leaders.get_data_frame()
            # Filter by conference
            conf_teams = east_teams if conf_filter == "East" else west_teams
            filtered = df[df["TEAM"].isin(conf_teams)] if "TEAM" in df.columns else df
            rows = []
            for _, row in filtered.head(8).iterrows():
                rows.append([
                    row.get("PLAYER",""),
                    row.get("TEAM",""),
                    str(int(row.get("GP",0) or 0)),
                    str(round(float(row.get(stat,0) or 0)*float(row.get("GP",1) or 1),1)),
                    str(round(float(row.get(stat,0) or 0),1)),
                ])
            if rows:
                cats.append({"cat": display, "cols": cols, "rows": rows})
        return {"label": label, "cats": cats}
    except Exception as e:
        print(f"    NBA leaders error ({label}): {e}")
        return {"label": label, "cats": []}

def nba_fallback(client):
    """Fallback NBA section if nba_api unavailable."""
    story = claude_call(client, """Write a brief NBA playoffs story for today's Sports Page.
Return JSON: {"kicker":"NBA PLAYOFFS","headline":"HEADLINE","deck":"Deck","byline":"By Frank Dolan","body":"Two paragraphs separated by \\n\\n."}""")
    return {"story": story, "schedule": [], "boxScores": [],
            "standings": [], "leaders": {"left": {"label":"Eastern Conference","cats":[]}, "right": {"label":"Western Conference","cats":[]}}}

# ══════════════════════════════════════════════════════════════════════════════
# NHL  (api-web.nhle.com — official, free, no key)
# ══════════════════════════════════════════════════════════════════════════════
NHL = "https://api-web.nhle.com/v1"

def build_nhl(client, today_str, yesterday_str, nhl_season_id):
    print("  NHL: fetching data...")

    # Yesterday's scores
    sched_raw = api_get(f"{NHL}/schedule/{yesterday_str}")
    yesterday_games = []
    if sched_raw:
        for week in sched_raw.get("gameWeek", []):
            for g in week.get("games", []):
                state = g.get("gameState","")
                if state in ["OFF","FINAL"]:
                    yesterday_games.append(g)

    # Today's schedule
    today_raw = api_get(f"{NHL}/schedule/{today_str}")
    schedule = []
    if today_raw:
        for week in today_raw.get("gameWeek", []):
            for g in week.get("games", []):
                away = g.get("awayTeam",{})
                home = g.get("homeTeam",{})
                t = g.get("startTimeUTC","")
                time_str = "TBD"
                try:
                    dt = datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    et = dt + timedelta(hours=-4)
                    time_str = et.strftime("%-I:%M %p ET")
                except Exception:
                    pass
                series = g.get("seriesStatus",{})
                if isinstance(series, dict) and series:
                    top  = series.get("topSeedTeamAbbrev","")
                    bot  = series.get("bottomSeedTeamAbbrev","")
                    tw   = series.get("topSeedWins",0)
                    bw   = series.get("bottomSeedWins",0)
                    title= series.get("seriesTitle","")
                    note = f"{title}: {top} leads {tw}-{bw}" if tw > bw else                            f"{title}: {bot} leads {bw}-{tw}" if bw > tw else                            f"{title}: Tied {tw}-{bw}"
                else:
                    note = str(series) if series else ""
                away_name = away.get("placeName",{}).get("default","") or                              away.get("name",{}).get("default","") or                              away.get("fullName","") or                              away.get("teamName",{}).get("default","")
                home_name = home.get("placeName",{}).get("default","") or                              home.get("name",{}).get("default","") or                              home.get("fullName","") or                              home.get("teamName",{}).get("default","")
                # Skip games with no team names resolved
                if not away_name or not home_name:
                    continue
                entry = {
                    "time": time_str,
                    "away": away_name,
                    "home": home_name,
                }
                if note:
                    entry["note"] = note
                schedule.append(entry)

    # Box scores
    box_scores = []
    for i, g in enumerate(yesterday_games):
        gid  = g.get("id")
        away = g.get("awayTeam",{})
        home = g.get("homeTeam",{})
        away_name = away.get("name",{}).get("default","") or away.get("fullName","")
        home_name = home.get("name",{}).get("default","") or home.get("fullName","")
        ar = int(away.get("score",0) or 0)
        hr = int(home.get("score",0) or 0)
        winner = away_name if ar > hr else home_name
        loser  = home_name if ar > hr else away_name
        period_desc = g.get("gameOutcome",{}).get("lastPeriodType","")
        suffix = f" ({period_desc})" if period_desc and period_desc != "REG" else ""
        title = f"{winner} {max(ar,hr)}, {loser} {min(ar,hr)}{suffix}"

        # Build linescore from period line scores if available
        ls = {"away": {"name": away_name, "scores": [], "r": ar},
              "home": {"name": home_name, "scores": [], "r": hr}}

        batting = []
        box_raw = api_get(f"{NHL}/gamecenter/{gid}/boxscore")
        if box_raw:
            # Period scores
            for period in box_raw.get("linescore", {}).get("periods", []):
                ls["away"]["scores"].append(int(period.get("away",{}).get("goals",0) or 0))
                ls["home"]["scores"].append(int(period.get("home",{}).get("goals",0) or 0))

            # Player stats
            for side, key in [("away","awayTeam"), ("home","homeTeam")]:
                team_data = box_raw.get(key, {})
                team_name_bs = team_data.get("name",{}).get("default","") or \
                               (away_name if side=="away" else home_name)
                players = []
                for p in team_data.get("forwards",[]) + team_data.get("defensemen",[]):
                    name = p.get("name",{}).get("default","").split()[-1]
                    pos  = p.get("position","").lower()
                    players.append({
                        "name": f"{name} {pos}",
                        "g":   str(p.get("goals",0)),
                        "a":   str(p.get("assists",0)),
                        "pts": str(p.get("points",0)),
                        "pm":  f"{'+' if (p.get('plusMinus',0) or 0) >= 0 else ''}{p.get('plusMinus',0)}",
                        "pim": str(p.get("pim",0)),
                        "sog": str(p.get("sog",p.get("shots",0))),
                    })
                # Goalies
                totals_sog = sum(int(p.get("sog",p.get("shots",0)) or 0) for p in players)
                totals_pim = sum(int(p.get("pim",0) or 0) for p in players)
                for g_data in team_data.get("goalies",[]):
                    name = g_data.get("name",{}).get("default","").split()[-1]
                    dec  = g_data.get("decision","")
                    players.append({
                        "name": f"{name} g{' ('+dec+')' if dec else ''}",
                        "g":"—","a":"—","pts":"—","pm":"—",
                        "pim": str(g_data.get("pim",0)),
                        "sog": str(g_data.get("shotsAgainst",0)),
                    })
                batting.append({
                    "team": team_name_bs,
                    "players": players,
                    "totals": {"sog": str(totals_sog), "pim": str(totals_pim)},
                })

            # Notes from decision goalies
            notes_parts = []
            for gk in box_raw.get("awayTeam",{}).get("goalies",[]) + \
                       box_raw.get("homeTeam",{}).get("goalies",[]):
                dec = gk.get("decision","")
                name = gk.get("name",{}).get("default","").split()[-1]
                sa = gk.get("shotsAgainst",0)
                sv = gk.get("saves",0)
                if dec:
                    notes_parts.append(f"{name} ({dec}) {sv}/{sa} saves")
            notes = ". ".join(notes_parts) + "." if notes_parts else ""
        else:
            notes = ""

        box_scores.append({"title": title, "linescore": ls,
                            "batting": batting,
                            "notes": notes})

    # Standings
    # During playoffs NHL standings endpoint may return 0 teams for current date
    # Try today first, then fall back to April 18 (end of regular season)
    std_raw = api_get(f"{NHL}/standings/{today_str}")
    if not std_raw or not std_raw.get("standings"):
        print("    NHL standings empty for today, trying end-of-season date...")
        std_raw = api_get(f"{NHL}/standings/2026-04-18")
    if not std_raw or not std_raw.get("standings"):
        std_raw = api_get(f"{NHL}/standings/now")
    standings = fmt_nhl_standings(std_raw)

    # Leaders
    leaders = {
        "left":  fmt_nhl_leaders_side("East", "Eastern Conference", nhl_season_id),
        "right": fmt_nhl_leaders_side("West", "Western Conference", nhl_season_id),
    }

    # Story
    print("    Writing NHL story...")
    scores_txt = "; ".join(b["title"] for b in box_scores[:4])
    nhl_news = fetch_sport_news("hockey/nhl")
    nhl_news_ctx = f"\nBreaking NHL news today:\n{nhl_news}" if nhl_news else ""
    if scores_txt:
        nhl_prompt = f"Write the lead hockey story for The Sports Page dated {today_str}. Yesterday\'s NHL results: {scores_txt}.{nhl_news_ctx} Only reference breaking news if it is genuinely major (death, season-ending injury to a star, blockbuster trade). Routine news should be ignored — always prefer a compelling game story. Return JSON: {{\"kicker\":\"NHL PLAYOFFS\",\"headline\":\"HEADLINE ALL CAPS\",\"deck\":\"Under 20 words\",\"byline\":\"By Dan Callahan\",\"body\":\"Three vivid paragraphs separated by \\\\n\\\\n.\"}}"
    else:
        nhl_prompt = f"Write an NHL story for The Sports Page dated {today_str}. No games yesterday.{nhl_news_ctx} Lead with breaking news if available, otherwise write a playoff preview. Return JSON: {{\"kicker\":\"NHL PLAYOFFS\",\"headline\":\"HEADLINE ALL CAPS\",\"deck\":\"Under 20 words\",\"byline\":\"By Dan Callahan\",\"body\":\"Three vivid paragraphs separated by \\\\n\\\\n.\"}}"
    story = claude_call(client, nhl_prompt)

    return {"story": story, "schedule": schedule,
            "boxScores": box_scores, "standings": standings, "leaders": leaders}

def fmt_nhl_standings(raw):
    if not raw:
        print("    NHL Standings: no raw data")
        return []
    east = {"label":"Eastern Conference","teams":[]}
    west = {"label":"Western Conference","teams":[]}
    standings = raw.get("standings", [])
    print(f"    NHL Standings: {len(standings)} teams")
    for t in standings:
        conf = t.get("conferenceName","") or t.get("conferenceAbbrev","")
        l10w  = int(t.get("l10Wins",0) or 0)
        l10l  = int(t.get("l10Losses",0) or 0)
        l10ot = int(t.get("l10OtLosses",0) or 0)
        # Team name — try multiple fields
        name = (t.get("teamName",{}) or {}).get("default","") or                (t.get("teamCommonName",{}) or {}).get("default","") or                t.get("teamName","") or t.get("name","")
        pctg = t.get("pointPctg", t.get("winPctg", 0)) or 0
        try:
            pct_str = f".{str(round(float(pctg)*1000)).zfill(3)}"
        except Exception:
            pct_str = ".000"
        streak_code = t.get("streakCode","") or ""
        streak_count = t.get("streakCount","") or ""
        entry = {
            "rank": int(t.get("conferenceSequence",0) or 0),
            "name": name,
            "w":    int(t.get("wins",0) or 0),
            "l":    int(t.get("losses",0) or 0),
            "pct":  pct_str,
            "gb":   "—",
            "l10":  f"{l10w}-{l10l+l10ot}",
            "strk": f"{streak_code}{streak_count}",
            "home": f"{t.get('homeWins',0)}-{int(t.get('homeLosses',0) or 0)+int(t.get('homeOtLosses',0) or 0)}",
            "away": f"{t.get('roadWins',0)}-{int(t.get('roadLosses',0) or 0)+int(t.get('roadOtLosses',0) or 0)}",
        }
        if "East" in conf or conf in ["E","Eastern"]:
            east["teams"].append(entry)
        else:
            west["teams"].append(entry)
    east["teams"].sort(key=lambda x: x["rank"])
    west["teams"].sort(key=lambda x: x["rank"])
    return [east, west]

def fmt_nhl_leaders_side(conf_abbr, label, season_id):
    cats_config = [
        ("goals",  "Goals",  ["Player","Team","G"]),
        ("assists","Assists",["Player","Team","A"]),
        ("points", "Points", ["Player","Team","G","A","Pts"]),
    ]
    cats = []

    def get_name(p):
        fn = p.get("firstName",{}); ln = p.get("lastName",{})
        fn = fn.get("default","") if isinstance(fn,dict) else str(fn)
        ln = ln.get("default","") if isinstance(ln,dict) else str(ln)
        return f"{fn} {ln}".strip() or p.get("skaterFullName","")

    def get_team(p):
        t = p.get("teamAbbrevAlt","") or p.get("teamAbbrev","")
        return t.get("default","") if isinstance(t,dict) else str(t)

    for cat, display, cols in cats_config:
        for game_type in ["3","2"]:
            data = api_get(
                f"https://api-web.nhle.com/v1/skater-stats-leaders/{season_id}/{game_type}",
                params={"categories": cat, "limit": 8}
            )
            if not data: continue
            players = data.get(cat,[])
            if not players: continue
            rows = []
            for p in players[:8]:
                nm = get_name(p); tm = get_team(p)
                if cat == "points":
                    rows.append([nm,tm,str(p.get("goals",0)),str(p.get("assists",0)),str(p.get("points",0))])
                else:
                    rows.append([nm, tm, str(p.get(cat,0))])
            if rows:
                cats.append({"cat":display,"cols":cols,"rows":rows})
                break

    for game_type in ["3","2"]:
        data = api_get(
            f"https://api-web.nhle.com/v1/goalie-stats-leaders/{season_id}/{game_type}",
            params={"categories":"savePctg","limit":8}
        )
        if not data: continue
        goalies = data.get("savePctg",[])
        if not goalies: continue
        rows = []
        for p in goalies[:8]:
            fn = p.get("firstName",{}); ln = p.get("lastName",{})
            fn = fn.get("default","") if isinstance(fn,dict) else str(fn)
            ln = ln.get("default","") if isinstance(ln,dict) else str(ln)
            name = f"{fn} {ln}".strip()
            team = p.get("teamAbbrevAlt","") or p.get("teamAbbrev","")
            team = team.get("default","") if isinstance(team,dict) else str(team)
            gaa=p.get("goalsAgainstAvg",""); svp=p.get("savePctg",""); gp=p.get("gamesPlayed","")
            rows.append([name,str(team),str(gp),
                         f"{float(gaa):.2f}" if gaa else "—",
                         f".{str(round(float(svp)*1000)).zfill(3)}" if svp else "—"])
        if rows:
            cats.append({"cat":"Goaltending","cols":["Goalie","Team","GP","GAA","SV%"],"rows":rows})
            break

    return {"label": label, "cats": cats}



def fetch_nfl_standings():
    """Fetch NFL standings from ESPN, explicitly requesting the most recent completed season."""
    today = date.today()
    season_year = today.year if today.month >= 9 else today.year - 1
    data = api_get(
        "https://site.api.espn.com/apis/v2/sports/football/nfl/standings",
        {"season": season_year, "seasontype": 2}
    )
    if data and data.get("children"):
        return data
    return api_get("https://site.api.espn.com/apis/v2/sports/football/nfl/standings")

def fetch_nfl_leaders():
    """Fetch NFL season stat leaders from ESPN."""
    today = date.today()
    season_year = today.year if today.month >= 9 else today.year - 1
    result = {"left": {"label":"AFC","cats":[]}, "right": {"label":"NFC","cats":[]}}
    # Try ESPN leaders endpoint — available during season (Sep-Feb), 404 in offseason
    data = api_get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/leaders",
                   {"season": season_year})
    if not data or not data.get("categories"):
        data = api_get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/leaders")
    if not data or not data.get("categories"):
        print("    NFL leaders: endpoint unavailable (offseason)")
        data = None
    if not data:
        return result
    cat_map = {
        "passing":   ("Passing Yards",  ["Player","Team","Att","Cmp","Yds","TD","Int"]),
        "rushing":   ("Rushing Yards",  ["Player","Team","Car","Yds","Avg","TD"]),
        "receiving": ("Receiving Yards",["Player","Team","Rec","Yds","Avg","TD"]),
        "sacks":     ("Sacks",          ["Player","Team","Sacks"]),
    }
    for cat_group in data.get("categories",[]):
        cat_name = cat_group.get("name","").lower()
        if cat_name not in cat_map:
            continue
        display, cols = cat_map[cat_name]
        afc_rows = []; nfc_rows = []
        for leader in cat_group.get("leaders",[])[:8]:
            athlete = leader.get("athlete",{})
            team    = leader.get("team",{})
            name    = athlete.get("shortName", athlete.get("displayName",""))
            conf    = team.get("conferenceId","")
            abbr    = team.get("abbreviation","")
            val     = leader.get("displayValue","")
            row     = [name, abbr, val]
            if conf == "8":   afc_rows.append(row)
            elif conf == "7": nfc_rows.append(row)
        if afc_rows:
            result["left"]["cats"].append({"cat":display,"cols":cols,"rows":afc_rows[:8]})
        if nfc_rows:
            result["right"]["cats"].append({"cat":display,"cols":cols,"rows":nfc_rows[:8]})
    return result

def fmt_nhl_standings(raw):
    if not raw:
        print("    NHL Standings: no raw data")
        return []
    east = {"label":"Eastern Conference","teams":[]}
    west = {"label":"Western Conference","teams":[]}
    standings = raw.get("standings", [])
    print(f"    NHL Standings: {len(standings)} teams")
    for t in standings:
        conf = t.get("conferenceName","") or t.get("conferenceAbbrev","")
        l10w  = int(t.get("l10Wins",0) or 0)
        l10l  = int(t.get("l10Losses",0) or 0)
        l10ot = int(t.get("l10OtLosses",0) or 0)
        name = (t.get("teamName",{}) or {}).get("default","") or                (t.get("teamCommonName",{}) or {}).get("default","") or                t.get("teamName","") or t.get("name","")
        pctg = t.get("pointPctg", t.get("winPctg", 0)) or 0
        try:
            pct_str = f".{str(round(float(pctg)*1000)).zfill(3)}"
        except Exception:
            pct_str = ".000"
        streak_code  = t.get("streakCode","")  or ""
        streak_count = t.get("streakCount","") or ""
        entry = {
            "rank": int(t.get("conferenceSequence",0) or 0),
            "name": name,
            "w":    int(t.get("wins",0) or 0),
            "l":    int(t.get("losses",0) or 0),
            "pct":  pct_str,
            "gb":   "—",
            "l10":  f"{l10w}-{l10l+l10ot}",
            "strk": f"{streak_code}{streak_count}",
            "home": f"{t.get('homeWins',0)}-{int(t.get('homeLosses',0) or 0)+int(t.get('homeOtLosses',0) or 0)}",
            "away": f"{t.get('roadWins',0)}-{int(t.get('roadLosses',0) or 0)+int(t.get('roadOtLosses',0) or 0)}",
        }
        if "East" in conf or conf in ["E","Eastern"]:
            east["teams"].append(entry)
        else:
            west["teams"].append(entry)
    east["teams"].sort(key=lambda x: x["rank"])
    west["teams"].sort(key=lambda x: x["rank"])
    return [east, west]

def build_nfl(client):
    print("  NFL: fetching data from ESPN...")
    ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

    standings_raw = fetch_nfl_standings()
    standings = fmt_espn_nfl_standings(standings_raw)
    leaders   = fetch_nfl_leaders()

    box_scores = []
    game_summaries = []

    for season_type in ["3","2"]:
        data = api_get(f"{ESPN_BASE}/scoreboard", {"seasontype": season_type, "limit": 10})
        if not data: continue
        events = data.get("events",[])
        for event in events[:6]:
            comps = event.get("competitions",[{}])[0]
            if not comps.get("status",{}).get("type",{}).get("completed",False):
                continue
            competitors = comps.get("competitors",[])
            if len(competitors) < 2: continue
            home = next((t for t in competitors if t.get("homeAway")=="home"), competitors[0])
            away = next((t for t in competitors if t.get("homeAway")=="away"), competitors[1])
            away_name  = away.get("team",{}).get("displayName","")
            home_name  = home.get("team",{}).get("displayName","")
            away_score = int(away.get("score",0) or 0)
            home_score = int(home.get("score",0) or 0)
            winner = away_name if away_score > home_score else home_name
            loser  = home_name if away_score > home_score else away_name
            title  = f"{winner} {max(away_score,home_score)}, {loser} {min(away_score,home_score)}"
            event_name = event.get("name", title)
            game_id = event.get("id","")

            away_lines = [int(q.get("value",0) or 0) for q in away.get("linescores",[])]
            home_lines = [int(q.get("value",0) or 0) for q in home.get("linescores",[])]
            ls = {
                "away": {"name": away_name, "scores": away_lines, "r": away_score},
                "home": {"name": home_name, "scores": home_lines, "r": home_score},
            }

            nfl_stats = []; notes = ""
            summary = api_get(f"{ESPN_BASE}/summary", {"event": game_id})
            if summary:
                for cat in summary.get("boxscore",{}).get("players",[]):
                    for stat_group in cat.get("statistics",[]):
                        label = stat_group.get("name","")
                        if label not in ["passing","rushing","receiving"]: continue
                        keys = [k.get("name","") for k in stat_group.get("keys",[])]
                        COL_MAP = {
                            "name":"Player","completions/passingAttempts":"Cmp/Att",
                            "passingYards":"Yds","passingTouchdowns":"TD","interceptions":"Int",
                            "rushingAttempts":"Car","rushingYards":"Yds","rushingTouchdowns":"TD",
                            "receivingTargets":"Tgt","receptions":"Rec","receivingYards":"Yds",
                            "receivingTouchdowns":"TD","avg":"Avg",
                        }
                        cols = [COL_MAP.get(k,k) for k in keys]
                        rows = []
                        for athlete in stat_group.get("athletes",[])[:5]:
                            pname = athlete.get("athlete",{}).get("shortName","")
                            rows.append([pname] + athlete.get("stats",[])[:len(cols)-1])
                        if rows:
                            nfl_stats.append({"label":label.title(),"cols":cols,"rows":rows})

            box_scores.append({
                "title": event_name, "linescore": ls,
                "batting": [], "nflStats": nfl_stats, "notes": notes,
            })
            game_summaries.append(title)
        if box_scores: break

    schedule = [
        {"time":"May 22","away":"Deadline","home":"5th-Year Options","note":"Teams must exercise options for 2021 first-round picks"},
        {"time":"June 1","away":"Cutdown","home":"Roster Moves","note":"Post-June 1 designations take effect"},
        {"time":"July 24","away":"Training","home":"Camps Open","note":"Veteran reporting date for all 32 teams"},
    ]

    scores_txt = "; ".join(game_summaries[:4]) if game_summaries else "NFL offseason"
    story = claude_call(client, f"""Write an NFL offseason story for today's Sports Page.
CONTEXT: The 2025 NFL season concluded in February 2026 with Super Bowl LX.
It is now May 2026 — the NFL offseason. No games are being played.
Write about current offseason news: trades, signings, draft analysis, training camp storylines.
Do NOT write about upcoming Super Bowls or suggest the season is still ongoing.
Recent news or results: {scores_txt}
Return JSON: {{"kicker":"NFL OFFSEASON","headline":"HEADLINE ALL CAPS","deck":"Under 20 words","byline":"By Ray Torino","body":"Three paragraphs separated by \\n\\n."}}""")

    return {"story": story, "schedule": schedule,
            "boxScores": box_scores, "standings": standings, "leaders": leaders}

def fmt_espn_nfl_standings(raw):
    if not raw:
        return []
    divs = []
    for group in raw.get("children",[]):
        for div in group.get("children",[]):
            div_name = div.get("name","")
            teams = []
            for i, entry in enumerate(div.get("standings",{}).get("entries",[])):
                tm    = entry.get("team",{})
                stats = {s["name"]:s["displayValue"] for s in entry.get("stats",[])}
                teams.append({
                    "rank": i+1,
                    "name": tm.get("displayName",""),
                    "w":    stats.get("wins","—"),
                    "l":    stats.get("losses","—"),
                    "pct":  stats.get("winPercent",".000"),
                    "gb":   stats.get("gamesBehind","—"),
                    "note": stats.get("clincher","") or stats.get("playoffSeed",""),
                })
            if teams:
                divs.append({"label": div_name, "teams": teams})
    return divs

def build_front(client, mlb_data, nba_data, nhl_data, nfl_data, today_str='today', now_str='today'):
    print("  Writing front page...")
    mlb_scores = [b["title"] for b in mlb_data.get("boxScores",[])[:5]]
    nba_scores = [b["title"] for b in nba_data.get("boxScores",[])[:3]]
    nhl_scores = [b["title"] for b in nhl_data.get("boxScores",[])[:3]]

    # Pass already-written sport headlines so front page doesn't duplicate them
    mlb_hl = mlb_data.get("story",{}).get("headline","")
    nba_hl = nba_data.get("story",{}).get("headline","")
    nhl_hl = nhl_data.get("story",{}).get("headline","")
    nfl_hl = nfl_data.get("story",{}).get("headline","")
    existing = ", ".join(h for h in [mlb_hl,nba_hl,nhl_hl,nfl_hl] if h)

    # Fetch breaking news for front page context
    all_news = {}
    for sport_key, path in [("mlb","baseball/mlb"),("nba","basketball/nba"),("nhl","hockey/nhl"),("nfl","football/nfl")]:
        news = fetch_sport_news(path, limit=3)
        if news: all_news[sport_key] = news
    news_summary = ""
    if all_news:
        news_summary = "\nMajor breaking sports news today (only use if genuinely significant — death, star player season-ending injury, blockbuster trade):\n" + "\n".join(f"{k.upper()}: {v}" for k,v in all_news.items())

        nba_ctx = '; '.join(nba_scores) if nba_scores else "NBA Playoffs ongoing — conference semifinals in progress"
    nhl_ctx = '; '.join(nhl_scores) if nhl_scores else "NHL Playoffs ongoing — second round in progress"
    mlb_ctx = '; '.join(mlb_scores) if mlb_scores else "No MLB games yesterday"

    content = claude_call(client, f"""You are writing the front page of The Sports Page for {today_str}.

Sports context:
MLB (yesterday\'s results): {mlb_ctx}
NBA Playoffs (May 2026, conference semifinals): {nba_ctx}
NHL Playoffs (May 2026, second round): {nhl_ctx}
NFL: Offseason — the 2025 season ended February 2026 with Super Bowl LX{news_summary}

EDITORIAL RULES:
- Choose the single most newsworthy story across all sports — a walk-off grand slam, a Game 7 win, or a historic pitching performance beats a routine playoff game every time
- If the NBA or NHL had a dramatic result, that leads. If baseball had the best story, baseball leads. Pick like a real editor.
- The three secondary stories should cover different sports when possible — avoid running two baseball stories if there is NHL or NBA news
- The sport section pages already cover these headlines: {existing} — do not repeat the exact same angle; find a fresh frame or different story
- Write specific journalism with real team names and playoff context
- It is May 2026. The NBA and NHL playoffs are in the second round. The NFL is in the offseason.
- Never mention an upcoming Super Bowl or suggest the NFL season is ongoing

Return JSON:
{{
  "headline": {{"kicker":"SPORT NAME","headline":"BIGGEST STORY IN ALL CAPS","deck":"Deck under 20 words","byline":"By Frank Dolan","body":"Three paragraphs separated by \\n\\n."}},
  "secondary": [
    {{"kicker":"SPORT","headline":"HEADLINE","deck":"Deck","byline":"By Frank Dolan","body":"Two paragraphs separated by \\n\\n."}},
    {{"kicker":"SPORT","headline":"HEADLINE","deck":"Deck","byline":"By Frank Dolan","body":"Two paragraphs separated by \\n\\n."}},
    {{"kicker":"SPORT","headline":"HEADLINE","deck":"Deck","byline":"By Frank Dolan","body":"Two paragraphs separated by \\n\\n."}}
  ],
  "column": {{"tag":"FROM THE PRESS BOX","headline":"OPINION HEADLINE","byline":"By Frank Dolan","body":"Two opinionated paragraphs separated by \\n\\n."}}
}}""", max_tokens=3000)

    def fmt_scores(boxes):
        return [{"away": b["linescore"]["away"]["name"],
                 "away_score": b["linescore"]["away"]["r"],
                 "home": b["linescore"]["home"]["name"],
                 "home_score": b["linescore"]["home"]["r"],
                 "status": "Final"}
                for b in boxes if b.get("linescore")]

    this_day = {"items": []}


    return {
        "headline":  content.get("headline",{}),
        "secondary": content.get("secondary",[]),
        "column":    content.get("column",{}),
        "this_day":  this_day if isinstance(this_day, dict) else {},
        "scores": {
            "mlb": fmt_scores(mlb_data.get("boxScores",[])[:8]),
            "nba": fmt_scores(nba_data.get("boxScores",[])[:4]),
            "nhl": fmt_scores(nhl_data.get("boxScores",[])[:4]),
        }
    }

def main():
    print("=== The Sports Page Daily Pipeline ===")
    now = datetime.now(timezone.utc)
    print(f"Running at {now.strftime('%Y-%m-%d %H:%M UTC')}\n")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Use Eastern Time for dates — MLB games end by midnight ET
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
    except ImportError:
        from datetime import timezone as _tz
        et = _tz(timedelta(hours=-4))  # EDT fallback
    now_et    = now.astimezone(et)
    today     = now_et.date().strftime("%Y-%m-%d")
    yesterday = (now_et.date() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"  Dates (ET): today={today}, yesterday={yesterday}")
    mlb_s, nba_s, nhl_s = season_ids()

    print("Building sections...")
    mlb = build_mlb(client, today, yesterday, mlb_s)
    nba = build_nba(client, today, yesterday, nba_s)
    nhl = build_nhl(client, today, yesterday, nhl_s)
    nfl = build_nfl(client)
    front = build_front(client, mlb, nba, nhl, nfl, today_str=now.strftime('%A, %B %-d, %Y'), now_str=now.strftime('%B %-d'))

    output = {
        "date":    now.strftime("%A, %B %-d, %Y"),
        "edition": f"Vol. CXLVIII · No. {now.timetuple().tm_yday + 133}",
        "front":   front,
        "mlb":     mlb,
        "nba":     nba,
        "nhl":     nhl,
        "nfl":     nfl,
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json","w") as f:
        json.dump(output, f, indent=2)
    print(f"\n✓ docs/data.json written ({len(json.dumps(output)):,} bytes)")

    # Generate edition archive files — only once per day
    os.makedirs("docs/editions", exist_ok=True)
    edition_path = f"docs/editions/{today}.html"
    if not os.path.exists(edition_path):
        edition_html = generate_edition_html(output, today)
        if edition_html:
            with open(edition_path, "w") as f:
                f.write(edition_html)
            print(f"✓ Edition page written: {edition_path}")
            update_edition_index(output, today)
        else:
            print("  Edition page skipped (generation failed)")
    else:
        print(f"  Edition page already exists for {today} — skipping")
    print("✓ Pipeline complete.")

def generate_edition_html(data, date_str):
    """Generate a standalone HTML page for a single edition."""
    headline_obj = data.get("front", {}).get("headline", {})
    headline_txt = headline_obj.get("headline", "The Sports Page")
    deck_txt     = headline_obj.get("deck", "")
    date_label   = data.get("date", date_str)
    edition_lbl  = data.get("edition", "")
    sports_present = [s for s in ["mlb","nba","nhl","nfl"]
                      if data.get(s, {}).get("boxScores")]

    data_json = json.dumps(data, ensure_ascii=False)

    # Read the current index.html as the rendering engine base
    try:
        with open("docs/index.html", "r") as f:
            base_html = f.read()
    except FileNotFoundError:
        return None

    # Build the edition page by modifying the base
    # 1. Update <title>
    base_html = base_html.replace(
        "<title>The Sports Page</title>",
        f"<title>The Sports Page — {date_label}</title>"
    )

    # 2. Add SEO meta tags after <title>
    seo_tags = f"""<title>The Sports Page — {date_label}</title>
<meta name="description" content="{headline_txt}. {deck_txt} Full box scores, standings and stories from {date_label}."/>
<meta property="og:title" content="The Sports Page — {date_label}"/>
<meta property="og:description" content="{headline_txt}"/>
<link rel="canonical" href="https://thesportspage.app/editions/{date_str}.html"/>"""
    base_html = base_html.replace(
        f"<title>The Sports Page — {date_label}</title>",
        seo_tags
    )

    # 3. Inject the edition data so it auto-loads without needing data.json
    edition_script = f"""
<script>
// Edition data baked in — no fetch needed
window.__EDITION_DATA__ = {data_json};
window.__EDITION_DATE__ = "{date_str}";
</script>"""
    base_html = base_html.replace("</head>", edition_script + "\n</head>")

    # 4. Patch init() to use baked-in data first, still try data.json for today
    old_init_fetch = """  // Then try to overlay live data from pipeline
  try {
    const res = await fetch('data.json?t=' + Date.now());
    if (!res.ok) throw new Error('data.json not found');
    const text = await res.text();
    if (!text || text.trim()[0] !== '{') throw new Error('data.json is not JSON');
    const d = JSON.parse(text);"""

    new_init_fetch = """  // Load edition data (baked in) or fall back to data.json
  try {
    let d = window.__EDITION_DATA__;
    if (!d) {
      const res = await fetch('../data.json?t=' + Date.now());
      if (!res.ok) throw new Error('data.json not found');
      const text = await res.text();
      if (!text || text.trim()[0] !== '{') throw new Error('not JSON');
      d = JSON.parse(text);
    }"""

    base_html = base_html.replace(old_init_fetch, new_init_fetch)

    # 5. Add edition banner at top of paper (back to archive link)
    old_masthead = '<div class="masthead">'
    edition_banner = f"""<div style="background:#111;color:#fff;padding:5px 24px;display:flex;justify-content:space-between;align-items:center;font-size:.52rem;letter-spacing:.5px;text-transform:uppercase">
  <a href="../archive.html" style="color:#ccc;text-decoration:none;font-weight:700;letter-spacing:1px">&#8592; Archive</a>
  <span style="color:#aaa">{date_label}</span>
  <a href="../index.html" style="color:#ccc;text-decoration:none;font-weight:700;letter-spacing:1px">Today's Edition &#8594;</a>
</div>
<div class="masthead">"""
    base_html = base_html.replace(old_masthead, edition_banner, 1)

    # 6. Fix asset paths (fonts, data.json) for editions/ subdirectory
    base_html = base_html.replace(
        "fetch('data.json?t='",
        "fetch('../data.json?t='"
    )

    return base_html


def update_edition_index(data, date_str):
    """Add this edition to the editions/index.json manifest."""
    index_path = "docs/editions/index.json"
    try:
        with open(index_path, "r") as f:
            index = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        index = {"editions": []}

    # Remove any existing entry for this date
    index["editions"] = [e for e in index["editions"] if e.get("date") != date_str]

    headline_obj = data.get("front", {}).get("headline", {})
    sports = [s for s in ["mlb","nba","nhl","nfl"]
              if data.get(s, {}).get("boxScores")]

    index["editions"].append({
        "date":     date_str,
        "label":    data.get("date", date_str),
        "headline": headline_obj.get("headline", ""),
        "deck":     headline_obj.get("deck", ""),
        "kicker":   headline_obj.get("kicker", ""),
        "sports":   sports,
        "url":      f"editions/{date_str}.html",
    })

    # Sort by date descending
    index["editions"].sort(key=lambda x: x["date"], reverse=True)

    os.makedirs("docs/editions", exist_ok=True)
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)
    print(f"  Edition index updated: {len(index['editions'])} editions")


if __name__ == "__main__":
    main()
