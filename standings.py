import os, sys, subprocess, json, time
from pprint import pprint
import requests

"""
Golly Standings Table with Elimination Number

Elim = G + 1 - W_A - L_B

GB = ((W_A - L_A) - (W_B - L_B))/2
"""

def main():
    cup = 'ii'
    dps = 49

    season0, day0 = get_current_season_day(cup, dps)

    print_division_standings_w_elim(season0, day0, cup, dps)
    print_legend()


def print_legend():
    print("")
    print("Legend:")
    print("    y-       Clinched Division")
    print("    w-       Wild Card Current Holder")
    print("    x-       Eliminated")


def get_current_season_day(cup, dps):
    api_url = f'https://cloud.{cup}.golly.life'

    resp = requests.get(f'{api_url}/mode').json()

    mode = resp['mode']
    season0 = resp['season']

    if mode < 10:
        season0 -= 1
        day0 = dps

    elif mode < 20:
        resp = requests.get(f'{api_url}/season').json()
        day0 = resp[-1][0]['day']

    else:
        day0 = dps-1

    return season0, day0

def get_base_dir(cup):
    try:
        BASE_DIR = os.environ['GOLLYX_BASE_DATA_DIR']
    except KeyError:
        raise Exception("Error: no GOLLYX_DATA_DIR env var defined. Try running 'source environment' first.")
    return os.path.join(BASE_DIR, f'gollyx-{cup}-data')

def fetch_season_data(which_season0, cup):
    cup = cup.lower()
    seas_file = os.path.join(get_base_dir(cup), f'season{which_season0}', 'season.json')
    if not os.path.exists(seas_file):
        raise Exception(f"Error: season {which_season0} not valid: {seas_file} does not exist")
    with open(seas_file, 'r') as f:
        season0_seas = json.load(f)
    return season0_seas

def fetch_teams_data(which_season0, cup):
    cup = cup.lower()
    teams_file = os.path.join(get_base_dir(cup), f'season{which_season0}', 'teams.json')
    if not os.path.exists(teams_file):
        raise Exception(f"Error: season {which_season0} not valid: {teams_file} does not exist")
    with open(teams_file, 'r') as f:
        season0_teams = json.load(f)
    return season0_teams

def get_leagues(team_dat):
    leagues = list(set([t['league'] for t in team_dat]))
    return sorted(leagues)

def get_leagues_divisions(team_dat):
    leagues_divs = list(set([(t['league'], t['division']) for t in team_dat]))
    leagues_divs.sort(key=lambda x: (x[0], x[1]))
    return leagues_divs

def get_league_division_team(team_abbr, team_dat):
    for t in team_dat:
        if t['teamAbbr'] == team_abbr:
            return (t['league'], t['division'])
    return None

def team_name_to_abbr(team_name, team_dat):
    for t in team_dat:
        if t['teamName'].lower()==team_name.lower():
            return t['teamAbbr']
    return None

def get_division_standings(season0, day0, cup):
    """
    Returns a dictionary
    
    keys are tuples:
    (league name, division name)
    
    values are lists of tuples:
    (team abbr, team wins, team losses, team points scored)
    
    {
        ('X League', 'Y Division'):    [ ('EA',  10,  7,  2345),
                                         ('SS',  12,  5,  1234),
                                         ...
                                       ]
    }
    """
    seas_dat = fetch_season_data(season0, cup)
    teams_dat = fetch_teams_data(season0, cup)
    
    team_w = {}
    team_l = {}
    team_s = {}
    
    for team in teams_dat:
        ta = team['teamAbbr']
        team_w[ta] = 0
        team_l[ta] = 0
        team_s[ta] = 0
    
    # Accumulate runs up to and including day0
    for i in range(day0+1):
        today = seas_dat[i]
        for game in today:
            t1a = game['team1Abbr']
            t2a = game['team2Abbr']
            
            t1s = game['team1Score']
            t2s = game['team2Score']
            
            team_s[t1a] += t1s
            team_s[t2a] += t2s
    
    # Accumulate W/L including day0 outcome
    last_day = seas_dat[day0]
    for game in last_day:
        t1a = game['team1Abbr']
        t2a = game['team2Abbr']

        t1s = game['team1Score']
        t2s = game['team2Score']
            
        t1w, t1l = game['team1WinLoss']
        t2w, t2l = game['team2WinLoss']
        if game['team1Score'] > game['team2Score']:
            t1w += 1
            t2l += 1
        else:
            t2w += 1
            t1l += 1
        
        team_w[t1a] = t1w
        team_l[t1a] = t1l
        
        team_w[t2a] = t2w
        team_l[t2a] = t2l
    
    division_standings = {}
    
    lea_div = get_leagues_divisions(teams_dat)
    for ld in lea_div:
        division_standings[ld] = []
    
    for team in teams_dat:
        ta = team['teamAbbr']
        tl = team['league']
        td = team['division']
        k = (tl, td)
        v = (ta, team_w[ta], team_l[ta], team_s[ta])
        division_standings[k].append(v)
    
    for k in division_standings.keys():
        division_standings[k].sort(key = lambda x: (x[1], x[3]), reverse = True)
    
    return division_standings

def print_division_standings_w_elim(season0, day0, cup, dps):
    
    print("Standings:")
    print(f"Season {season0+1}, Day {day0+1}")
    print("")
    
    standings = get_division_standings(season0, day0, cup)
    for league, division in standings.keys():
        
        key = (league, division)
        data = standings[key]
        
        print(f"{league}, {division}:")
        print("===========================================")
        print("")
        print(f"  Team  |  W  |  L  | Pct   | GB | Left | Elim # | WC Elim # ")
        print( "-------------------------------------------------------------")
        
        for i, row in enumerate(data):
            prefix = "  "

            gb = ""
            elim = ""
            wc_elim = ""
            
            if i==0:
                # First row is first place team (incl. points tiebreaker)
                
                # Determine magic # for first place team
                first_wins = row[1]
                second_losses = data[1][2]
                magic = dps + 1 - first_wins - second_losses
                
                # If the first place team's magic # < 0, they clinched
                if magic < 0 or day0 == dps-1:
                    prefix = "y-"
            
            else:
                # Determine elimination for not first place teams
                first_wins = data[0][1]
                our_losses = row[2]
                elim = dps + 1 - first_wins - our_losses
                
                # # Naive approach:
                # # Elimination number of 0 or less means you have no hope
                # if elim <= 0:
                #     prefix = "x-"
                
                # FALSE. In order for all hope to be lost,
                # elimination number <= 0,
                # and wild card elimination number <= 0
                
                # Wild cards:
                # Need to combine and sort not first place teams from both divisions
                combined = []
                for lea_, div_ in standings.keys():
                    if lea_==league:
                        for j, item in enumerate(standings[(lea_,div_)]):
                            if j>0:
                                combined.append(item)
                
                combined.sort(key = lambda x: (x[1], x[3]), reverse = True)
                namecol = 0
                if row[namecol]==combined[0][namecol] or row[0]==combined[1][namecol]:
                    prefix = "w-"
                else:
                    # Determine WC elim # for not wc teams
                    wc_elim = dps + 1 - combined[1][1] - row[2]

                    if elim <= 0 and wc_elim <= 0:
                        # All hope is lost
                        prefix = "x-"

                # Games behind
                first_wins = data[0][1]
                first_losses = data[0][2]
                our_wins = row[1]
                our_losses = row[2]
                gb = ((first_wins-first_losses)-(our_wins-our_losses))//2

                if gb > 0:
                    gb = str(gb)
                else:
                    gb = "-"

                elim = str(elim)
                wc_elim = str(wc_elim)
            
            print(f"{prefix}{row[0]:5} | {row[1]:>3} | {row[2]:>3} | {row[1]/(row[1]+row[2]):>3.3f} | {gb:>2} | {dps-day0-1:>4} | {elim:>6} | {wc_elim:>9} ")
            
        print("\n")




if __name__=="__main__":
    main()
