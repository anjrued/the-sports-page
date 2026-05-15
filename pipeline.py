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
Respond ONLY with a valid JSON object. First char { last char }. No markdown, no backticks."""

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
        "hydrate": "linescore,team",
    })
    games = []
    if data:
        for d in data.get("dates", []):
            for g in d.get("games", []):
                if g.get("status", {}).get("abstractGameState") == "Final":
                    games.append(g)
    return games

def mlb_today(today_date):
    """Return today's scheduled games with probable pitchers."""
    data = api_get(f"{MLB}/schedule", {
        "sportId": 1,
        "date": today_date,
        "hydrate": "probablePitcher,team",
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

def fmt_mlb_batting(box, side):
    team_data = box.get("teams", {}).get(side, {})
    team_name = team_data.get("team", {}).get("name", side)
    batters = []
    for pid, p in team_data.get("players", {}).items():
        order = p.get("battingOrder")
        if not order:
            continue
        stats = p.get("stats", {}).get("batting", {})
        if not stats:
            continue
        pos = p.get("position", {}).get("abbreviation", "").lower()
        last = p.get("person", {}).get("fullName", "").split()[-1]
        prefix = "" if int(order) % 100 == 0 else "a-"
        batters.append({
            "_o": int(order),
            "name": f"{prefix}{last} {pos}",
            "ab": stats.get("atBats", 0),
            "r":  stats.get("runs", 0),
            "h":  stats.get("hits", 0),
            "bi": stats.get("rbi", 0),
            "bb": stats.get("baseOnBalls", 0),
            "so": stats.get("strikeOuts", 0),
            "avg": stats.get("avg", ".000"),
        })
    batters.sort(key=lambda x: x["_o"])
    for b in batters:
        del b["_o"]
    ts = team_data.get("teamStats", {}).get("batting", {})
    totals = {"ab": ts.get("atBats",0), "r": ts.get("runs",0),
              "h": ts.get("hits",0),   "bi": ts.get("rbi",0),
              "bb": ts.get("baseOnBalls",0), "so": ts.get("strikeOuts",0)}
    return {"team": team_name, "players": batters, "totals": totals}

def fmt_mlb_notes(box):
    notes = []
    for item in box.get("info", []):
        lbl = item.get("label","")
        val = item.get("value","")
        if lbl in ["HR","2B","3B","SB","WP","LP","SV","LOB","E"]:
            notes.append(f"{lbl}: {val}")
    return ". ".join(notes) + "." if notes else ""

def fmt_mlb_schedule(games):
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
            n = p.get("fullName","").split()
            last = n[-1] if n else ""
            # Try to get record/ERA from a quick stats call
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
    div_order = ["AL East","AL Central","AL West","NL East","NL Central","NL West"]
    divs = {}
    if not raw:
        return []
    for rec in raw.get("records", []):
        div = rec.get("division",{}).get("name","")
        teams = []
        for i, tr in enumerate(rec.get("teamRecords",[])):
            splits = {s["type"]:s for s in tr.get("records",{}).get("splitRecords",[])}
            ho = splits.get("home",{}); aw = splits.get("away",{}); lt = splits.get("lastTen",{})
            gb = tr.get("gamesBack","—")
            teams.append({
                "rank": i+1,
                "name": tr.get("team",{}).get("name",""),
                "w": tr.get("wins",0),
                "l": tr.get("losses",0),
                "pct": tr.get("winningPercentage",".000"),
                "gb": "-" if gb in ["0.0","0"] else gb,
                "l10": f"{lt.get('wins',0)}-{lt.get('losses',0)}",
                "strk": tr.get("streak",{}).get("streakCode",""),
                "home": f"{ho.get('wins',0)}-{ho.get('losses',0)}",
                "away": f"{aw.get('wins',0)}-{aw.get('losses',0)}",
            })
        divs[div] = {"label": div, "teams": teams}
    return [divs[d] for d in div_order if d in divs]

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
    today_games_raw = mlb_today(today_str)
    standings_raw   = mlb_standings(mlb_season)
    print(f"    {len(yesterday_games)} games yesterday, {len(today_games_raw)} today")

    # Schedule
    schedule = fmt_mlb_schedule(today_games_raw)

    # All box scores — full batting for first 3, linescore-only for rest
    box_scores = []
    for i, game in enumerate(yesterday_games[:15]):
        pk        = game.get("gamePk")
        away_name = game.get("teams",{}).get("away",{}).get("team",{}).get("name","")
        home_name = game.get("teams",{}).get("home",{}).get("team",{}).get("name","")
        ls_raw    = mlb_linescore(pk)
        ls        = fmt_mlb_linescore(ls_raw, away_name, home_name)
        if not ls:
            continue
        ar, hr = ls["away"]["r"], ls["home"]["r"]
        winner = away_name if ar > hr else home_name
        loser  = home_name if ar > hr else away_name
        title  = f"{winner.split()[-1]}s {max(ar,hr)}, {loser.split()[-1]}s {min(ar,hr)}"

        batting, notes = [], ""
        if i < 3:  # Full box score for top 3 games
            box_raw = mlb_boxscore(pk)
            if box_raw:
                batting = [fmt_mlb_batting(box_raw,"away"),
                           fmt_mlb_batting(box_raw,"home")]
                notes   = fmt_mlb_notes(box_raw)

        box_scores.append({"title": title, "linescore": ls,
                            "batting": batting, "notes": notes})
        time.sleep(0.2)

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
    story = claude_call(client, f"""Write the lead baseball story for today's Sports Page.
Yesterday's results: {scores_txt}
Return JSON: {{"kicker":"BASEBALL","headline":"HEADLINE ALL CAPS","deck":"Under 20 words","byline":"By [Name], Baseball Writer","body":"Three paragraphs separated by \\n\\n."}}""")

    return {"story": story, "schedule": schedule,
            "boxScores": box_scores, "standings": standings, "leaders": leaders}

# ══════════════════════════════════════════════════════════════════════════════
# NBA  (stats.nba.com via nba_api — official, free, no key)
# ══════════════════════════════════════════════════════════════════════════════

def build_nba(client, today_str, yesterday_str, nba_season):
    print("  NBA: fetching data...")
    try:
        from nba_api.stats.endpoints import (
            scoreboardv2, boxscoretraditionalv2,
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
                time.sleep(0.6)
                obj = endpoint_cls(**kwargs)
                obj._endpoint_headers = NBA_HEADERS
                return obj
            except Exception as e:
                if attempt == 2:
                    print(f"    NBA API error: {e}")
                    return None
                time.sleep(3)
        return None

    # Yesterday's scores
    board = nba_get(scoreboardv2.ScoreBoardV2, game_date=yesterday_str, league_id="00")
    yesterday_games = []
    if board:
        try:
            games_df = board.game_header.get_data_frame()
            line_df  = board.line_score.get_data_frame()
            for _, g in games_df.iterrows():
                gid = g.get("GAME_ID","")
                lines = line_df[line_df["GAME_ID"]==gid]
                if len(lines) >= 2:
                    away_row = lines.iloc[0]
                    home_row = lines.iloc[1]
                    yesterday_games.append({
                        "game_id": gid,
                        "away": away_row.get("TEAM_CITY_NAME","") + " " + away_row.get("TEAM_NAME",""),
                        "home": home_row.get("TEAM_CITY_NAME","") + " " + home_row.get("TEAM_NAME",""),
                        "away_score": int(away_row.get("PTS",0) or 0),
                        "home_score": int(home_row.get("PTS",0) or 0),
                        "status": g.get("GAME_STATUS_TEXT","Final"),
                    })
        except Exception as e:
            print(f"    NBA scoreboard parse error: {e}")

    # Today's schedule
    today_board = nba_get(scoreboardv2.ScoreBoardV2, game_date=today_str, league_id="00")
    schedule = []
    if today_board:
        try:
            games_df  = today_board.game_header.get_data_frame()
            series_df = today_board.series_standings.get_data_frame()
            for _, g in games_df.iterrows():
                gid = g.get("GAME_ID","")
                away = (g.get("VISITOR_TEAM_CITY","") + " " + g.get("VISITOR_TEAM_NICKNAME","")).strip()
                home = (g.get("HOME_TEAM_CITY","") + " " + g.get("HOME_TEAM_NICKNAME","")).strip()
                time_et = g.get("GAME_STATUS_TEXT","TBD")
                note = ""
                if not series_df.empty:
                    sr = series_df[series_df["GAME_ID"]==gid]
                    if not sr.empty:
                        note = sr.iloc[0].get("SERIES_LEADER","")
                entry = {"time": time_et, "away": away, "home": home}
                if note:
                    entry["note"] = note
                schedule.append(entry)
        except Exception as e:
            print(f"    NBA today schedule parse error: {e}")

    # Box scores
    box_scores = []
    for i, g in enumerate(yesterday_games):
        gid = g["game_id"]
        ar, hr = g["away_score"], g["home_score"]
        winner = g["away"] if ar > hr else g["home"]
        loser  = g["home"] if ar > hr else g["away"]
        title  = f"{winner.split()[-1]}s {max(ar,hr)}, {loser.split()[-1]}s {min(ar,hr)}"
        status = g["status"]

        # Linescore from scoreboard
        ls = {
            "away": {"name": g["away"], "scores": [], "r": ar},
            "home": {"name": g["home"], "scores": [], "r": hr},
        }

        batting = []
        if i < 3:  # Full box for top 3 games
            box = nba_get(boxscoretraditionalv2.BoxScoreTraditionalV2, game_id=gid)
            if box:
                try:
                    pl = box.player_stats.get_data_frame()
                    tm = box.team_stats.get_data_frame()

                    # Quarter scores from team stats
                    for _, row in tm.iterrows():
                        side_key = "away" if row.get("TEAM_ID") == \
                            games_df[games_df["GAME_ID"]==gid].iloc[0].get("VISITOR_TEAM_ID") \
                            else "home"
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
    story = claude_call(client, f"""Write the lead basketball story for today's Sports Page.
Yesterday's NBA results: {scores_txt if scores_txt else 'No games yesterday'}
Return JSON: {{"kicker":"NBA PLAYOFFS","headline":"HEADLINE ALL CAPS","deck":"Under 20 words","byline":"By [Name], Basketball Writer","body":"Three paragraphs separated by \\n\\n."}}""")

    return {"story": story, "schedule": schedule,
            "boxScores": box_scores, "standings": standings, "leaders": leaders}

def nba_leaders_side(client, season, conf_filter, label):
    """Get NBA leaders for one conference via nba_api."""
    try:
        from nba_api.stats.endpoints import leagueleaders
        cats_config = [
            ("PTS", "Scoring (PPG)",    ["Player","Team","G","Pts","PPG"]),
            ("REB", "Rebounds (RPG)",   ["Player","Team","G","Reb","RPG"]),
            ("AST", "Assists (APG)",    ["Player","Team","G","Ast","APG"]),
        ]
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
            rows = []
            for _, row in df.head(8).iterrows():
                rows.append([
                    row.get("PLAYER",""),
                    row.get("TEAM",""),
                    str(int(row.get("GP",0) or 0)),
                    str(round(float(row.get(stat,0) or 0)*row.get("GP",1),1)),
                    str(round(float(row.get(stat,0) or 0),1)),
                ])
            if rows:
                cats.append({"cat": display, "cols": cols, "rows": rows})
        return {"label": label, "cats": cats}
    except Exception as e:
        print(f"    NBA leaders error: {e}")
        return {"label": label, "cats": []}

def nba_fallback(client):
    """Fallback NBA section if nba_api unavailable."""
    story = claude_call(client, """Write a brief NBA playoffs story for today's Sports Page.
Return JSON: {"kicker":"NBA PLAYOFFS","headline":"HEADLINE","deck":"Deck","byline":"By Staff","body":"Two paragraphs separated by \\n\\n."}""")
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
                note = g.get("seriesStatus","") or g.get("gameType","")
                entry = {
                    "time": time_str,
                    "away": away.get("name",{}).get("default","") or away.get("fullName",""),
                    "home": home.get("name",{}).get("default","") or home.get("fullName",""),
                }
                if note:
                    entry["note"] = str(note)
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
        title = f"{winner.split()[-1]}s {max(ar,hr)}, {loser.split()[-1]}s {min(ar,hr)}{suffix}"

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
                            "batting": batting, "notes": notes})

    # Standings
    std_raw = api_get(f"{NHL}/standings/{today_str}")
    standings = fmt_nhl_standings(std_raw)

    # Leaders
    leaders = {
        "left":  fmt_nhl_leaders_side("East", "Eastern Conference", nhl_season_id),
        "right": fmt_nhl_leaders_side("West", "Western Conference", nhl_season_id),
    }

    # Story
    print("    Writing NHL story...")
    scores_txt = "; ".join(b["title"] for b in box_scores[:4])
    story = claude_call(client, f"""Write the lead hockey story for today's Sports Page.
Yesterday's NHL results: {scores_txt if scores_txt else 'No games yesterday'}
Return JSON: {{"kicker":"NHL PLAYOFFS","headline":"HEADLINE ALL CAPS","deck":"Under 20 words","byline":"By [Name], Hockey Writer","body":"Three paragraphs separated by \\n\\n."}}""")

    return {"story": story, "schedule": schedule,
            "boxScores": box_scores, "standings": standings, "leaders": leaders}

def fmt_nhl_standings(raw):
    if not raw:
        return []
    east = {"label":"Eastern Conference","teams":[]}
    west = {"label":"Western Conference","teams":[]}
    for t in raw.get("standings",[]):
        conf = t.get("conferenceName","")
        l10w = t.get("l10Wins",0); l10l = t.get("l10Losses",0); l10ot = t.get("l10OtLosses",0)
        entry = {
            "rank": int(t.get("conferenceSequence",0) or 0),
            "name": t.get("teamName",{}).get("default","") or t.get("teamCommonName",{}).get("default",""),
            "w":    int(t.get("wins",0) or 0),
            "l":    int(t.get("losses",0) or 0),
            "pct":  f".{str(round(float(t.get('pointPctg',0))*1000)).zfill(3)}",
            "gb":   "—",
            "l10":  f"{l10w}-{l10l+l10ot}",
            "strk": f"{t.get('streakCode','')}{t.get('streakCount','')}",
            "home": f"{t.get('homeWins',0)}-{t.get('homeLosses',0)+t.get('homeOtLosses',0)}",
            "away": f"{t.get('roadWins',0)}-{t.get('roadLosses',0)+t.get('roadOtLosses',0)}",
        }
        if "East" in conf:
            east["teams"].append(entry)
        else:
            west["teams"].append(entry)
    east["teams"].sort(key=lambda x: x["rank"])
    west["teams"].sort(key=lambda x: x["rank"])
    return [east, west]

def fmt_nhl_leaders_side(conf_abbr, label, season_id):
    cats_config = [
        ("goals",   "Goals (Season)",   ["Player","Team","G"]),
        ("assists", "Assists (Season)", ["Player","Team","A"]),
        ("points",  "Points (Season)",  ["Player","Team","G","A","Pts"]),
    ]
    cats = []
    for cat, display, cols in cats_config:
        # Try playoff leaders first, fall back to regular season
        for game_type in ["3","2"]:
            data = api_get(
                f"https://api-web.nhle.com/v1/skater-stats-leaders/{season_id}/{game_type}",
                params={"categories": cat, "limit": 8}
            )
            if data and data.get(cat):
                rows = []
                for p in data[cat]:
                    name = p.get("lastName",{}).get("default","")
                    team = p.get("teamAbbrevAlt","") or p.get("teamAbbrev",{}).get("default","")
                    if cat == "points":
                        rows.append([name, team,
                                     str(p.get("goals",0)),
                                     str(p.get("assists",0)),
                                     str(p.get("points",0))])
                    else:
                        rows.append([name, team, str(p.get(cat,0))])
                if rows:
                    cats.append({"cat": display, "cols": cols, "rows": rows})
                break
    # Goaltending
    for game_type in ["3","2"]:
        data = api_get(
            f"https://api-web.nhle.com/v1/goalie-stats-leaders/{season_id}/{game_type}",
            params={"categories": "savePctg", "limit": 6}
        )
        if data and data.get("savePctg"):
            rows = []
            for p in data["savePctg"]:
                name = p.get("lastName",{}).get("default","")
                team = p.get("teamAbbrev",{}).get("default","")
                gaa  = p.get("goalsAgainstAvg","")
                svp  = p.get("savePctg","")
                gp   = p.get("gamesPlayed","")
                rows.append([name, team, str(gp), f"{float(gaa):.2f}" if gaa else "—",
                              f".{str(round(float(svp)*1000)).zfill(3)}" if svp else "—"])
            if rows:
                cats.append({"cat":"Goaltending (GAA)","cols":["Goalie","Team","GP","GAA","SV%"],"rows":rows})
            break
    return {"label": label, "cats": cats}

# ══════════════════════════════════════════════════════════════════════════════
# NFL  (ESPN free API for standings, Claude for story + offseason content)
# ══════════════════════════════════════════════════════════════════════════════

def build_nfl(client):
    print("  NFL: fetching standings + writing story...")
    # ESPN free API for standings
    ESPN = "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
    raw = api_get(ESPN)
    standings = fmt_espn_nfl_standings(raw)

    # NFL offseason schedule items
    schedule = [
        {"time":"May 22","away":"Deadline","home":"Fifth-Year Options","note":"Teams must exercise options for 2022 first-round picks"},
        {"time":"June 1","away":"Cutdown","home":"Roster Moves","note":"Post-June 1 designations take effect; cap savings accelerate"},
        {"time":"July 24","away":"Training","home":"Camps Open","note":"Veteran reporting date for all 32 teams"},
    ]

    # Static postseason box scores (no free API for NFL player stats)
    box_scores = [
        {"title":"Super Bowl LIX: Eagles 38, 49ers 10",
         "linescore":{"away":{"name":"Philadelphia","scores":[10,14,7,7],"r":38},
                      "home":{"name":"San Francisco","scores":[3,0,7,0],"r":10}},
         "batting":[],
         "nflStats":[
             {"label":"Passing","cols":["Player","Team","Att","Cmp","Yds","TD","Int","Rating"],
              "rows":[["Hurts","PHI","31","22","221","2","0","112.3"],["Purdy","SF","27","16","142","0","2","48.1"]]},
             {"label":"Rushing","cols":["Player","Team","Car","Yds","Avg","TD"],
              "rows":[["Hurts","PHI","12","72","6.0","1"],["Henry","PHI","22","88","4.0","1"],["McCaffrey","SF","8","31","3.9","0"]]},
             {"label":"Receiving","cols":["Player","Team","Rec","Tgt","Yds","Avg","TD"],
              "rows":[["AJBrown","PHI","6","8","82","13.7","1"],["DeVonta Smith","PHI","5","7","62","12.4","1"],["Aiyuk","SF","6","9","58","9.7","0"]]},
         ],
         "notes":"MVP: Jalen Hurts. Eagles win first championship since Super Bowl LII."},
        {"title":"AFC Championship: Ravens 27, Chiefs 24",
         "linescore":{"away":{"name":"Baltimore","scores":[3,10,7,7],"r":27},
                      "home":{"name":"Kansas City","scores":[7,10,0,7],"r":24}},
         "batting":[],
         "nflStats":[
             {"label":"Passing","cols":["Player","Team","Att","Cmp","Yds","TD","Int"],
              "rows":[["Jackson","BAL","38","28","312","2","1"],["Mahomes","KC","47","29","281","1","2"]]},
             {"label":"Rushing","cols":["Player","Team","Car","Yds","Avg","TD"],
              "rows":[["Henry","BAL","21","98","4.7","1"],["Jackson","BAL","7","44","6.3","0"]]},
         ],
         "notes":"Tucker 47-yd FG with 0:08 remaining. Jackson 28/38, 2 TD."},
    ]

    # Leaders (static — no free NFL API with player stats)
    leaders = {
        "left": {"label":"AFC","cats":[
            {"cat":"Passing Yards","cols":["Player","Team","Att","Cmp","Yds","TD","Int"],
             "rows":[["Allen, Buffalo","BUF","581","387","4,306","34","12"],
                     ["Jackson, Baltimore","BAL","468","302","3,984","37","11"],
                     ["Mahomes, Kansas City","KC","542","348","4,021","32","11"]]},
            {"cat":"Rushing Yards","cols":["Player","Team","Car","Yds","Avg","TD"],
             "rows":[["Henry, Baltimore","BAL","287","1,459","5.1","17"],
                     ["Chubb, Cleveland","CLE","231","1,101","4.8","9"]]},
            {"cat":"Receiving Yards","cols":["Player","Team","Rec","Yds","Avg","TD"],
             "rows":[["Hill, Miami","MIA","108","1,799","16.7","13"],
                     ["Diggs, Buffalo","BUF","96","1,291","13.4","9"]]},
        ]},
        "right": {"label":"NFC","cats":[
            {"cat":"Passing Yards","cols":["Player","Team","Att","Cmp","Yds","TD","Int"],
             "rows":[["Hurts, Philadelphia","PHI","512","341","4,021","36","7"],
                     ["Goff, Detroit","DET","563","376","4,010","30","9"]]},
            {"cat":"Rushing Yards","cols":["Player","Team","Car","Yds","Avg","TD"],
             "rows":[["McCaffrey, San Francisco","SF","298","1,411","4.7","14"],
                     ["Gibbs, Detroit","DET","241","1,088","4.5","11"]]},
            {"cat":"Receiving Yards","cols":["Player","Team","Rec","Yds","Avg","TD"],
             "rows":[["Smith, Philadelphia","PHI","97","1,401","14.4","11"],
                     ["Jefferson, Minnesota","MIN","91","1,377","15.1","10"]]},
        ]},
    }

    story = claude_call(client, """Write a brief NFL offseason news story for today's Sports Page.
Focus on real current news: trades, signings, training camp storylines.
Return JSON: {"kicker":"NFL OFFSEASON","headline":"HEADLINE ALL CAPS","deck":"Under 20 words","byline":"By [Name], NFL Writer","body":"Three paragraphs separated by \\n\\n."}""")

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
                tm = entry.get("team",{})
                stats = {s["name"]:s["displayValue"] for s in entry.get("stats",[])}
                teams.append({
                    "rank": i+1,
                    "name": tm.get("displayName",""),
                    "w":    stats.get("wins","—"),
                    "l":    stats.get("losses","—"),
                    "pct":  stats.get("winPercent",".000"),
                    "gb":   stats.get("gamesBehind","—"),
                    "note": stats.get("clincher",""),
                })
            if teams:
                divs.append({"label": div_name, "teams": teams})
    return divs

# ══════════════════════════════════════════════════════════════════════════════
# FRONT PAGE  (Claude writes based on real data summary)
# ══════════════════════════════════════════════════════════════════════════════

def build_front(client, mlb_data, nba_data, nhl_data, nfl_data):
    print("  Writing front page...")

    mlb_scores = [b["title"] for b in mlb_data.get("boxScores",[])[:5]]
    nba_scores = [b["title"] for b in nba_data.get("boxScores",[])[:3]]
    nhl_scores = [b["title"] for b in nhl_data.get("boxScores",[])[:3]]

    content = claude_call(client, f"""Write the front page for today's Sports Page newspaper.

Real results from yesterday:
MLB: {'; '.join(mlb_scores) if mlb_scores else 'No games'}
NBA: {'; '.join(nba_scores) if nba_scores else 'No games'}
NHL: {'; '.join(nhl_scores) if nhl_scores else 'No games'}

Return JSON:
{{
  "headline": {{"kicker":"SPORT","headline":"BIGGEST STORY IN ALL CAPS","deck":"Deck under 20 words","byline":"By [Name], Sports Writer","body":"Three paragraphs separated by \\n\\n."}},
  "secondary": [
    {{"kicker":"SPORT","headline":"HEADLINE","deck":"Deck","byline":"By [Name]","body":"Two paragraphs separated by \\n\\n."}},
    {{"kicker":"SPORT","headline":"HEADLINE","deck":"Deck","byline":"By [Name]","body":"Two paragraphs separated by \\n\\n."}},
    {{"kicker":"SPORT","headline":"HEADLINE","deck":"Deck","byline":"By [Name]","body":"Two paragraphs separated by \\n\\n."}}
  ],
  "column": {{"tag":"FROM THE PRESS BOX","headline":"OPINION HEADLINE","byline":"By Pat McAllister","body":"Two opinionated paragraphs separated by \\n\\n."}}
}}""", max_tokens=3000)

    # Build scores sidebar from real data
    def fmt_scores(boxes):
        return [{"away": b["linescore"]["away"]["name"].split()[-1],
                 "away_score": b["linescore"]["away"]["r"],
                 "home": b["linescore"]["home"]["name"].split()[-1],
                 "home_score": b["linescore"]["home"]["r"],
                 "status": b.get("notes","Final")[:30]}
                for b in boxes if b.get("linescore")]

    return {
        "headline":  content.get("headline",{}),
        "secondary": content.get("secondary",[]),
        "column":    content.get("column",{}),
        "scores": {
            "mlb": fmt_scores(mlb_data.get("boxScores",[])[:8]),
            "nba": fmt_scores(nba_data.get("boxScores",[])[:4]),
            "nhl": fmt_scores(nhl_data.get("boxScores",[])[:4]),
        }
    }

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=== The Sports Page Daily Pipeline ===")
    now = datetime.now(timezone.utc)
    print(f"Running at {now.strftime('%Y-%m-%d %H:%M UTC')}\n")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    today     = now.date().strftime("%Y-%m-%d")
    yesterday = (now.date() - timedelta(days=1)).strftime("%Y-%m-%d")
    mlb_s, nba_s, nhl_s = season_ids()

    print("Building sections...")
    mlb = build_mlb(client, today, yesterday, mlb_s)
    nba = build_nba(client, today, yesterday, nba_s)
    nhl = build_nhl(client, today, yesterday, nhl_s)
    nfl = build_nfl(client)
    front = build_front(client, mlb, nba, nhl, nfl)

    output = {
        "date":    now.strftime("%A, %B %-d, %Y"),
        "edition": f"Vol. CXLVIII · No. {now.timetuple().tm_yday + 133}",
        "weather": "Check your local forecast",
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
    print("✓ Pipeline complete.")

if __name__ == "__main__":
    main()
