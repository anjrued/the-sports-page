#!/usr/bin/env python3
"""
The Sports Page — Daily Pipeline
Makes one Claude call per section so each fits within token limits.
"""

import json, os, re
from datetime import datetime, timezone
import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM = """You are the sports editor of The Sports Page, a classic American daily newspaper.
Generate realistic, detailed, and internally consistent sports data.
Write vivid newspaper journalism — inverted pyramid, specific, real player names.
No em-dashes anywhere. No first person.
Respond ONLY with a valid JSON object. First char { last char }. No markdown, no backticks."""

def claude(client, prompt, max_tokens=6000):
    """Single Claude call — no tools, pure generation from training knowledge."""
    r = client.messages.create(
        model=MODEL, max_tokens=max_tokens,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    texts = [b for b in r.content if b.type == "text"]
    if not texts:
        raise ValueError(f"No text in response (stop_reason={r.stop_reason})")
    raw = texts[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    s, e = raw.find('{'), raw.rfind('}')+1
    if s == -1 or e == 0:
        raise ValueError(f"No JSON object found. Response started: {raw[:200]}")
    return json.loads(raw[s:e])

# ── FRONT PAGE ────────────────────────────────────────────────────────────────
def gen_front(client, date):
    print("  Writing front page...")
    return claude(client, f"""Write the front page for {date} of The Sports Page newspaper.

Return this JSON (fill ALL values with real current data):
{{
  "headline": {{
    "kicker": "SPORT NAME",
    "headline": "TODAY'S BIGGEST STORY IN ALL CAPS",
    "deck": "Elaborating deck under 20 words",
    "byline": "By [Full Name], Sports Writer",
    "body": "Three vivid paragraphs separated by \\n\\n. Real names, real scores."
  }},
  "secondary": [
    {{"kicker":"SPORT","headline":"REAL HEADLINE","deck":"Deck","byline":"By [Name]","body":"Two paragraphs separated by \\n\\n."}},
    {{"kicker":"SPORT","headline":"REAL HEADLINE","deck":"Deck","byline":"By [Name]","body":"Two paragraphs separated by \\n\\n."}},
    {{"kicker":"SPORT","headline":"REAL HEADLINE","deck":"Deck","byline":"By [Name]","body":"Two paragraphs separated by \\n\\n."}}
  ],
  "column": {{
    "tag": "FROM THE PRESS BOX",
    "headline": "OPINION COLUMN HEADLINE IN ALL CAPS",
    "byline": "By Pat McAllister",
    "body": "Two punchy opinionated paragraphs separated by \\n\\n."
  }},
  "scores": {{
    "mlb": [
      {{"away":"NYY","away_score":6,"home":"BOS","home_score":4,"status":"Final"}},
      {{"away":"LAD","away_score":9,"home":"SF","home_score":2,"status":"Final"}},
      {{"away":"ATL","away_score":7,"home":"PHI","home_score":3,"status":"Final"}},
      {{"away":"TOR","away_score":8,"home":"BAL","home_score":3,"status":"Final"}},
      {{"away":"SEA","away_score":6,"home":"OAK","home_score":0,"status":"Final"}},
      {{"away":"CLE","away_score":2,"home":"DET","home_score":1,"status":"Final"}}
    ],
    "nba": [
      {{"away":"IND","away_score":112,"home":"NYK","home_score":118,"status":"Final/OT","note":"NYK leads 3-3"}},
      {{"away":"OKC","away_score":107,"home":"DEN","home_score":99,"status":"Final","note":"OKC wins 4-1"}},
      {{"away":"MIN","away_score":93,"home":"GSW","home_score":88,"status":"Final","note":"MIN leads 3-2"}},
      {{"away":"BOS","away_score":101,"home":"CLE","home_score":98,"status":"Final","note":"Series tied 3-3"}}
    ],
    "nhl": [
      {{"away":"BOS","away_score":3,"home":"FLA","home_score":4,"status":"Final/2OT","note":"FLA leads 3-2"}},
      {{"away":"EDM","away_score":3,"home":"VAN","home_score":2,"status":"Final/OT","note":"EDM wins 4-1"}},
      {{"away":"CAR","away_score":5,"home":"NJD","home_score":1,"status":"Final","note":"CAR wins 4-2"}},
      {{"away":"NYR","away_score":2,"home":"WSH","home_score":4,"status":"Final","note":"Series tied 3-3"}}
    ]
  }}
}}""")

# ── MLB ────────────────────────────────────────────────────────────────────────
def gen_mlb(client, date):
    print("  Writing MLB section...")
    return claude(client, f"""Write the Baseball section for {date} of The Sports Page. Include real pitcher names for today's schedule.

Return this JSON with ALL real current data:
{{
  "story": {{
    "kicker": "BASEBALL",
    "headline": "MLB HEADLINE IN ALL CAPS",
    "deck": "Deck under 20 words",
    "byline": "By [Full Name], Baseball Writer",
    "body": "Three paragraphs separated by \\n\\n. Real players, real scores."
  }},
  "schedule": [
    {{"time":"1:05 PM ET","away":"NY Yankees","home":"Baltimore","asp":"Fried (4-2, 2.91)","hsp":"Bradish (1-5, 4.83)"}},
    {{"time":"1:10 PM ET","away":"LA Angels","home":"Cleveland","asp":"Detmers (1-3, 4.33)","hsp":"Messick (4-1, 2.30)"}},
    {{"time":"6:40 PM ET","away":"Washington","home":"Cincinnati","asp":"JIrvin (1-4, 5.22)","hsp":"Lodolo (0-1, 6.75)"}},
    {{"time":"6:40 PM ET","away":"Colorado","home":"Pittsburgh","asp":"Quintana (1-2, 3.90)","hsp":"MKeller (4-1, 2.87)"}},
    {{"time":"6:45 PM ET","away":"Philadelphia","home":"Boston","asp":"Painter (1-4, 6.89)","hsp":"SGray (3-1, 3.54)"}},
    {{"time":"7:07 PM ET","away":"Tampa Bay","home":"Toronto","asp":"Jax (1-2, 5.00)","hsp":"Cease (3-1, 2.58)"}},
    {{"time":"7:10 PM ET","away":"Detroit","home":"NY Mets","asp":"FValdez (2-2, 4.57)","hsp":"Scott (0-0, 3.27)"}},
    {{"time":"7:15 PM ET","away":"Chi Cubs","home":"Atlanta","asp":"Imanaga (4-2, 2.28)","hsp":"Ritchie (1-0, 3.63)"}},
    {{"time":"7:40 PM ET","away":"Kansas City","home":"Chi White Sox","asp":"SLugo (1-2, 3.21)","hsp":"Schultz (2-2, 4.68)"}},
    {{"time":"9:40 PM ET","away":"St. Louis","home":"LA Dodgers","asp":"Mikolas (2-3, 4.44)","hsp":"Glasnow (4-1, 2.88)"}},
    {{"time":"9:40 PM ET","away":"San Francisco","home":"San Diego","asp":"Webb (3-2, 3.11)","hsp":"Darvish (2-2, 3.75)"}},
    {{"time":"10:10 PM ET","away":"Milwaukee","home":"Arizona","asp":"Peralta (1-3, 5.22)","hsp":"Pfaadt (2-2, 3.98)"}}
  ],
  "boxScores": [
    {{
      "title": "Team1 X, Team2 Y",
      "linescore": {{
        "away": {{"name":"Team1","scores":[0,2,0,1,0,0,2,0,1],"r":6,"h":11,"e":0}},
        "home": {{"name":"Team2","scores":[0,0,2,0,1,0,0,1,0],"r":4,"h":9,"e":1}}
      }},
      "batting": [
        {{
          "team": "Team1",
          "players": [
            {{"name":"Lastname pos","ab":4,"r":1,"h":2,"bi":1,"bb":1,"so":1,"avg":".312"}},
            {{"name":"Lastname pos","ab":5,"r":1,"h":2,"bi":1,"bb":0,"so":1,"avg":".298"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":1,"bi":2,"bb":1,"so":2,"avg":".310"}},
            {{"name":"Lastname pos","ab":5,"r":0,"h":2,"bi":0,"bb":0,"so":1,"avg":".271"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":1,"bi":0,"bb":1,"so":1,"avg":".244"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":1,"bi":1,"bb":0,"so":2,"avg":".228"}},
            {{"name":"Lastname pos","ab":4,"r":0,"h":1,"bi":0,"bb":0,"so":1,"avg":".239"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":1,"bi":1,"bb":0,"so":2,"avg":".252"}},
            {{"name":"Lastname pos","ab":3,"r":0,"h":0,"bi":0,"bb":1,"so":1,"avg":".216"}}
          ],
          "totals": {{"ab":37,"r":6,"h":11,"bi":6,"bb":4,"so":12}}
        }},
        {{
          "team": "Team2",
          "players": [
            {{"name":"Lastname pos","ab":4,"r":1,"h":2,"bi":0,"bb":1,"so":1,"avg":".283"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":1,"bi":1,"bb":1,"so":2,"avg":".265"}},
            {{"name":"Lastname pos","ab":5,"r":0,"h":2,"bi":1,"bb":0,"so":1,"avg":".291"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":2,"bi":0,"bb":0,"so":1,"avg":".275"}},
            {{"name":"Lastname pos","ab":4,"r":0,"h":1,"bi":1,"bb":0,"so":0,"avg":".270"}},
            {{"name":"Lastname pos","ab":4,"r":0,"h":1,"bi":0,"bb":0,"so":2,"avg":".211"}},
            {{"name":"Lastname pos","ab":3,"r":1,"h":0,"bi":0,"bb":1,"so":2,"avg":".188"}},
            {{"name":"Lastname pos","ab":4,"r":0,"h":0,"bi":1,"bb":0,"so":3,"avg":".198"}},
            {{"name":"Lastname pos","ab":3,"r":0,"h":0,"bi":0,"bb":1,"so":2,"avg":".201"}}
          ],
          "totals": {{"ab":35,"r":4,"h":9,"bi":4,"bb":4,"so":14}}
        }}
      ],
      "notes": "HR: Judge (16). 2B: Chisholm (8), Devers (11). WP: Schmidt (3-2). LP: Sale (3-3). SV: CSmith (12). A: 36,741."
    }},
    {{
      "title": "Team3 X, Team4 Y",
      "linescore": {{
        "away": {{"name":"Team3","scores":[0,2,0,3,0,0,4,0,0],"r":9,"h":14,"e":0}},
        "home": {{"name":"Team4","scores":[0,0,0,0,1,0,1,0,0],"r":2,"h":6,"e":1}}
      }},
      "batting": [
        {{
          "team": "Team3",
          "players": [
            {{"name":"Lastname pos","ab":5,"r":2,"h":3,"bi":2,"bb":0,"so":0,"avg":".318"}},
            {{"name":"Lastname pos","ab":4,"r":2,"h":2,"bi":4,"bb":1,"so":1,"avg":".321"}},
            {{"name":"Lastname pos","ab":5,"r":1,"h":2,"bi":1,"bb":0,"so":1,"avg":".289"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":2,"bi":1,"bb":1,"so":1,"avg":".244"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":2,"bi":0,"bb":0,"so":1,"avg":".295"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":1,"bi":1,"bb":0,"so":1,"avg":".248"}},
            {{"name":"Lastname pos","ab":4,"r":0,"h":1,"bi":0,"bb":0,"so":2,"avg":".211"}},
            {{"name":"Lastname pos","ab":3,"r":1,"h":1,"bi":0,"bb":1,"so":1,"avg":".239"}},
            {{"name":"Lastname pos","ab":3,"r":0,"h":0,"bi":0,"bb":1,"so":1,"avg":".222"}}
          ],
          "totals": {{"ab":36,"r":9,"h":14,"bi":9,"bb":4,"so":9}}
        }},
        {{
          "team": "Team4",
          "players": [
            {{"name":"Lastname pos","ab":4,"r":0,"h":1,"bi":0,"bb":0,"so":2,"avg":".241"}},
            {{"name":"Lastname pos","ab":3,"r":0,"h":1,"bi":0,"bb":1,"so":1,"avg":".248"}},
            {{"name":"Lastname pos","ab":4,"r":1,"h":1,"bi":0,"bb":0,"so":2,"avg":".258"}},
            {{"name":"Lastname pos","ab":4,"r":0,"h":1,"bi":1,"bb":0,"so":1,"avg":".241"}},
            {{"name":"Lastname pos","ab":4,"r":0,"h":1,"bi":0,"bb":0,"so":1,"avg":".271"}},
            {{"name":"Lastname pos","ab":3,"r":1,"h":1,"bi":1,"bb":1,"so":0,"avg":".234"}},
            {{"name":"Lastname pos","ab":3,"r":0,"h":0,"bi":0,"bb":0,"so":2,"avg":".198"}},
            {{"name":"Lastname pos","ab":3,"r":0,"h":0,"bi":0,"bb":0,"so":2,"avg":".201"}},
            {{"name":"Lastname pos","ab":3,"r":0,"h":0,"bi":0,"bb":0,"so":2,"avg":".218"}}
          ],
          "totals": {{"ab":31,"r":2,"h":6,"bi":2,"bb":2,"so":13}}
        }}
      ],
      "notes": "HR: Ohtani (14), Ohtani (15). WP: Glasnow (4-1). LP: Webb (3-3). A: 40,312."
    }}
  ],
  "standings": [
    {{"label":"AL East","teams":[{{"rank":1,"name":"Tampa Bay","w":28,"l":13,"pct":".683","gb":"-","l10":"9-1","strk":"W3","home":"14-4","away":"14-9"}},{{"rank":2,"name":"NY Yankees","w":27,"l":16,"pct":".628","gb":"2.0","l10":"5-5","strk":"W1","home":"14-6","away":"13-10"}},{{"rank":3,"name":"Baltimore","w":19,"l":24,"pct":".442","gb":"10.0","l10":"4-6","strk":"L1","home":"11-12","away":"8-12"}},{{"rank":4,"name":"Toronto","w":18,"l":24,"pct":".429","gb":"10.5","l10":"3-7","strk":"L3","home":"12-11","away":"6-13"}},{{"rank":5,"name":"Boston","w":17,"l":24,"pct":".415","gb":"11.0","l10":"5-5","strk":"L2","home":"7-13","away":"10-11"}}]}},
    {{"label":"AL Central","teams":[{{"rank":1,"name":"Cleveland","w":23,"l":21,"pct":".523","gb":"-","l10":"5-5","strk":"W2","home":"12-9","away":"11-12"}},{{"rank":2,"name":"Chi White Sox","w":20,"l":21,"pct":".488","gb":"1.5","l10":"6-4","strk":"W3","home":"10-9","away":"10-12"}},{{"rank":3,"name":"Minnesota","w":19,"l":23,"pct":".452","gb":"3.0","l10":"5-5","strk":"W3","home":"11-10","away":"8-13"}},{{"rank":4,"name":"Kansas City","w":19,"l":23,"pct":".452","gb":"3.0","l10":"6-4","strk":"L2","home":"13-10","away":"6-13"}},{{"rank":5,"name":"Detroit","w":19,"l":23,"pct":".452","gb":"3.0","l10":"3-7","strk":"L1","home":"12-6","away":"7-17"}}]}},
    {{"label":"AL West","teams":[{{"rank":1,"name":"Athletics","w":21,"l":20,"pct":".512","gb":"-","l10":"4-6","strk":"L2","home":"8-9","away":"13-11"}},{{"rank":2,"name":"Seattle","w":21,"l":22,"pct":".488","gb":"1.0","l10":"5-5","strk":"W2","home":"12-11","away":"9-11"}},{{"rank":3,"name":"Texas","w":20,"l":22,"pct":".476","gb":"1.5","l10":"4-6","strk":"W1","home":"10-10","away":"10-12"}},{{"rank":4,"name":"LA Angels","w":16,"l":27,"pct":".372","gb":"6.0","l10":"4-6","strk":"L2","home":"8-10","away":"8-17"}},{{"rank":5,"name":"Houston","w":16,"l":27,"pct":".372","gb":"6.0","l10":"4-6","strk":"L4","home":"9-12","away":"7-15"}}]}},
    {{"label":"NL East","teams":[{{"rank":1,"name":"Atlanta","w":29,"l":13,"pct":".690","gb":"-","l10":"7-3","strk":"W3","home":"13-6","away":"16-7"}},{{"rank":2,"name":"Philadelphia","w":20,"l":22,"pct":".476","gb":"9.0","l10":"7-3","strk":"W3","home":"12-12","away":"8-10"}},{{"rank":3,"name":"Washington","w":20,"l":22,"pct":".476","gb":"9.0","l10":"5-5","strk":"W1","home":"6-13","away":"14-9"}},{{"rank":4,"name":"Miami","w":19,"l":23,"pct":".452","gb":"10.0","l10":"4-6","strk":"L1","home":"14-12","away":"5-11"}},{{"rank":5,"name":"NY Mets","w":16,"l":25,"pct":".390","gb":"12.5","l10":"6-4","strk":"W1","home":"7-12","away":"9-13"}}]}},
    {{"label":"NL Central","teams":[{{"rank":1,"name":"Chi Cubs","w":27,"l":15,"pct":".643","gb":"-","l10":"7-3","strk":"L3","home":"18-5","away":"9-10"}},{{"rank":2,"name":"Milwaukee","w":23,"l":16,"pct":".590","gb":"2.5","l10":"8-2","strk":"W5","home":"14-8","away":"9-8"}},{{"rank":3,"name":"St. Louis","w":24,"l":17,"pct":".585","gb":"2.5","l10":"6-4","strk":"W1","home":"10-10","away":"14-7"}},{{"rank":4,"name":"Pittsburgh","w":23,"l":19,"pct":".548","gb":"4.0","l10":"7-3","strk":"W1","home":"12-9","away":"11-10"}},{{"rank":5,"name":"Cincinnati","w":22,"l":20,"pct":".524","gb":"5.0","l10":"2-8","strk":"L1","home":"12-10","away":"10-10"}}]}},
    {{"label":"NL West","teams":[{{"rank":1,"name":"San Diego","w":24,"l":17,"pct":".585","gb":"-","l10":"5-5","strk":"L1","home":"13-10","away":"11-7"}},{{"rank":2,"name":"LA Dodgers","w":24,"l":18,"pct":".571","gb":"0.5","l10":"4-6","strk":"L4","home":"13-10","away":"11-8"}},{{"rank":3,"name":"Arizona","w":20,"l":21,"pct":".488","gb":"4.0","l10":"4-6","strk":"L1","home":"12-9","away":"8-12"}},{{"rank":4,"name":"San Francisco","w":18,"l":24,"pct":".429","gb":"6.5","l10":"5-5","strk":"W3","home":"10-12","away":"8-12"}},{{"rank":5,"name":"Colorado","w":16,"l":26,"pct":".381","gb":"8.5","l10":"2-8","strk":"L3","home":"8-11","away":"8-15"}}]}}
  ],
  "leaders": {{
    "left": {{
      "label": "American League",
      "cats": [
        {{"cat":"Batting Average","cols":["Player","Team","G","AB","H","Avg"],"rows":[["Langeliers","Athletics","37","153","52",".340"],["JoJung","Texas","39","147","47",".320"],["RGreene","Detroit","42","149","47",".315"],["Simpson","Tampa Bay","40","156","49",".314"],["Rice","NY Yankees","38","129","40",".310"],["YAlvarez","Houston","43","159","49",".308"],["WittJr","Kansas City","43","167","51",".305"],["YDiaz","Tampa Bay","39","150","44",".293"]]}},
        {{"cat":"Home Runs","cols":["Player","Team","HR"],"rows":[["Judge","NY Yankees","16"],["Murakami","Chi White Sox","15"],["YAlvarez","Houston","13"],["Buxton","Minnesota","13"],["Rice","NY Yankees","13"],["Langeliers","Athletics","12"],["Caminero","Tampa Bay","11"],["Trout","LA Angels","11"]]}},
        {{"cat":"RBI","cols":["Player","Team","RBI"],"rows":[["Aranda","Tampa Bay","33"],["Judge","NY Yankees","30"],["YAlvarez","Houston","29"],["Bellinger","NY Yankees","29"],["Murakami","Chi White Sox","29"],["Rice","NY Yankees","29"],["CMontgomery","Chi White Sox","28"],["Soler","LA Angels","28"]]}},
        {{"cat":"Hits","cols":["Player","Team","H"],"rows":[["Langeliers","Athletics","52"],["WittJr","Kansas City","51"],["YAlvarez","Houston","49"],["Clement","Toronto","49"],["Simpson","Tampa Bay","49"],["Arozarena","Seattle","47"],["RGreene","Detroit","47"],["JoJung","Texas","47"]]}},
        {{"cat":"Stolen Bases","cols":["Player","Team","SB"],"rows":[["JoRamirez","Cleveland","16"],["Simpson","Tampa Bay","14"],["Caballero","NY Yankees","13"],["WittJr","Kansas City","12"],["ChisholmJr","NY Yankees","11"],["Arozarena","Seattle","10"]]}},
        {{"cat":"ERA","cols":["Pitcher","Team","IP","ERA"],"rows":[["Messick","Cleveland","58.1","2.30"],["JSoriano","LA Angels","56.2","2.55"],["Cease","Toronto","62.0","2.58"],["GWilliams","Cleveland","54.1","3.12"],["Ober","Minnesota","52.0","3.18"],["SGray","Boston","58.2","3.54"]]}},
        {{"cat":"Strikeouts","cols":["Pitcher","Team","K"],"rows":[["Cease","Toronto","66"],["GWilliams","Cleveland","66"],["JSoriano","LA Angels","61"],["Schlittler","NY Yankees","59"],["WWarren","NY Yankees","59"],["deGrom","Texas","57"]]}},
        {{"cat":"Saves","cols":["Pitcher","Team","SV"],"rows":[["CSmith","Cleveland","12"],["Baker","Tampa Bay","11"],["Erceg","Kansas City","10"],["Chapman","Boston","8"],["AMunoz","Seattle","8"],["KJansen","Detroit","7"]]}}
      ]
    }},
    "right": {{
      "label": "National League",
      "cats": [
        {{"cat":"Batting Average","cols":["Player","Team","G","AB","H","Avg"],"rows":[["Marsh","Philadelphia","38","137","48",".350"],["OLopez","Miami","41","163","55",".337"],["IVargas","Arizona","34","134","45",".336"],["TJohnston","Colorado","38","122","40",".328"],["Ohtani","LA Dodgers","46","168","54",".321"],["NGonzales","Pittsburgh","38","140","45",".321"],["APages","LA Dodgers","42","154","49",".318"],["XEdwards","Miami","42","153","48",".314"]]}},
        {{"cat":"Home Runs","cols":["Player","Team","HR"],"rows":[["Ohtani","LA Dodgers","15"],["Harper","Philadelphia","13"],["Acuna","Atlanta","11"],["Olson","Atlanta","8"],["Alonso","NY Mets","8"],["Machado","San Diego","7"],["Arenado","St. Louis","7"]]}},
        {{"cat":"RBI","cols":["Player","Team","RBI"],"rows":[["Ohtani","LA Dodgers","42"],["Alonso","NY Mets","27"],["Olson","Atlanta","26"],["Harper","Philadelphia","25"],["Goldschmidt","St. Louis","24"],["Freeman","LA Dodgers","23"]]}},
        {{"cat":"Hits","cols":["Player","Team","H"],"rows":[["OLopez","Miami","55"],["Marsh","Philadelphia","48"],["Ohtani","LA Dodgers","54"],["APages","LA Dodgers","49"],["NGonzales","Pittsburgh","45"],["IVargas","Arizona","45"]]}},
        {{"cat":"Stolen Bases","cols":["Player","Team","SB"],"rows":[["Acuna","Atlanta","18"],["Betts","LA Dodgers","14"],["Rojas","LA Dodgers","12"],["Hampson","Colorado","11"],["Newman","Pittsburgh","10"]]}},
        {{"cat":"ERA","cols":["Pitcher","Team","IP","ERA"],"rows":[["Imanaga","Chi Cubs","61.0","2.28"],["MKeller","Pittsburgh","57.2","2.87"],["Glasnow","LA Dodgers","56.0","2.88"],["Webb","San Francisco","61.1","3.11"],["Darvish","San Diego","58.0","3.75"]]}},
        {{"cat":"Strikeouts","cols":["Pitcher","Team","K"],"rows":[["Imanaga","Chi Cubs","52"],["MKeller","Pittsburgh","48"],["Glasnow","LA Dodgers","46"],["Webb","San Francisco","44"],["Darvish","San Diego","43"]]}},
        {{"cat":"Saves","cols":["Pitcher","Team","SV"],"rows":[["Bednar","Pittsburgh","10"],["Helsley","St. Louis","7"],["Iglesias","Miami","7"],["Robertson","Chi Cubs","6"],["Knebel","Philadelphia","6"]]}}
      ]
    }}
  }}
}}
""")

# ── NBA ────────────────────────────────────────────────────────────────────────
def gen_nba(client, date):
    print("  Writing NBA section...")
    return claude(client, f"""Write the Basketball section for {date} of The Sports Page.

Return this JSON with ALL real current data:
{{
  "story": {{
    "kicker": "NBA PLAYOFFS",
    "headline": "NBA HEADLINE IN ALL CAPS",
    "deck": "Deck under 20 words",
    "byline": "By [Full Name], Basketball Writer",
    "body": "Three paragraphs separated by \\n\\n."
  }},
  "schedule": [
    {{"time":"8:00 PM ET","away":"Indiana Pacers","home":"New York Knicks","note":"Game 7 — Series tied 3-3"}},
    {{"time":"10:30 PM ET","away":"Minnesota Timberwolves","home":"Golden State Warriors","note":"Game 6 — MIN leads 3-2"}}
  ],
  "boxScores": [
    {{
      "title": "Knicks 118, Pacers 112 (OT)",
      "linescore": {{"away":{{"name":"Indiana","scores":[28,30,24,18,12],"r":112}},"home":{{"name":"New York","scores":[22,31,24,23,18],"r":118}}}},
      "batting": [
        {{"team":"Indiana","players":[
          {{"name":"Siakam sf","min":"42","fg":"7-18","tp":"1-4","ft":"2-2","reb":"9","ast":"4","pts":"17"}},
          {{"name":"Turner c","min":"38","fg":"5-10","tp":"2-5","ft":"1-2","reb":"8","ast":"2","pts":"13"}},
          {{"name":"Haliburton pg","min":"44","fg":"5-17","tp":"2-8","ft":"2-2","reb":"4","ast":"9","pts":"14"}},
          {{"name":"Mathurin sg","min":"36","fg":"8-14","tp":"3-6","ft":"5-6","reb":"5","ast":"1","pts":"24"}},
          {{"name":"Nembhard g","min":"40","fg":"6-11","tp":"4-7","ft":"0-0","reb":"3","ast":"5","pts":"16"}},
          {{"name":"Sheppard","min":"26","fg":"5-9","tp":"2-4","ft":"2-2","reb":"2","ast":"3","pts":"14"}},
          {{"name":"McConnell","min":"28","fg":"4-7","tp":"0-1","ft":"0-0","reb":"3","ast":"6","pts":"8"}},
          {{"name":"Toppin","min":"11","fg":"2-3","tp":"0-0","ft":"2-2","reb":"3","ast":"0","pts":"6"}}
        ],"totals":{{"fg":"42-89","tp":"14-35","ft":"14-16","reb":"37","ast":"30","pts":"112"}}}},
        {{"team":"New York","players":[
          {{"name":"Anunoby sf","min":"44","fg":"7-14","tp":"2-5","ft":"2-2","reb":"6","ast":"2","pts":"18"}},
          {{"name":"Towns c","min":"40","fg":"8-16","tp":"2-5","ft":"4-5","reb":"11","ast":"3","pts":"22"}},
          {{"name":"Brunson pg","min":"47","fg":"14-26","tp":"3-8","ft":"13-15","reb":"3","ast":"6","pts":"44"}},
          {{"name":"Hart sg","min":"38","fg":"3-8","tp":"1-4","ft":"2-2","reb":"7","ast":"4","pts":"9"}},
          {{"name":"Bridges g","min":"42","fg":"4-12","tp":"2-7","ft":"1-2","reb":"4","ast":"3","pts":"11"}},
          {{"name":"McBride","min":"20","fg":"2-5","tp":"1-3","ft":"2-2","reb":"1","ast":"2","pts":"7"}},
          {{"name":"Robinson","min":"14","fg":"1-3","tp":"1-3","ft":"0-0","reb":"2","ast":"0","pts":"3"}},
          {{"name":"Precious","min":"10","fg":"2-3","tp":"0-0","ft":"0-0","reb":"3","ast":"0","pts":"4"}}
        ],"totals":{{"fg":"41-87","tp":"12-35","ft":"24-28","reb":"37","ast":"20","pts":"118"}}}}
      ],
      "notes": "3-pt FG: IND 14-35 (Nembhard 4-7); NYK 12-35 (Brunson 3-8). A: 19,812."
    }},
    {{
      "title": "Thunder 107, Nuggets 99",
      "linescore": {{"away":{{"name":"Oklahoma City","scores":[28,24,30,25],"r":107}},"home":{{"name":"Denver","scores":[22,26,27,24],"r":99}}}},
      "batting": [
        {{"team":"Oklahoma City","players":[
          {{"name":"SGA pg","min":"42","fg":"11-22","tp":"4-9","ft":"5-6","reb":"4","ast":"7","pts":"31"}},
          {{"name":"Holmgren c","min":"36","fg":"7-14","tp":"2-4","ft":"3-4","reb":"9","ast":"2","pts":"19"}},
          {{"name":"Williams pf","min":"30","fg":"5-10","tp":"1-3","ft":"2-2","reb":"8","ast":"1","pts":"13"}},
          {{"name":"Dort sg","min":"34","fg":"4-9","tp":"2-5","ft":"1-2","reb":"3","ast":"2","pts":"11"}},
          {{"name":"Wallace sf","min":"28","fg":"3-7","tp":"1-3","ft":"1-2","reb":"4","ast":"3","pts":"8"}},
          {{"name":"Giddey","min":"22","fg":"3-6","tp":"0-2","ft":"2-2","reb":"5","ast":"5","pts":"8"}},
          {{"name":"Caruso","min":"18","fg":"2-4","tp":"1-3","ft":"2-2","reb":"2","ast":"3","pts":"7"}}
        ],"totals":{{"fg":"35-72","tp":"11-29","ft":"16-20","reb":"35","ast":"23","pts":"107"}}}},
        {{"team":"Denver","players":[
          {{"name":"Jokic c","min":"40","fg":"10-19","tp":"1-3","ft":"6-6","reb":"14","ast":"9","pts":"27"}},
          {{"name":"Murray pg","min":"42","fg":"8-21","tp":"3-9","ft":"3-4","reb":"4","ast":"8","pts":"22"}},
          {{"name":"MPJ sf","min":"34","fg":"6-14","tp":"3-7","ft":"1-2","reb":"5","ast":"2","pts":"16"}},
          {{"name":"Gordon pf","min":"30","fg":"4-9","tp":"1-3","ft":"2-2","reb":"7","ast":"2","pts":"11"}},
          {{"name":"KCP sg","min":"28","fg":"3-8","tp":"2-5","ft":"0-0","reb":"2","ast":"1","pts":"8"}},
          {{"name":"Braun","min":"22","fg":"2-5","tp":"1-3","ft":"3-4","reb":"3","ast":"2","pts":"8"}},
          {{"name":"Strawther","min":"14","fg":"1-4","tp":"1-2","ft":"0-0","reb":"2","ast":"1","pts":"3"}}
        ],"totals":{{"fg":"34-80","tp":"12-32","ft":"15-18","reb":"37","ast":"25","pts":"99"}}}}
      ],
      "notes": "OKC wins series 4-1. SGA 31 pts, 7 ast. Jokic 27-14-9. A: 18,203."
    }}
  ],
  "standings": [
    {{"label":"Eastern Conference — Playoffs","teams":[{{"rank":1,"name":"Cleveland Cavaliers","w":64,"l":18,"pct":".780","gb":"—","note":"vs BOS — Tied 3-3"}},{{"rank":2,"name":"Boston Celtics","w":61,"l":21,"pct":".744","gb":"3","note":"vs CLE — Tied 3-3"}},{{"rank":3,"name":"New York Knicks","w":51,"l":31,"pct":".622","gb":"13","note":"vs IND — Tied 3-3"}},{{"rank":4,"name":"Indiana Pacers","w":46,"l":36,"pct":".561","gb":"18","note":"vs NYK — Tied 3-3"}}]}},
    {{"label":"Western Conference — Playoffs","teams":[{{"rank":1,"name":"Oklahoma City Thunder","w":68,"l":14,"pct":".829","gb":"—","note":"vs DEN — OKC wins 4-1"}},{{"rank":2,"name":"Minnesota Timberwolves","w":53,"l":29,"pct":".646","gb":"15","note":"vs GSW — MIN leads 3-2"}},{{"rank":3,"name":"Denver Nuggets","w":57,"l":25,"pct":".695","gb":"11","note":"Eliminated"}},{{"rank":4,"name":"Golden State Warriors","w":48,"l":34,"pct":".585","gb":"20","note":"vs MIN — Trail 2-3"}}]}}
  ],
  "leaders": {{
    "left": {{"label":"Eastern Conference","cats":[
      {{"cat":"Scoring (Playoffs PPG)","cols":["Player","Team","G","Pts","PPG"],"rows":[["Brunson","New York","14","510","36.4"],["Tatum","Boston","14","441","31.5"],["Mitchell","Cleveland","14","407","29.1"],["Haliburton","Indiana","14","378","27.0"],["Brown","Boston","14","364","26.0"]]}},
      {{"cat":"Rebounds (Playoffs RPG)","cols":["Player","Team","G","Reb","RPG"],"rows":[["Towns","New York","14","154","11.0"],["Allen","Cleveland","14","144","10.3"],["Turner","Indiana","14","138","9.9"],["Porzingis","Boston","12","108","9.0"]]}},
      {{"cat":"Assists (Playoffs APG)","cols":["Player","Team","G","Ast","APG"],"rows":[["Haliburton","Indiana","14","123","8.8"],["Brunson","New York","14","98","7.0"],["Garland","Cleveland","14","96","6.9"],["Holiday","Boston","14","88","6.3"]]}}
    ]}},
    "right": {{"label":"Western Conference","cats":[
      {{"cat":"Scoring (Playoffs PPG)","cols":["Player","Team","G","Pts","PPG"],"rows":[["SGA","Oklahoma City","14","455","32.5"],["Edwards","Minnesota","13","390","30.0"],["Jokic","Denver","13","376","28.9"],["Curry","Golden State","13","342","26.3"],["MPJ","Denver","13","321","24.7"]]}},
      {{"cat":"Rebounds (Playoffs RPG)","cols":["Player","Team","G","Reb","RPG"],"rows":[["Jokic","Denver","13","143","11.0"],["Gobert","Minnesota","13","128","9.8"],["Holmgren","Oklahoma City","14","128","9.1"],["Green","Golden State","13","109","8.4"]]}},
      {{"cat":"Assists (Playoffs APG)","cols":["Player","Team","G","Ast","APG"],"rows":[["Jokic","Denver","13","110","8.5"],["SGA","Oklahoma City","14","96","6.9"],["Murray","Denver","13","88","6.8"],["Paul","Golden State","13","82","6.3"]]}}
    ]}}
  }}
}}
""")

# ── NHL ────────────────────────────────────────────────────────────────────────
def gen_nhl(client, date):
    print("  Writing NHL section...")
    return claude(client, f"""Write the Hockey section for {date} of The Sports Page.

Return this JSON with ALL real current data:
{{
  "story": {{
    "kicker": "NHL PLAYOFFS",
    "headline": "NHL HEADLINE IN ALL CAPS",
    "deck": "Deck under 20 words",
    "byline": "By [Full Name], Hockey Writer",
    "body": "Three paragraphs separated by \\n\\n."
  }},
  "schedule": [
    {{"time":"7:30 PM ET","away":"Boston Bruins","home":"Florida Panthers","note":"Game 6 — FLA leads 3-2"}},
    {{"time":"9:30 PM ET","away":"Vancouver Canucks","home":"Edmonton Oilers","note":"Game 6 — EDM leads 4-1"}}
  ],
  "boxScores": [
    {{
      "title": "Panthers 4, Bruins 3 (2OT)",
      "linescore": {{"away":{{"name":"Boston","scores":[1,1,1,0,0],"r":3}},"home":{{"name":"Florida","scores":[1,2,0,0,1],"r":4}}}},
      "batting": [
        {{"team":"Boston","players":[
          {{"name":"Marchand lw","g":"2","a":"1","pts":"3","pm":"+1","pim":"4","sog":"5"}},
          {{"name":"Pastrnak rw","g":"0","a":"1","pts":"1","pm":"-1","pim":"0","sog":"7"}},
          {{"name":"Bergeron c","g":"1","a":"0","pts":"1","pm":"0","pim":"0","sog":"3"}},
          {{"name":"McAvoy d","g":"0","a":"1","pts":"1","pm":"+1","pim":"2","sog":"4"}},
          {{"name":"DeBrusk lw","g":"0","a":"1","pts":"1","pm":"0","pim":"0","sog":"3"}},
          {{"name":"Coyle c","g":"0","a":"0","pts":"0","pm":"-1","pim":"0","sog":"2"}},
          {{"name":"Haula c","g":"0","a":"0","pts":"0","pm":"0","pim":"6","sog":"1"}},
          {{"name":"Carlo d","g":"0","a":"0","pts":"0","pm":"0","pim":"2","sog":"2"}}
        ],"totals":{{"sog":"33","pim":"16"}}}},
        {{"team":"Florida","players":[
          {{"name":"Reinhart rw","g":"1","a":"1","pts":"2","pm":"+2","pim":"0","sog":"5"}},
          {{"name":"Tkachuk lw","g":"1","a":"1","pts":"2","pm":"+1","pim":"10","sog":"6"}},
          {{"name":"Barkov c","g":"1","a":"0","pts":"1","pm":"+1","pim":"0","sog":"4"}},
          {{"name":"Verhaeghe rw","g":"1","a":"0","pts":"1","pm":"0","pim":"0","sog":"3"}},
          {{"name":"Forsling d","g":"0","a":"1","pts":"1","pm":"+2","pim":"2","sog":"3"}},
          {{"name":"Kulikov d","g":"0","a":"1","pts":"1","pm":"+1","pim":"0","sog":"2"}},
          {{"name":"Lundell c","g":"0","a":"1","pts":"1","pm":"0","pim":"0","sog":"2"}},
          {{"name":"Bennett c","g":"0","a":"0","pts":"0","pm":"0","pim":"0","sog":"2"}}
        ],"totals":{{"sog":"47","pim":"12"}}}}
      ],
      "notes": "BOS: Swayman (L) 43 svs/47 shots. FLA: Bobrovsky (W) 44 svs/47 shots. PP: BOS 0/3, FLA 1/4. A: 19,250."
    }},
    {{
      "title": "Oilers 3, Canucks 2 (OT)",
      "linescore": {{"away":{{"name":"Edmonton","scores":[1,0,1,1],"r":3}},"home":{{"name":"Vancouver","scores":[1,1,0,0],"r":2}}}},
      "batting": [
        {{"team":"Edmonton","players":[
          {{"name":"McDavid c","g":"1","a":"1","pts":"2","pm":"+2","pim":"2","sog":"7"}},
          {{"name":"Draisaitl lw","g":"1","a":"2","pts":"3","pm":"+1","pim":"0","sog":"5"}},
          {{"name":"Hyman lw","g":"1","a":"0","pts":"1","pm":"+1","pim":"0","sog":"4"}},
          {{"name":"Nurse d","g":"0","a":"1","pts":"1","pm":"+1","pim":"2","sog":"3"}},
          {{"name":"Bouchard d","g":"0","a":"1","pts":"1","pm":"0","pim":"0","sog":"3"}},
          {{"name":"Nuge c","g":"0","a":"0","pts":"0","pm":"0","pim":"0","sog":"2"}},
          {{"name":"Foegele lw","g":"0","a":"0","pts":"0","pm":"0","pim":"0","sog":"2"}}
        ],"totals":{{"sog":"30","pim":"4"}}}},
        {{"team":"Vancouver","players":[
          {{"name":"Pettersson c","g":"1","a":"0","pts":"1","pm":"-1","pim":"0","sog":"6"}},
          {{"name":"JTMiller lw","g":"0","a":"1","pts":"1","pm":"-1","pim":"2","sog":"4"}},
          {{"name":"Boeser rw","g":"1","a":"0","pts":"1","pm":"0","pim":"0","sog":"5"}},
          {{"name":"Q.Hughes d","g":"0","a":"1","pts":"1","pm":"-1","pim":"0","sog":"4"}},
          {{"name":"Garland rw","g":"0","a":"0","pts":"0","pm":"0","pim":"0","sog":"3"}},
          {{"name":"Schenn c","g":"0","a":"0","pts":"0","pm":"-1","pim":"4","sog":"2"}},
          {{"name":"Myers d","g":"0","a":"0","pts":"0","pm":"-1","pim":"0","sog":"2"}}
        ],"totals":{{"sog":"28","pim":"8"}}}}
      ],
      "notes": "EDM wins series 4-1. McDavid OT winner. Draisaitl 1G 2A. Demko 27 svs."
    }}
  ],
  "standings": [
    {{"label":"Eastern Conference","teams":[{{"rank":1,"name":"Florida Panthers","w":52,"l":20,"pct":".715","gb":"—","l10":"7-3","strk":"W1","home":"28-9","away":"24-11"}},{{"rank":2,"name":"Boston Bruins","w":51,"l":21,"pct":".708","gb":"1","l10":"6-4","strk":"L1","home":"27-10","away":"24-11"}},{{"rank":3,"name":"Carolina Hurricanes","w":49,"l":23,"pct":".681","gb":"3","l10":"7-3","strk":"W4","home":"27-11","away":"22-12"}},{{"rank":4,"name":"New York Rangers","w":47,"l":25,"pct":".653","gb":"5","l10":"5-5","strk":"W1","home":"25-12","away":"22-13"}},{{"rank":5,"name":"Washington Capitals","w":44,"l":28,"pct":".611","gb":"8","l10":"6-4","strk":"L1","home":"23-13","away":"21-15"}}]}},
    {{"label":"Western Conference","teams":[{{"rank":1,"name":"Edmonton Oilers","w":54,"l":18,"pct":".750","gb":"—","l10":"8-2","strk":"W3","home":"29-8","away":"25-10"}},{{"rank":2,"name":"Vancouver Canucks","w":50,"l":22,"pct":".694","gb":"4","l10":"6-4","strk":"L1","home":"26-10","away":"24-12"}},{{"rank":3,"name":"Dallas Stars","w":48,"l":24,"pct":".667","gb":"6","l10":"5-5","strk":"L1","home":"25-11","away":"23-13"}},{{"rank":4,"name":"Winnipeg Jets","w":44,"l":28,"pct":".611","gb":"10","l10":"5-5","strk":"W1","home":"24-12","away":"20-16"}},{{"rank":5,"name":"Colorado Avalanche","w":45,"l":27,"pct":".625","gb":"9","l10":"6-4","strk":"W2","home":"24-13","away":"21-14"}}]}}
  ],
  "leaders": {{
    "left": {{"label":"Eastern Conference","cats":[
      {{"cat":"Goals (Season)","cols":["Player","Team","G"],"rows":[["Ovechkin","Washington","52"],["Tkachuk","Florida","44"],["Reinhart","Florida","42"],["Aho","Carolina","40"],["Marchand","Boston","30"]]}},
      {{"cat":"Points (Season)","cols":["Player","Team","G","A","Pts"],"rows":[["Marchand","Boston","30","58","88"],["Tkachuk","Florida","44","43","87"],["Reinhart","Florida","42","37","79"],["Aho","Carolina","40","38","78"]]}},
      {{"cat":"Goals (Playoffs)","cols":["Player","Team","G"],"rows":[["Reinhart","Florida","9"],["Tkachuk","Florida","8"],["Aho","Carolina","7"],["Marchand","Boston","6"]]}},
      {{"cat":"Goaltending (GAA)","cols":["Goalie","Team","GP","GAA","SV%"],"rows":[["Bobrovsky","Florida","62","2.31",".921"],["Swayman","Boston","60","2.44",".918"],["Andersen","Carolina","58","2.51",".916"],["Shesterkin","NY Rangers","61","2.55",".914"]]}}
    ]}},
    "right": {{"label":"Western Conference","cats":[
      {{"cat":"Goals (Season)","cols":["Player","Team","G"],"rows":[["Draisaitl","Edmonton","48"],["McDavid","Edmonton","38"],["Kaprizov","Minnesota","39"],["Rantanen","Colorado","36"],["Scheifele","Winnipeg","32"]]}},
      {{"cat":"Points (Season)","cols":["Player","Team","G","A","Pts"],"rows":[["McDavid","Edmonton","38","67","105"],["Draisaitl","Edmonton","48","54","102"],["Rantanen","Colorado","36","58","94"],["Hertl","Vegas","28","56","84"]]}},
      {{"cat":"Goals (Playoffs)","cols":["Player","Team","G"],"rows":[["Draisaitl","Edmonton","8"],["McDavid","Edmonton","7"],["Hyman","Edmonton","5"],["Rantanen","Colorado","5"]]}},
      {{"cat":"Goaltending (GAA)","cols":["Goalie","Team","GP","GAA","SV%"],"rows":[["Hellebuyck","Winnipeg","72","2.29",".923"],["Demko","Vancouver","59","2.62",".912"],["Skinner","Edmonton","62","2.71",".912"],["Oettinger","Dallas","64","2.77",".910"]]}}
    ]}}
  }}
}}
""")

# ── NFL ────────────────────────────────────────────────────────────────────────
def gen_nfl(client, date):
    print("  Writing NFL section...")
    return claude(client, f"""Write the Football section for {date} of The Sports Page.

Return this JSON with ALL real current data:
{{
  "story": {{
    "kicker": "NFL OFFSEASON",
    "headline": "NFL HEADLINE IN ALL CAPS",
    "deck": "Deck under 20 words",
    "byline": "By [Full Name], NFL Writer",
    "body": "Three paragraphs separated by \\n\\n."
  }},
  "schedule": [
    {{"time":"May 22","away":"Deadline","home":"Fifth-Year Options","note":"Teams must exercise options for 2022 first-round picks"}},
    {{"time":"June 1","away":"Cutdown","home":"Roster Moves","note":"Post-June 1 designations take effect"}},
    {{"time":"July 24","away":"Training","home":"Camps Open","note":"Veteran reporting date for all 32 teams"}}
  ],
  "boxScores": [
    {{
      "title": "Super Bowl LIX: Eagles 38, 49ers 10",
      "linescore": {{"away":{{"name":"Philadelphia","scores":[10,14,7,7],"r":38}},"home":{{"name":"San Francisco","scores":[3,0,7,0],"r":10}}}},
      "batting": [],
      "nflStats": [
        {{"label":"Passing","cols":["Player","Team","Att","Cmp","Yds","TD","Int","Rating"],"rows":[["Hurts","PHI","31","22","221","2","0","112.3"],["Purdy","SF","27","16","142","0","2","48.1"]]}},
        {{"label":"Rushing","cols":["Player","Team","Car","Yds","Avg","TD"],"rows":[["Hurts","PHI","12","72","6.0","1"],["Henry","PHI","22","88","4.0","1"],["McCaffrey","SF","8","31","3.9","0"]]}},
        {{"label":"Receiving","cols":["Player","Team","Rec","Tgt","Yds","Avg","TD"],"rows":[["AJBrown","PHI","6","8","82","13.7","1"],["DeVonta Smith","PHI","5","7","62","12.4","1"],["Aiyuk","SF","6","9","58","9.7","0"]]}}
      ],
      "notes": "MVP: Jalen Hurts. Eagles win first championship since Super Bowl LII."
    }},
    {{
      "title": "AFC Championship: Ravens 27, Chiefs 24",
      "linescore": {{"away":{{"name":"Baltimore","scores":[3,10,7,7],"r":27}},"home":{{"name":"Kansas City","scores":[7,10,0,7],"r":24}}}},
      "batting": [],
      "nflStats": [
        {{"label":"Passing","cols":["Player","Team","Att","Cmp","Yds","TD","Int","Rating"],"rows":[["Jackson","BAL","38","28","312","2","1","94.1"],["Mahomes","KC","47","29","281","1","2","69.8"]]}},
        {{"label":"Rushing","cols":["Player","Team","Car","Yds","Avg","TD"],"rows":[["Henry","BAL","21","98","4.7","1"],["Jackson","BAL","7","44","6.3","0"]]}},
        {{"label":"Receiving","cols":["Player","Team","Rec","Tgt","Yds","Avg","TD"],"rows":[["Andrews","BAL","8","11","92","11.5","1"],["Kelce","KC","11","16","108","9.8","1"]]}}
      ],
      "notes": "Tucker 47-yd FG with 0:08 remaining. Jackson 28/38, 2 TD."
    }}
  ],
  "standings": [
    {{"label":"AFC East","teams":[{{"rank":1,"name":"Buffalo Bills","w":13,"l":4,"pct":".765","gb":"—","note":"Lost AFC Divisional"}},{{"rank":2,"name":"Miami Dolphins","w":9,"l":8,"pct":".529","gb":"4","note":"Missed playoffs"}},{{"rank":3,"name":"NY Jets","w":7,"l":10,"pct":".412","gb":"6","note":"Missed playoffs"}},{{"rank":4,"name":"New England Patriots","w":4,"l":13,"pct":".235","gb":"9","note":"Missed playoffs"}}]}},
    {{"label":"AFC North","teams":[{{"rank":1,"name":"Baltimore Ravens","w":13,"l":4,"pct":".765","gb":"—","note":"Lost AFC Championship"}},{{"rank":2,"name":"Pittsburgh Steelers","w":10,"l":7,"pct":".588","gb":"3","note":"Lost Wild Card"}},{{"rank":3,"name":"Cleveland Browns","w":8,"l":9,"pct":".471","gb":"5","note":"Missed playoffs"}},{{"rank":4,"name":"Cincinnati Bengals","w":7,"l":10,"pct":".412","gb":"6","note":"Missed playoffs"}}]}},
    {{"label":"AFC South","teams":[{{"rank":1,"name":"Houston Texans","w":10,"l":7,"pct":".588","gb":"—","note":"Lost AFC Divisional"}},{{"rank":2,"name":"Indianapolis Colts","w":9,"l":8,"pct":".529","gb":"1","note":"Missed playoffs"}},{{"rank":3,"name":"Jacksonville Jaguars","w":4,"l":13,"pct":".235","gb":"6","note":"Missed playoffs"}},{{"rank":4,"name":"Tennessee Titans","w":3,"l":14,"pct":".176","gb":"7","note":"Missed playoffs"}}]}},
    {{"label":"AFC West","teams":[{{"rank":1,"name":"Kansas City Chiefs","w":15,"l":2,"pct":".882","gb":"—","note":"Lost AFC Championship"}},{{"rank":2,"name":"Denver Broncos","w":10,"l":7,"pct":".588","gb":"5","note":"Lost Wild Card"}},{{"rank":3,"name":"LA Chargers","w":8,"l":9,"pct":".471","gb":"7","note":"Missed playoffs"}},{{"rank":4,"name":"Las Vegas Raiders","w":4,"l":13,"pct":".235","gb":"11","note":"Missed playoffs"}}]}},
    {{"label":"NFC East","teams":[{{"rank":1,"name":"Philadelphia Eagles","w":14,"l":3,"pct":".824","gb":"—","note":"Super Bowl Champions"}},{{"rank":2,"name":"Dallas Cowboys","w":10,"l":7,"pct":".588","gb":"4","note":"Missed playoffs"}},{{"rank":3,"name":"Washington Commanders","w":9,"l":8,"pct":".529","gb":"5","note":"Lost Wild Card"}},{{"rank":4,"name":"NY Giants","w":4,"l":13,"pct":".235","gb":"10","note":"Missed playoffs"}}]}},
    {{"label":"NFC North","teams":[{{"rank":1,"name":"Detroit Lions","w":15,"l":2,"pct":".882","gb":"—","note":"Lost NFC Championship"}},{{"rank":2,"name":"Minnesota Vikings","w":14,"l":3,"pct":".824","gb":"1","note":"Lost NFC Divisional"}},{{"rank":3,"name":"Green Bay Packers","w":11,"l":6,"pct":".647","gb":"4","note":"Lost NFC Divisional"}},{{"rank":4,"name":"Chicago Bears","w":6,"l":11,"pct":".353","gb":"9","note":"Missed playoffs"}}]}},
    {{"label":"NFC South","teams":[{{"rank":1,"name":"Tampa Bay Buccaneers","w":10,"l":7,"pct":".588","gb":"—","note":"Lost Wild Card"}},{{"rank":2,"name":"Atlanta Falcons","w":9,"l":8,"pct":".529","gb":"1","note":"Missed playoffs"}},{{"rank":3,"name":"New Orleans Saints","w":5,"l":12,"pct":".294","gb":"5","note":"Missed playoffs"}},{{"rank":4,"name":"Carolina Panthers","w":3,"l":14,"pct":".176","gb":"7","note":"Missed playoffs"}}]}},
    {{"label":"NFC West","teams":[{{"rank":1,"name":"San Francisco 49ers","w":13,"l":4,"pct":".765","gb":"—","note":"Lost Super Bowl"}},{{"rank":2,"name":"LA Rams","w":10,"l":7,"pct":".588","gb":"3","note":"Lost NFC Divisional"}},{{"rank":3,"name":"Seattle Seahawks","w":10,"l":7,"pct":".588","gb":"3","note":"Lost Wild Card"}},{{"rank":4,"name":"Arizona Cardinals","w":8,"l":9,"pct":".471","gb":"5","note":"Missed playoffs"}}]}}
  ],
  "leaders": {{
    "left": {{"label":"AFC","cats":[
      {{"cat":"Passing Yards","cols":["Player","Team","Att","Cmp","Yds","TD","Int"],"rows":[["Allen, Buffalo","BUF","581","387","4,306","34","12"],["Jackson, Baltimore","BAL","468","302","3,984","37","11"],["Mahomes, Kansas City","KC","542","348","4,021","32","11"]]}},
      {{"cat":"Rushing Yards","cols":["Player","Team","Car","Yds","Avg","TD"],"rows":[["Henry, Baltimore","BAL","287","1,459","5.1","17"],["Chubb, Cleveland","CLE","231","1,101","4.8","9"],["Cook, Buffalo","BUF","201","822","4.1","7"]]}},
      {{"cat":"Receiving Yards","cols":["Player","Team","Rec","Yds","Avg","TD"],"rows":[["Hill, Miami","MIA","108","1,799","16.7","13"],["Diggs, Buffalo","BUF","96","1,291","13.4","9"],["Andrews, Baltimore","BAL","91","1,187","13.0","8"]]}},
      {{"cat":"Sacks","cols":["Player","Team","Sacks"],"rows":[["Watt, Pittsburgh","PIT","13.0"],["Burns, Buffalo","BUF","11.5"],["Jefferson, Houston","HOU","10.5"]]}}
    ]}},
    "right": {{"label":"NFC","cats":[
      {{"cat":"Passing Yards","cols":["Player","Team","Att","Cmp","Yds","TD","Int"],"rows":[["Hurts, Philadelphia","PHI","512","341","4,021","36","7"],["Goff, Detroit","DET","563","376","4,010","30","9"],["Stafford, LA Rams","LAR","541","357","3,992","28","11"]]}},
      {{"cat":"Rushing Yards","cols":["Player","Team","Car","Yds","Avg","TD"],"rows":[["McCaffrey, San Francisco","SF","298","1,411","4.7","14"],["Gibbs, Detroit","DET","241","1,088","4.5","11"],["Hurts, Philadelphia","PHI","171","922","5.4","8"]]}},
      {{"cat":"Receiving Yards","cols":["Player","Team","Rec","Yds","Avg","TD"],"rows":[["Smith, Philadelphia","PHI","97","1,401","14.4","11"],["Jefferson, Minnesota","MIN","91","1,377","15.1","10"],["Nacua, LA Rams","LAR","105","1,314","12.5","8"]]}},
      {{"cat":"Sacks","cols":["Player","Team","Sacks"],"rows":[["Bosa, San Francisco","SF","17.5"],["Parsons, Dallas","DAL","14.0"],["Hutchinson, Detroit","DET","13.5"]]}}
    ]}}
  }}
}}
""")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def run_pipeline():
    print("=== The Sports Page Daily Pipeline ===")
    now = datetime.now(timezone.utc)
    print(f"Running at {now.strftime('%Y-%m-%d %H:%M UTC')}\n")

    client   = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    date_str = now.strftime("%A, %B %-d, %Y")

    front = gen_front(client, date_str)
    mlb   = gen_mlb(client, date_str)
    nba   = gen_nba(client, date_str)
    nhl   = gen_nhl(client, date_str)
    nfl   = gen_nfl(client, date_str)

    output = {
        "date":    date_str,
        "edition": f"Vol. CXLVIII · No. {now.timetuple().tm_yday + 133}",
        "weather": "Check your local forecast",
        "front":   front,
        "mlb":     mlb,
        "nba":     nba,
        "nhl":     nhl,
        "nfl":     nfl,
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/data.json", "w") as f:
        json.dump(output, f, indent=2)

    size = len(json.dumps(output))
    print(f"\n✓ docs/data.json written ({size:,} bytes)")
    print("✓ Pipeline complete.")

if __name__ == "__main__":
    run_pipeline()
