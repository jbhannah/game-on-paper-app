from flask import Flask, request, jsonify
import xgboost as xgb
import numpy as np
from datetime import datetime as dt
from flask_logs import LogSetup
from play_handler import PlayProcess
import os
import logging
import urllib
import pandas as pd
import json

app = Flask(__name__)
app.config["LOG_TYPE"] = os.environ.get("LOG_TYPE", "stream")
app.config["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")

logs = LogSetup()
logs.init_app(app)

ep_model = xgb.Booster({'nthread': 4})  # init model
ep_model.load_model('models/ep_model.model')

wp_model = xgb.Booster({'nthread': 4})  # init model
wp_model.load_model('models/wp_spread.model')

@app.after_request
def after_request(response):
    logger = logging.getLogger("app.access")
    logger.info(
        "[python] %s [%s] %s %s %s",
        request.remote_addr,
        dt.utcnow().strftime("%d/%b/%Y:%H:%M:%S.%f")[:-3],
        request.method,
        request.path,
        response.status
    )
    return response

@app.route('/cfb/process', methods=['POST'])
def process():
    gameId = request.get_json(force=True)['gameId']
    processed_data = PlayProcess(logger = logging.getLogger("root"), gameId = gameId)
    git_cache_pbp = processed_data.git_pbp()
    if (git_cache_pbp != None):
        pbp = json.loads(git_cache_pbp)
        box = pbp["advBoxScore"] if ("advBoxScore" in pbp.keys()) else pbp["box_score"]
        for k in box.keys():
            box_list = box[k]
            for item in box_list:
                item["pos_team"] = item["posteam"]
            
        jsonified_df = pbp["plays"]
    else:
        pbp = processed_data.cfb_pbp()
        processed_data.run_processing_pipeline()
        tmp_json = processed_data.plays_json.to_json(orient="records")
        jsonified_df = json.loads(tmp_json)
        box = processed_data.create_box_score()

    bad_cols = [
        'start.distance', 'start.yardLine', 'start.team.id', 'start.down', 'start.yardsToEndzone', 'start.posTeamTimeouts', 'start.defTeamTimeouts', 
        'start.shortDownDistanceText', 'start.possessionText', 'start.downDistanceText', 'start.pos_team_timeouts', 'start.def_pos_team_timeouts',
        'clock.displayValue',
        'type.id', 'type.text', 'type.abbreviation',
        'end.distance', 'end.yardLine', 'end.team.id','end.down', 'end.yardsToEndzone', 'end.posTeamTimeouts','end.defTeamTimeouts', 
        'end.shortDownDistanceText', 'end.possessionText', 'end.downDistanceText', 'end.pos_team_timeouts', 'end.def_pos_team_timeouts',
        'expectedPoints.before', 'expectedPoints.after', 'expectedPoints.added', 
        'winProbability.before', 'winProbability.after', 'winProbability.added', 
        'scoringType.displayName', 'scoringType.name', 'scoringType.abbreviation'
    ]
    # clean records back into ESPN format
    for record in jsonified_df:
        record["pos_team"] = record["pos_team"] if ("pos_team" in record.keys()) else record["posteam"]

        record["clock"] = {
            "displayValue" : record["clock.displayValue"]
        }

        record["type"] = {
            "id" : record["type.id"],
            "text" : record["type.text"],
            "abbreviation" : record["type.abbreviation"],
        }
        record["modelInputs"] = {
            "start" : {
                "down" : record["start.down"],
                "distance" : record["start.distance"],
                "yardsToEndzone" : record["start.yardsToEndzone"],
                "TimeSecsRem": record["start.TimeSecRem"] if ("start.TimeSecRem" in record.keys()) else record["start.half_seconds_remaining"],
                "adj_TimeSecsRem" : record["start.adj_TimeSecRem"] if ("start.adj_TimeSecRem" in record.keys()) else record["start.game_seconds_remaining"],
                "pos_score_diff" : record["start.pos_score_diff"] if ("start.pos_score_diff" in record.keys()) else record["start.posteam_score_differential"],
                "posTeamTimeouts" : record["start.posTeamTimeouts"] if ("start.posTeamTimeouts" in record.keys()) else record["start.posteamTimeouts"],
                "defTeamTimeouts" : record["start.defPosTeamTimeouts"] if ("start.defPosTeamTimeouts" in record.keys()) else record["start.defteamTimeouts"],
                "ExpScoreDiff" : record["start.ExpScoreDiff"],
                "ExpScoreDiff_Time_Ratio" : record["start.ExpScoreDiff_Time_Ratio"],
                "spread_time" : record['start.spread_time'],
                "pos_team_receives_2H_kickoff": record["start.pos_team_receives_2H_kickoff"] if ("start.pos_team_receives_2H_kickoff" in record.keys()) else record["start.posteam_receives_2H_kickoff"],
                "is_home": record["start.is_home"] if ("start.is_home" in record.keys()) else (record["start.team.id"] == record["homeTeamId"]),
                "period": record["period"]
            },
            "end" : {
                "down" : record["end.down"],
                "distance" : record["end.distance"],
                "yardsToEndzone" : record["end.yardsToEndzone"],
                "TimeSecsRem": record["end.TimeSecRem"] if ("end.TimeSecRem" in record.keys()) else record["end.half_seconds_remaining"],
                "adj_TimeSecsRem" : record["end.adj_TimeSecRem"] if ("end.adj_TimeSecRem" in record.keys()) else record["end.game_seconds_remaining"],
                "posTeamTimeouts" : record["end.posTeamTimeouts"] if ("end.posTeamTimeouts" in record.keys()) else record["end.posteamTimeouts"],
                "defTeamTimeouts" : record["end.defPosTeamTimeouts"] if ("end.defPosTeamTimeouts" in record.keys()) else record["end.defteamTimeouts"],
                "pos_score_diff" : record["end.pos_score_diff"] if ("end.pos_score_diff" in record.keys()) else record["end.posteam_score_differential"],
                "ExpScoreDiff" : record["end.ExpScoreDiff"],
                "ExpScoreDiff_Time_Ratio" : record["end.ExpScoreDiff_Time_Ratio"],
                "spread_time" : record['end.spread_time'],
                "pos_team_receives_2H_kickoff": record["end.pos_team_receives_2H_kickoff"] if ("end.pos_team_receives_2H_kickoff" in record.keys()) else record["end.posteam_receives_2H_kickoff"],
                "is_home": record["end.is_home"] if ("end.is_home" in record.keys()) else (record["end.team.id"] == record["homeTeamId"]),
                "period": record["period"]
            }
        }

        record["expectedPoints"] = {
            "before" : record["EP_start"],
            "after" : record["EP_end"],
            "added" : record["EPA"]
        }

        record["winProbability"] = {
            "before" : record["wp_before"],
            "after" : record["wp_after"],
            "added" : record["wpa"]
        }

        record["start"] = {
            "team" : {
                "id" : record["start.team.id"],
            },
            "pos_team": {
                "id" : record["start.pos_team.id"] if ("start.pos_team.id" in record.keys()) else record["start.posteam.id"],
                "name" : record["start.pos_team.name"] if ("start.pos_team.name" in record.keys()) else record["start.posteam.name"]
            },
            "def_pos_team": {
                "id" : record["start.def_pos_team.id"] if ("start.def_pos_team.id" in record.keys()) else record["start.defteam.id"],
                "name" : record["start.def_pos_team.name"] if ("start.def_pos_team.name" in record.keys()) else record["start.defteam.name"],
            },
            "distance" : record["start.distance"],
            "yardLine" : record["start.yardLine"],
            "down" : record["start.down"],
            "yardsToEndzone" : record["start.yardsToEndzone"],
            "homeScore" : record["start.homeScore"],
            "awayScore" : record["start.awayScore"],
            "pos_team_score" : record["start.pos_team_score"] if ("start.pos_team_score" in record.keys()) else record["start.posteam_score"],
            "def_pos_team_score" : record["start.def_pos_team_score"] if ("start.def_pos_team_score" in record.keys()) else record["start.defteam_score"],
            "pos_score_diff" : record["start.pos_score_diff"] if ("start.pos_score_diff" in record.keys()) else record["start.posteam_score_differential"],
            "posTeamTimeouts" : record["start.posTeamTimeouts"] if ("start.posTeamTimeouts" in record.keys()) else record["start.posteamTimeouts"],
            "defTeamTimeouts" : record["start.defPosTeamTimeouts"] if ("start.defPosTeamTimeouts" in record.keys()) else record["start.defteamTimeouts"],
            "ExpScoreDiff" : record["start.ExpScoreDiff"],
            "ExpScoreDiff_Time_Ratio" : record["start.ExpScoreDiff_Time_Ratio"],
            "shortDownDistanceText" : record["start.shortDownDistanceText"],
            "possessionText" : record["start.possessionText"],
            "downDistanceText" : record["start.downDistanceText"]
        }

        record["end"] = {
            "team" : {
                "id" : record["end.team.id"],
            },
            "pos_team": {
                "id" : record["end.pos_team.id"] if ("end.pos_team.id" in record.keys()) else record["end.posteam.id"],
                "name" : record["end.pos_team.name"] if ("end.pos_team.name" in record.keys()) else record["end.posteam.name"],
            }, 
            "def_pos_team": {
                "id" : record["end.def_pos_team.id"] if ("end.def_pos_team.id" in record.keys()) else record["end.defteam.id"],
                "name" : record["end.def_pos_team.name"] if ("end.def_pos_team.name" in record.keys()) else record["end.defteam.name"],
            }, 
            "distance" : record["end.distance"],
            "yardLine" : record["end.yardLine"],
            "down" : record["end.down"],
            "yardsToEndzone" : record["end.yardsToEndzone"],
            "homeScore" : record["end.homeScore"],
            "awayScore" : record["end.awayScore"],
            "pos_team_score" : record["end.pos_team_score"] if ("end.pos_team_score" in record.keys()) else record["end.posteam_score"],
            "def_pos_team_score" : record["end.def_pos_team_score"] if ("end.def_pos_team_score" in record.keys()) else record["end.defteam_score"],
            "pos_score_diff" : record["end.pos_score_diff"] if ("end.pos_score_diff" in record.keys()) else record["end.posteam_score_differential"],
            "posTeamTimeouts" : record["end.posTeamTimeouts"] if ("end.posTeamTimeouts" in record.keys()) else record["end.posteamTimeouts"],
            "defPosTeamTimeouts" : record["end.defPosTeamTimeouts"] if ("end.defPosTeamTimeouts" in record.keys()) else record["end.defteamTimeouts"],
            "ExpScoreDiff" : record["end.ExpScoreDiff"],
            "ExpScoreDiff_Time_Ratio" : record["end.ExpScoreDiff_Time_Ratio"],
            "shortDownDistanceText" : record["end.shortDownDistanceText"],
            "possessionText" : record["end.possessionText"],
            "downDistanceText" : record["end.downDistanceText"]
        }

        record["players"] = {
            'passer_player_name' : record["passer_player_name"],
            'rusher_player_name' : record["rusher_player_name"],
            'receiver_player_name' : record["receiver_player_name"],
            'sack_player_name' : record["sack_player_name"],
            'sack_player_name2' : record["sack_player_name2"],
            'pass_breakup_player_name' : record["pass_breakup_player_name"],
            'interception_player_name' : record["interception_player_name"],
            'fg_kicker_player_name' : record["fg_kicker_player_name"],
            'fg_block_player_name' : record["fg_block_player_name"],
            'fg_return_player_name' : record["fg_return_player_name"],
            'kickoff_player_name' : record["kickoff_player_name"],
            'kickoff_return_player_name' : record["kickoff_return_player_name"],
            'punter_player_name' : record["punter_player_name"],
            'punt_block_player_name' : record["punt_block_player_name"],
            'punt_return_player_name' : record["punt_return_player_name"],
            'punt_block_return_player_name' : record["punt_block_return_player_name"],
            'fumble_player_name' : record["fumble_player_name"],
            'fumble_forced_player_name' : record["fumble_forced_player_name"],
            'fumble_recovered_player_name' : record["fumble_recovered_player_name"],
        }
        # remove added columns
        for col in bad_cols:
            record.pop(col, None)

    result = {
        "id": gameId,
        "count" : len(jsonified_df),
        "plays" : jsonified_df,
        "box_score" : box,
        "homeTeamId": pbp['header']['competitions'][0]['competitors'][0]['team']['id'],
        "awayTeamId": pbp['header']['competitions'][0]['competitors'][1]['team']['id'],
        "drives" : pbp['drives'],
        "scoringPlays" : np.array(pbp['scoringPlays']).tolist(),
        "winprobability" : np.array(pbp['winprobability']).tolist(),
        "boxScore" : pbp['boxscore'],
        "homeTeamSpread" : np.array(pbp['homeTeamSpread']).tolist() if ("homeTeamSpread" in pbp.keys()) else jsonified_df[0]["homeTeamSpread"],
        "header" : pbp['header'],
        "broadcasts" : np.array(pbp['broadcasts']).tolist(),
        "videos" : np.array(pbp['videos']).tolist(),
        "standings" : pbp['standings'],
        "pickcenter" : np.array(pbp['pickcenter']).tolist(),
        "espnWinProbability" : np.array(pbp['espnWP']).tolist(),
        "gameInfo" : np.array(pbp['gameInfo']).tolist(),
        "season" : np.array(pbp['season']).tolist()
    }
    
    # logging.getLogger("root").info(result)
    return jsonify(result)

@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    return jsonify({
        "status": "ok"
    })

if __name__ == '__main__':
    app.run(port=7000, debug=False, host='0.0.0.0')

