from selenium import webdriver
from selenium.common.exceptions import *
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager 
from selenium.webdriver.chrome.service import Service as ChromeService 
from datetime import datetime
from unidecode import unidecode
from threading import Thread
import requests
from time import sleep
import json
from Leagues import leagues


TRIGGER = {
    "Rain": {"id" : 0, "odd" : "under"},
    "Better Rain": {"id" : 1, "odd" : "under"},
    "Drought": {"id" : 2, "odd" : "over"},
    "Better Drought": {"id" : 3, "odd" : "over"}
}

FILTER_MARKET = {
    1 : {"filter" : "Quarters", "market" : "1st Quarter - Total"},
    2 : {"filter" : "Half"    , "market" : "1st Half - Asian Total"},
    3 : {"filter" : "Quarters", "market" : "3rd Quarter - Total"},
    4 : {"filter" : "Quarters", "market" : "4th Quarter - Total"}
}

LIVE_SCRAPING_URLS = [
    "https://stake.ac/sports/live/basketball",
    "https://stake.ac/sports/basketball/usa/ncaa-regular"
]

LIMIT_TIME_QUARTER_TOTAL = 240
LIMIT_TIME_QUARTER_ML = 120
LIMIT_PING = 2
EMPTY = '--@--'

QUARTER_TOTAL = "QuarterTotal"
HALFTIME = "Halftime"
QUARTER_ML = "QuarterML"

is_scrapping_now = False
Odds_QuarterML = {}

options = Options()
options.add_experimental_option("debuggerAddress", "127.0.0.1:9015")
options.add_argument("user-agent=Chrome/120.0.6099.200")
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

def log(content):
    with open("schedule.txt", "+a") as file:
        file.write(content + "\n")

def scrap_odds(url, filter_name, market_title):
    global is_scrapping_now
    is_scrapping_now = True
    result = {"over" : EMPTY, "under" : EMPTY, "home" : 0.0, "away" : 0.0}

    driver.get(url)
    is_ok = False
    timeout = 0.0
    while not is_ok:
        menus = driver.find_elements(By.CLASS_NAME, 'variant-tabmenu')
        for menu in menus:
            if menu.text == filter_name:
                driver.execute_script("arguments[0].click();", menu)
                is_ok = True
                break
        if menus:
            timeout += 0.1
            if timeout > 5:
                print(f'{datetime.now().strftime("%H:%M:%S")} {" ".ljust(10)} filter timeout - {filter_name}\n')
                break
        sleep(0.1)
    timeout = 0.0
    while is_ok:
        markets = driver.find_elements(By.CLASS_NAME, 'secondary-accordion')
        for market in markets:
            try:
                title = market.find_element(By.CLASS_NAME, 'weight-semibold').text
                odds = market.find_elements(By.CLASS_NAME, 'outcome')
                if title == market_title:
                    if "Quarter - 1x2" in market_title:
                        result["home"] = odds[0].text.split("\n")[-1]
                        result["away"] = odds[2].text.split("\n")[-1]
                    else:
                        result["over"] = odds[0].text.replace("\n", "@")
                        result["under"] = odds[1].text.replace("\n", "@")
                    break
            except:
                pass
        if markets:
            timeout += 0.1
            if timeout > 5:
                print(f'{datetime.now().strftime("%H:%M:%S")} {" ".ljust(10)} market timeout - {market_title}\n')
                break
        if ("Quarter - 1x2" in market_title and result["home"] != 0.0) or ("Quarter - 1x2" not in market_title and result["over"] != EMPTY):
            break
        sleep(0.1)
    is_scrapping_now = False
    driver.get("https://stake.ac/sports/live/basketball")

    return result

def scrap_odds_for_QuarterML():
    global Odds_QuarterML
    while True:
        if driver.current_url == "https://stake.ac/sports/live/basketball":
            odds_to_name_map = {}
            match_elements = driver.find_elements(By.CLASS_NAME, 'fixture-preview')
            for match_element in match_elements:
                try:
                    teams = match_element.find_element(By.CLASS_NAME, 'teams').text.split('\n')
                    home_team, away_team = teams[0], teams[1]

                    live_odds = match_element.find_elements(By.CLASS_NAME, 'weight-bold')
                    underdog = "None"
                    try:
                        odds_home, odds_away = float(live_odds[0].text), float(live_odds[1].text)
                        if odds_home > odds_away:
                            underdog = "home"
                        if odds_home < odds_away:
                            underdog = "away"
                    except:
                        pass
                    odds_to_name_map[f'{home_team} vs {away_team}'] = underdog
                except:
                    pass
            if odds_to_name_map:
                Odds_QuarterML = odds_to_name_map
        sleep(0.1)

def fetch_live(schedules, gameIds):
    print('-'*50, 'fetching live'.center(50), '-'*50, '\n')
    live_matchs = {}

    timecount = 0
    driver.get("https://stake.ac/sports/live/basketball")
    while gameIds or schedules[HALFTIME]:
        removed_ids = []
        for id in gameIds:
            response = requests.get(f'https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{id}.json')        
            if response.status_code == 200:
                game = response.json().get('game')
                gameTime = 1200
                if game["gameClock"] != "": 
                    gameClock = game["gameClock"].replace("PT", "").split(".")[0]
                    gameTime = int(gameClock.split("M")[0]) * 60 + int(gameClock.split("M")[1])
                q_no = game["period"]
                scores_api = {"home" : [0, 0, 0, 0, 0], "away" : [0, 0, 0, 0, 0]}
                for item in game["homeTeam"]["periods"]:
                    scores_api["home"][item["period"] - 1] = item["score"]
                for item in game["awayTeam"]["periods"]:
                    scores_api["away"][item["period"] - 1] = item["score"]

                if id in schedules[QUARTER_ML]:
                    match = schedules[QUARTER_ML][id]
                    q_no = max(q_no, match["q_no"])
                    schedules[QUARTER_ML][id]["q_no"] = q_no
                    match_league = match["league"]
                    scrap_url = match["url"]
                    print_league_teams = f'{match_league["short_name"].ljust(10)} [{match["home"].center(30)}] vs [{match["away"].center(30)}]'

                    swap = match["swap"]
                    scores = scores_api
                    if swap:
                        scores["home"] = scores_api["away"]
                        scores["away"] = scores_api["home"]
                    curr_quarter_home_score = scores["home"][q_no - 1]
                    curr_quarter_away_score = scores["away"][q_no - 1]

                    diff_scores = curr_quarter_home_score - curr_quarter_away_score
                    q_ml_match_data = match[q_no]
                    # updated_remain = match_league["time"] * 60 - gameTime
                    updated_remain = gameTime
                    if q_no <= match_league["round"]:
                        if updated_remain >= LIMIT_TIME_QUARTER_ML:
                            if q_ml_match_data["status"]:
                                if q_ml_match_data["ping"] == 0:
                                    criteria = match_league[QUARTER_ML]["score"]
                                    underdog = q_ml_match_data["underdog"]
                                    if (underdog == "home" and diff_scores >= criteria) or (underdog == "away" and -diff_scores >= criteria):
                                        quarters = ["1st", "2nd", "3rd", "4th"]
                                        scrap_result = scrap_odds(scrap_url, "Quarters", f"{quarters[q_no - 1]} Quarter - 1x2")
                                        message = {
                                            "league" : match_league["name"],
                                            "short_name" : match_league["short_name"],
                                            "time" : match_league["time"],
                                            "q_no" : q_no,
                                            "remain" : updated_remain,
                                            "home" : match["home"],
                                            "away" : match["away"],
                                            "url" : scrap_url,
                                            "odds" : scrap_result[underdog],
                                            "underdog" : match[underdog],
                                            "scores" : f"{sum(scores['home'])}:{sum(scores['away'])}",
                                            "algorithm" : QUARTER_ML
                                            }
                                        with open('json files/message_to_be_pinged.json', 'w') as file:
                                            json.dump(message, file)
                                        schedules[QUARTER_ML][id][q_no]["ping"] = 1
                                        if q_no == match_league["round"]:
                                            schedules[QUARTER_ML][id]["q_no"] = q_no + 1
                            else:
                                key = f'{match["home"]} vs {match["away"]}'
                                if key in Odds_QuarterML: # match_league["time"] * 60
                                    schedules[QUARTER_ML][id][q_no]["status"] = True
                                    underdog = Odds_QuarterML[key]
                                    if underdog == "None":                                    
                                        if sum(scores["home"]) > sum(scores["away"]):
                                            underdog = "away"
                                        elif sum(scores["home"]) < sum(scores["away"]):
                                            underdog = "home"
                                        else:
                                            pass
                                    schedules[QUARTER_ML][id][q_no]["underdog"] = underdog
                                key = f'{match["away"]} vs {match["home"]}'
                                if key in Odds_QuarterML: # match_league["time"] * 60
                                    schedules[QUARTER_ML][id][q_no]["status"] = True
                                    underdog = Odds_QuarterML[key]
                                    if underdog == "None":                                    
                                        if sum(scores["home"]) > sum(scores["away"]):
                                            underdog = "away"
                                        elif sum(scores["home"]) < sum(scores["away"]):
                                            underdog = "home"
                                        else:
                                            pass
                                    elif underdog == "home":
                                        underdog = "away"
                                    else:
                                        underdog = "home"
                                    schedules[QUARTER_ML][id][q_no]["underdog"] = underdog
                            print_out = f'{print_league_teams} : Q{q_no}, underdog-{q_ml_match_data["underdog"]}, Ping {q_ml_match_data["ping"]}, scores {curr_quarter_home_score}:{curr_quarter_away_score}, {updated_remain} remains'
                            print(f'{datetime.now().strftime("%H:%M:%S")} {print_out}', '\n')
                        else:
                            print(f'{datetime.now().strftime("%H:%M:%S")} {print_league_teams} : Time Exceed({updated_remain})\n')
                            schedules[QUARTER_ML][id][q_no]["timeout_count"] += 1
                            if schedules[QUARTER_ML][id][q_no]["timeout_count"] > 3:
                                if q_ml_match_data["status"]:
                                    schedules[QUARTER_ML][id]["q_no"] = q_no + 1
                                    print(f'{datetime.now().strftime("%H:%M:%S")} {print_league_teams} : Moved To Q{q_no + 1} - {QUARTER_ML}', '\n')
                    else:
                        del schedules[QUARTER_ML][id]
                        if id not in schedules[QUARTER_TOTAL]:
                            removed_ids.append(id)
                        print(f'{datetime.now().strftime("%H:%M:%S")} {print_league_teams} : Deleted - {QUARTER_ML}', '\n')

                if id in schedules[QUARTER_TOTAL]:
                    match = schedules[QUARTER_TOTAL][id]
                    q_no = max(q_no, match["q_no"])
                    schedules[QUARTER_TOTAL][id]["q_no"] = q_no
                    match_league = match["league"]
                    scrap_url = match["url"]
                    print_league_teams = f'{match_league["short_name"].ljust(10)} [{match["home"].center(30)}] vs [{match["away"].center(30)}]'
                    
                    swap = match["swap"]
                    scores = scores_api
                    if swap:
                        scores["home"] = scores_api["away"]
                        scores["away"] = scores_api["home"]

                    updated_scores = sum(scores["home"]) + sum(scores["away"])
                    # updated_remain = match_league["time"] * 60 - gameTime
                    updated_remain = gameTime
                    if q_no == 0 and match[1]["over"] == EMPTY:
                        timestamp = datetime.fromisoformat(match["gameEt"].replace('Z', '+00:00')).timestamp()
                        if timestamp - int(datetime.now().timestamp()) < 60:
                            while is_scrapping_now:
                                sleep(0.1)
                            result = scrap_odds(scrap_url, FILTER_MARKET["1"]["filter"], FILTER_MARKET["1"]["market"])
                            schedules[QUARTER_TOTAL][id]["1"]["over"] = result["over"]
                            schedules[QUARTER_TOTAL][id]["1"]["under"] = result["under"]
                            print_out = f'{print_league_teams} : over {result["over"]} | under {result["under"]}'
                            print(f'{datetime.now().strftime("%H:%M:%S")} {print_out}', FILTER_MARKET["1"]["market"], '\n')
                        
                    output = f'updated time: {updated_remain}'

                    if q_no < match_league["round"] or (match_league["short_name"] == "CBA" and q_no == match_league["round"]):                    
                        if updated_remain > LIMIT_TIME_QUARTER_TOTAL:
                            remain_last = -1
                            if id not in live_matchs:
                                live_matchs[id] = []
                            if live_matchs[id]:
                                remain_last = live_matchs[id][-1]["remain"]
                            if updated_remain != remain_last:
                                live_matchs[id].append({"scores" : updated_scores, "remain" : updated_remain})

                                while len(live_matchs[id]) > 100:
                                    del live_matchs[id][0]
                                
                                result = "Don't Trigger"
                                if abs(sum(scores["home"]) - sum(scores["away"])) < 30:
                                    for data in live_matchs[id]:
                                        if data["remain"] - updated_remain <= 50:
                                            diff = updated_scores - data["scores"]
                                            if diff >= match_league[QUARTER_TOTAL][q_no]["rain"] and schedules[QUARTER_TOTAL][id]["trigger"] != "Rain":
                                                result = 'Rain'
                                            if diff >= match_league[QUARTER_TOTAL][q_no]["rain better"] and schedules[QUARTER_TOTAL][id]["trigger"] != "Better Rain":
                                                result = 'Better Rain'
                                    if result == "Don't Trigger":
                                        length = len(live_matchs[id])
                                        for index in range(length, 0, -1):
                                            data = live_matchs[id][index-1]
                                            diff = updated_scores - data["scores"]
                                            time_interval = data["remain"] - updated_remain
                                            time_drought = match_league[QUARTER_TOTAL][q_no]["drought"]
                                            time_better_dought = match_league[QUARTER_TOTAL][q_no]["drought better"]
                                            if time_interval >= time_drought and time_interval < time_better_dought and diff <= 1 and schedules[QUARTER_TOTAL][id]["trigger"] != "Drought":
                                                result = 'Drought'
                                            if time_interval >= time_better_dought and diff <= 1 and schedules[QUARTER_TOTAL][id]["trigger"] != "Better Drought":
                                                result = 'Better Drought'

                                if result != "Don't Trigger":
                                    schedules[QUARTER_TOTAL][id]["trigger"] = result
                                    if "Rain" in result:
                                        type = "ping_rain"
                                    if "Drought" in result:
                                        type = "ping_drought"
                                    if match[q_no][type] < LIMIT_PING:
                                        if match[q_no + 1]['over'] == EMPTY:
                                            while is_scrapping_now:
                                                sleep(0.1)
                                            scrap_result = scrap_odds(scrap_url, FILTER_MARKET[q_no]["filter"], FILTER_MARKET[q_no]["market"])
                                            print_out = f'{print_league_teams} : over {scrap_result["over"]} | under {scrap_result["under"]}'
                                            print(f'{datetime.now().strftime("%H:%M:%S")} {print_out}', FILTER_MARKET[q_no]["market"], '\n')
                                            live = scrap_result[TRIGGER[result]["odd"]]
                                            prematch = match[q_no][TRIGGER[result]["odd"]]

                                            emoji = ""
                                            if live != EMPTY:
                                                if  prematch != EMPTY:
                                                    if "Rain" in result and float(live.split('@')[0]) < float(prematch.split('@')[0]):
                                                        emoji = "⛔⛔⛔"
                                                    if "Drought" in result and float(live.split('@')[0]) > float(prematch.split('@')[0]):    
                                                        emoji = "⛔⛔⛔"
                                                else:
                                                    live_line = float(live.split('@')[0])
                                                    live_odds = live.split('@')[1]
                                                    if "Rain" in result:
                                                        live_line -= 1
                                                    if "Drought" in result:
                                                        live_line += 1 
                                                    try:
                                                        live_odds = float(live.split('@')[1])
                                                        if "Rain" in result:
                                                            live_odds -= 0.5
                                                        if "Drought" in result:
                                                            live_odds += 0.5
                                                    except:
                                                        pass
                                                    prematch = f"{live_line}@{live_odds}"
                                                    schedules[QUARTER_TOTAL][id][q_no][TRIGGER[result]["odd"]] = prematch
                                            else:
                                                emoji = "⛔⛔⛔"

                                            message = {
                                                "league" : match_league["name"],
                                                "short_name" : match_league["short_name"],
                                                "time" : match_league["time"],
                                                "id" : TRIGGER[result]["id"],
                                                "q_no" : q_no,
                                                "title" : FILTER_MARKET[q_no]["market"],
                                                "remain" : updated_remain,
                                                "home" : match["home"],
                                                "away" : match["away"],
                                                "prematch" : prematch,
                                                "live" : live,
                                                "url" : scrap_url,
                                                "emoji" : emoji,
                                                "algorithm" : QUARTER_TOTAL
                                                }
                                            with open('json files/message_to_be_pinged.json', 'w') as file:
                                                json.dump(message, file)
                                            schedules[QUARTER_TOTAL][id][q_no][type] += 1

                                seconds = 60 * match_league["time"] * q_no - updated_remain
                                game_time = f'{str(int(seconds / 60)).zfill(2)}:{str(int(seconds % 60)).zfill(2)}'
                                curr_prematch = f'Q{q_no}({(match[q_no]["over"]).center(9)}, {(match[q_no]["under"]).center(9)})'
                                next_prematch = f'Q{q_no + 1}({(match[q_no + 1]["over"]).center(9)}, {(match[q_no + 1]["under"]).center(9)})'
                                ping_rain = schedules[QUARTER_TOTAL][id][q_no]["ping_rain"]
                                ping_drought = schedules[QUARTER_TOTAL][id][q_no]["ping_drought"]
                                output = f'rain: {ping_rain}, drought: {ping_drought}, {result}\n\n{" "*91}{curr_prematch}, {next_prematch}, Time {game_time}'                                                                                                                        
                            else:
                                output = f'remain equal({updated_remain})'    
                        else:
                            schedules[QUARTER_TOTAL][id][q_no]["timeout_count"] += 1
                            if schedules[QUARTER_TOTAL][id][q_no]["timeout_count"] >= 5:
                                if updated_remain < 10 or (match_league["short_name"] == "CBA" and q_no == 4) or (match_league["short_name"] != "CBA" and q_no == 3):
                                    schedules[QUARTER_TOTAL][id]["q_no"] = q_no + 1

                                if id not in live_matchs or live_matchs[id]:
                                    live_matchs[id] = []
                                    schedules[QUARTER_TOTAL][id]["trigger"] = "Don't Trigger"

                                if updated_remain < 60 and match[q_no + 1]["over"] == EMPTY:
                                    while is_scrapping_now:
                                        sleep(0.1)
                                    result = scrap_odds(scrap_url, FILTER_MARKET[q_no + 1]["filter"], FILTER_MARKET[q_no + 1]["market"])
                                    print_out = f'{print_league_teams} : over {result["over"]} | under {result["under"]}'
                                    print(f'{datetime.now().strftime("%H:%M:%S")} {print_out}', FILTER_MARKET[q_no + 1]["market"], '\n')
                                    schedules[QUARTER_TOTAL][id][q_no + 1]["over"] = result["over"]
                                    schedules[QUARTER_TOTAL][id][q_no + 1]["under"] = result["under"]                                        
                            output = f'Time Exceed({updated_remain})'
                    else:
                        if id in schedules[QUARTER_TOTAL]:
                            del schedules[QUARTER_TOTAL][id]
                            if id not in schedules[QUARTER_ML]:
                                removed_ids.append(id)
                            print(f'{datetime.now().strftime("%H:%M:%S")} {print_league_teams} : Deleted - {QUARTER_TOTAL}', '\n')
                        if id in live_matchs:
                            del live_matchs[id]
                        output = 'Ended'
                    print(f'{datetime.now().strftime("%H:%M:%S")} {print_league_teams} : Q{q_no}, {output}\n')
        
        for id in removed_ids:
            gameIds.remove(id)

        if schedules[HALFTIME]:
            timecount += 1
            if timecount % 150 == 0:
                print('-'*50, f'{datetime.now().strftime("%H:%M:%S")} Quarter Total({len(schedules[QUARTER_TOTAL])}), Halftime({len(schedules[HALFTIME])}), Quarter ML({len(schedules[QUARTER_ML])})'.center(50), '-'*50, '\n')
                dest_url = LIVE_SCRAPING_URLS[0] # int(timecount / 150)%2
                if driver.current_url != dest_url:
                    driver.get(dest_url)
                if timecount == 300:
                    timecount = 0
                match_elements = []
                while not match_elements:
                    try:
                        empty = driver.find_element(By.ID, 'main-content').find_element(By.CLASS_NAME, 'sports-empty-list').text
                        match_elements.append(empty)
                    except:
                        pass
                    
                    # buttons = driver.find_elements(By.CLASS_NAME, 'x-flex-start')
                    # if len(buttons) == 2:
                    #     load_more = buttons[1].find_element(By.TAG_NAME, 'button')
                    #     print(load_more.text, "clicked")
                    #     driver.execute_script("arguments[0].click();", load_more)
                    #     sleep(0.5)
                    # if len(buttons) == 1:
                    match_elements = driver.find_elements(By.CLASS_NAME, 'fixture-preview')
                    for index, match_element in enumerate(match_elements):
                        try:
                            teams = match_element.find_element(By.CLASS_NAME, 'teams').text.split('\n')
                            home_team, away_team = teams[0], teams[1]
                            key = f"{home_team} vs {away_team}"
                            if key in schedules[HALFTIME]:
                                message = schedules[HALFTIME][key]
                                favourite_team = message["favourite"]
                                criteria_score = message["criteria"]
                                quarter = match_element.find_element(By.CLASS_NAME, 'fixture-details').text.replace('\n', ' ')
                                if "Second Break" in quarter or "Halftime" in quarter:
                                    temp = match_element.find_elements(By.CLASS_NAME, "weight-semibold")
                                    scores_home, scores_away = int(temp[0].text), int(temp[1].text)
                                    live_odds = match_element.find_elements(By.CLASS_NAME, 'weight-bold')
                                    print_league_teams = f'{" ".ljust(10)} [{home_team.center(30)}] vs [{away_team.center(30)}]'
                                    if favourite_team == "home" and scores_away - scores_home >= criteria_score:
                                        try:
                                            message["live"] = float(live_odds[0].text)
                                            message["scores"] = f"{scores_home}:{scores_away}"
                                            message["algorithm"] = HALFTIME
                                            with open('json files/message_to_be_pinged.json', 'w') as file:
                                                json.dump(message, file)
                                            del schedules[HALFTIME][key]
                                            print(f'{datetime.now().strftime("%H:%M:%S")} {print_league_teams} : Deleted - {HALFTIME}', '\n')
                                        except:
                                            pass
                                    if favourite_team == "away" and scores_home - scores_away >= criteria_score:
                                        try:
                                            message["live"] = float(live_odds[1].text)
                                            message["scores"] = f"{scores_away}:{scores_home}"
                                            message["algorithm"] = HALFTIME
                                            with open('json files/message_to_be_pinged.json', 'w') as file:
                                                json.dump(message, file)
                                            del schedules[HALFTIME][key]
                                            print(f'{datetime.now().strftime("%H:%M:%S")} {print_league_teams} : Deleted - {HALFTIME}', '\n')
                                        except:
                                            pass
                        except:
                            pass
                    sleep(0.1)
                if driver.current_url != LIVE_SCRAPING_URLS[0]:
                    driver.get(LIVE_SCRAPING_URLS[0])
        
        sleep(0.5)
    print('', '-'*50, 'fetching live End'.center(50), '-'*50, '\n')

def fetch_schedule():
    schedules = {
        QUARTER_TOTAL : {},
        HALFTIME : {},
        QUARTER_ML : {}
    }
    gameIds = []

    rankings = {}
    with open("json files/rankings.json", 'r') as file:
        rankings = json.load(file)

    print('\n')
    response = input("Are you sure you want to receive new ranking data? (y/n) ")
    print('\n')
    if response == "y":
        print('-'*50, 'Scrapping Rankings of NBA '.center(50), '-'*50, '\n')
        team_ranking_to_stake_map = {}
        with open("json files/team_ranking_to_stake_map.json", 'r') as file:
            team_ranking_to_stake_map = json.load(file)
        driver.get("https://www.teamrankings.com/nba/ranking/last-5-games-by-other")
        count = 0
        while True:
            try:
                rows = driver.find_element(By.ID, 'DataTables_Table_0').find_element(By.TAG_NAME, 'tbody').find_elements(By.TAG_NAME, 'tr')
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, 'td')
                    rank = int(cols[0].text)
                    name = " (".join(cols[1].text.split(" (")[:-1])
                    score = cols[1].text.split(" (")[-1].replace(")", "").split("-")
                    home_win = int(score[0])
                    away_win = int(score[1])
                    if team_ranking_to_stake_map["NBA"][name] == "":
                        count += 1
                        team_ranking_to_stake_map["NBA"][name] = f"{count}"
                    rankings[team_ranking_to_stake_map["NBA"][name]]  = {"ranking" : rank, "win" : home_win >= 2}
                if rows:
                    break
            except:
                pass
            try:
                empty = driver.find_element(By.CLASS_NAME, 'dataTables_empty').text
                break
            except:
                pass
            sleep(0.1)
        
        print('-'*50, 'Scrapping Rankings of NCAA'.center(50), '-'*50, '\n')
        driver.get("https://www.teamrankings.com/ncaa-basketball/ranking/last-5-games-by-other")
        while True:
            try:
                rows = driver.find_element(By.ID, 'DataTables_Table_0').find_element(By.TAG_NAME, 'tbody').find_elements(By.TAG_NAME, 'tr')
                results = {}
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, 'td')
                    rank = int(cols[0].text)
                    name = " (".join(cols[1].text.split(" (")[:-1])
                    score = cols[1].text.split(" (")[-1].replace(")", "").split("-")
                    home_win = int(score[0])
                    away_win = int(score[1])
                    if team_ranking_to_stake_map["NCAA"][name] == "":
                        count += 1
                        team_ranking_to_stake_map["NCAA"][name] = f"{count}"
                    rankings[team_ranking_to_stake_map["NCAA"][name]]  = {"ranking" : rank, "win" : home_win >= 2}
                if rows:
                    break
            except:
                pass
            try:
                empty = driver.find_element(By.CLASS_NAME, 'dataTables_empty').text
                break
            except:
                pass
            sleep(0.1)
        
        print('-'*50, 'Scrapping Rankings of CBA '.center(50), '-'*50, '\n')
        driver.get("https://www.flashscore.com/basketball/china/cba/standings/#/G2EAP5n6/form/overall/5")
        while True:
            try:
                rows = driver.find_elements(By.CLASS_NAME, 'ui-table__row')
                results = {}
                for row in rows:
                    cols = row.text.split("\n")
                    rank = int(cols[0].replace(".", ""))
                    name = cols[1]
                    home_win = int(cols[3])
                    away_win = int(cols[4])
                    if team_ranking_to_stake_map["CBA"][name] == "":
                        count += 1
                        team_ranking_to_stake_map["CBA"][name] = f"{count}"
                    rankings[team_ranking_to_stake_map["CBA"][name]]  = {"ranking" : rank, "win" : home_win >= 2}
                if rows:
                    break
            except:
                pass
            sleep(0.1)
        
        with open("json files/rankings.json", 'w') as file:
            json.dump(rankings, file)

    api_schedule = []
    response = requests.get('https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData/scoreboard/todaysScoreboard_00.json')        
    if response.status_code == 200:
        results = response.json().get('scoreboard')
        games = results["games"]
        for game in games:
            gameId = game["gameId"]
            gameEt = game["gameEt"]
            home = game["homeTeam"]
            away = game["awayTeam"]
            homeTeam = home["teamCity"] + " " + home["teamName"]
            awayTeam = away["teamCity"] + " " + away["teamName"]
            api_schedule.append({"home" : homeTeam, "away" : awayTeam, "gameId": gameId, "gameEt" : gameEt})
        
    with open("schedule.txt", "w") as file:
        file.write("")

    for league in leagues:
        print(f'{"-"*50} {league["name"].center(50)} {"-"*50}\n')
        log(f'{"-"*20} {league["name"].center(50)} {"-"*20}\n')
        driver.get(league['url'])
        sleep(1)
        while True:
            try:
                buttons = driver.find_elements(By.CLASS_NAME, 'x-flex-start')
                if len(buttons) == 2:
                    load_more = buttons[1].find_element(By.TAG_NAME, 'button')
                    driver.execute_script("arguments[0].click();", load_more)
                    sleep(0.5)
                if len(buttons) == 1:
                    match_elements = driver.find_elements(By.CLASS_NAME, 'fixture-preview')
                    for index, match_element in enumerate(match_elements):
                        url = match_element.find_element(By.TAG_NAME, 'a').get_attribute('href')
                        teams = match_element.find_element(By.CLASS_NAME, 'teams').text.split('\n')
                        home_team, away_team = teams[0], teams[1]
                        gameId, gameEt, swap = None, None, False
                        for api in api_schedule:
                            if home_team == api["home"] and away_team == api["away"]:
                                gameId, gameEt = api["gameId"], api["gameEt"]
                                gameIds.append(gameId)
                                break
                            elif home_team == api["away"] and away_team == api["home"]:
                                gameId, gameEt = api["gameId"], api["gameEt"]
                                gameIds.append(gameId)
                                swap = True
                                break
                            else:
                                pass
                        if gameId == api_schedule[-1]["gameId"]:
                            break
                        quarter = match_element.find_element(By.CLASS_NAME, 'fixture-details').text.replace('\n', ' ')
                        odds = match_element.find_elements(By.CLASS_NAME, 'weight-bold')
                        odds_home = 0
                        odds_away = 0
                        try:
                            odds_home = float(odds[0].text)
                        except:
                            pass
                        try:
                            odds_away = float(odds[1].text)
                        except:
                            pass

                        q_no = 1
                        if '2nd' in quarter or "First Break" in quarter:
                            q_no = 2
                        if '3rd' in quarter or "Second Break" in quarter:
                            q_no = 3
                        if '4th' in quarter or "Third Break" in quarter:
                            q_no = 4

                        output = ""
                        if 'End' not in quarter:                            
                            if league[HALFTIME]["status"]:
                                output_halftime = "Halftime - x"
                                if ":" in quarter or "1st" in quarter or "Start" in quarter or (league["round"] == 4 and ("First Break" in quarter or "2nd" in quarter)): 
                                    ranking_home, ranking_away = 0, 0
                                    try:
                                        ranking_home, ranking_away = rankings[home_team]['ranking'], rankings[away_team]['ranking']
                                    except:
                                        pass
                                    if odds_home <= league[HALFTIME]["odds"] and odds_home < odds_away and ranking_home < ranking_away and rankings[home_team]['win']:
                                        schedules[HALFTIME][f"{home_team} vs {away_team}"] = {
                                            "league" : league["name"],
                                            "short_name" : league["short_name"],
                                            "winner" : home_team,
                                            "prematch" : odds_home,
                                            "live" : 0,
                                            "scores" : "0:0",
                                            "url" : url,
                                            "criteria" : league[HALFTIME]['score'],
                                            "favourite" : "home",
                                            "algorithm" : ""
                                            }
                                        output_halftime = f"Halftime - o(home@{odds_home})"
                                    if odds_away <= league[HALFTIME]["odds"] and odds_away < odds_home and ranking_home > ranking_away and rankings[away_team]['win']:
                                        schedules[HALFTIME][f"{home_team} vs {away_team}"] = {
                                            "league" : league["name"],
                                            "short_name" : league["short_name"],
                                            "winner" : away_team,
                                            "prematch" : odds_away,
                                            "live" : 0,
                                            "scores" : "0:0",
                                            "url" : url,
                                            "criteria" : league[HALFTIME]['score'],
                                            "favourite" : "away",
                                            "algorithm" : ""
                                            }
                                        output_halftime = f"Halftime - o(away@{odds_away})"
                            
                            output_q_ml = f"QuarterML - x"
                            if league[QUARTER_ML]["status"]:
                                if gameId != None: 
                                    schedules[QUARTER_ML][gameId] = {
                                        "league" : league,
                                        "home" : home_team, 
                                        "away" : away_team,
                                        "url" : url,
                                        "q_no" : q_no,
                                        "swap" : swap,
                                        1 : {"ping" : 0, "underdog" : "None", "status" : False, "timeout_count" : 0},
                                        2 : {"ping" : 0, "underdog" : "None", "status" : False, "timeout_count" : 0},
                                        3 : {"ping" : 0, "underdog" : "None", "status" : False, "timeout_count" : 0},
                                        4 : {"ping" : 0, "underdog" : "None", "status" : False, "timeout_count" : 0},
                                        5 : {"ping" : 0, "underdog" : "None", "status" : False, "timeout_count" : 0}
                                        }
                                    output_q_ml = f"QuarterML - o"

                            output_q_total = f"QuarterTotal - x"
                            if league[QUARTER_TOTAL]["status"]:
                                if '4th' not in quarter and 'Third Break' not in quarter:
                                    if gameId != None:                                                   
                                        schedules[QUARTER_TOTAL][gameId] = {
                                            "league" : league,
                                            "home" : home_team, 
                                            "away" : away_team,
                                            "url" : url,
                                            "q_no" : q_no,
                                            "swap" : swap,
                                            "gameEt" : gameEt, 
                                            "trigger" : "Don't trigger",
                                            1 : {"over" : EMPTY, "under" : EMPTY, "ping_rain" : 0, "ping_drought" : 0, "timeout_count" : 0},
                                            2 : {"over" : EMPTY, "under" : EMPTY, "ping_rain" : 0, "ping_drought" : 0, "timeout_count" : 0},
                                            3 : {"over" : EMPTY, "under" : EMPTY, "ping_rain" : 0, "ping_drought" : 0, "timeout_count" : 0},
                                            4 : {"over" : EMPTY, "under" : EMPTY, "ping_rain" : 0, "ping_drought" : 0, "timeout_count" : 0},
                                            5 : {"over" : EMPTY, "under" : EMPTY, "ping_rain" : 0, "ping_drought" : 0, "timeout_count" : 0}
                                            }
                                        output_q_total = f"QuarterTotal - o"
                            output = f"Q{q_no}, {output_q_total}, {output_q_ml}, {output_halftime} swap-{swap}"
                        else:
                            output = "Ended"
                        
                        print(f'{str(index + 1).zfill(2)}. [{home_team.center(30)}] vs [{away_team.center(30)}] : {output}\n')
                        log(f'{str(index + 1).zfill(2)}. [{home_team.center(30)}] vs [{away_team.center(30)}] : {output}\n')
                    break
            except Exception as e:
                print(e)
            try:
                empty = driver.find_element(By.ID, 'main-content').find_element(By.CLASS_NAME, 'sports-empty-list').text
                break
            except:
                pass
            sleep(0.1)
    return schedules, list(set(gameIds))

if __name__ == "__main__":
    while True:
        schedules, gameIds = fetch_schedule()
        print(gameIds)
        with open("json files/schedules.json", 'w') as file:
            json.dump(schedules, file)

        curr_hour = datetime.now().hour
        curr_minute = datetime.now().minute
        curr_second = datetime.now().second
        waitingTime = 86400 - curr_hour * 3600  - curr_minute * 60 - curr_second

        hour = int(waitingTime / 3600)
        minute = int((waitingTime % 3600) / 60)
        second = int((waitingTime % 3600) % 60)
        print('-'*50, f'sleeping for {hour}:{minute}:{second}'.center(50), '-'*50, '\n')

        thread_live = Thread(target=fetch_live, args=(schedules, gameIds, ))
        thread_live.start()
        thread_QuarterML = Thread(target=scrap_odds_for_QuarterML)
        thread_QuarterML.start()

        sleep(waitingTime)
