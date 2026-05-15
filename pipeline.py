=== The Sports Page Daily Pipeline ===
Running at 2026-05-15 18:33 UTC

Building sections...
  MLB: fetching data...
    11 games yesterday, 15 today
    MLB Standings: 6 records from API
      div id=201 name=''
        → AL East: 5 teams OK
      div id=202 name=''
        → AL Central: 5 teams OK
      div id=200 name=''
        → AL West: 5 teams OK
      div id=204 name=''
        → NL East: 5 teams OK
      div id=205 name=''
        → NL Central: 5 teams OK
      div id=203 name=''
        → NL West: 5 teams OK
    MLB Standings final: 6 divisions
    Fetching MLB leaders...
    Writing MLB story...
  NBA: fetching data...
    NBA API error: HTTPSConnectionPool(host='stats.nba.com', port=443): Read timed out. (read timeout=60)
    nba_api failed, using ESPN fallback for NBA scores
    NBA API error: HTTPSConnectionPool(host='stats.nba.com', port=443): Read timed out. (read timeout=60)
    NBA API error: HTTPSConnectionPool(host='stats.nba.com', port=443): Read timed out. (read timeout=60)
    Writing NBA story...
  NHL: fetching data...
    NHL Standings: 0 teams
    Writing NHL story...
  NFL: fetching data from ESPN...
    API error (leaders): 404 Client Error: Not Found for url: https://site.api.espn.com/apis/site/v2/sports/football/nfl/leaders?season=2025&seasontype=2
  Writing front page...

✓ docs/data.json written (70,023 bytes)
✓ Pipeline complete.
