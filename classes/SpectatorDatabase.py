import datetime
import mysql.connector
import traceback
import config.database as config_db

class SpectatorDatabase:

    def __init__(self, json, is_live_game, logger):
        try:
            # Connect to database
            self.db = mysql.connector.connect(
                host=config_db.database['host'],
                user=config_db.database['user'],
                password=config_db.database['password'],
                database=config_db.database['database']
            )
            self.db_cursor = self.db.cursor()
            self.logger = logger
            self.spectator_participants = []
            self.participant_leagues_saved = []
            self.participant_data_saved = []

            spectator_data = [
                int(is_live_game),
                json.get("gameId", None),
                json.get("mapId", None),
                json.get("gameMode", None),
                json.get("gameType", None),
                self.epoch_to_datetime(json.get("gameStartTime", None)),
                json.get("gameLength", None),
                json.get("gameQueueConfigId", None),
                json.get("platformId", None),
                self.find_in_dict_levels(json, ['observers', 'encryptionKey'])
            ]
            spectator_data_insert = "INSERT INTO `spectator_data`(`live_game_data`, `gameId`, `mapId`, `gameMode`, `gameType`, `gameStartTime`, `gameLength`, `gameQueueConfigId`, `platformId`, `observers_encryptionKey`) VALUES (" + self.values_to_insert_values(spectator_data) + ")"
            # Insert game data
            self.db_cursor.execute(spectator_data_insert)
            self.db.commit()
            inserted_match_id = self.db_cursor.lastrowid
            self.match_id = inserted_match_id
            logger.log('Info', 'SpectatorDatabase', 'Match data inserted, match id #' + str(inserted_match_id) + " game id: " + str(json.get("gameId", None)))

            banned_champions_insert = "INSERT INTO `spectator_banned_champions`(`match_id`, `bannedChampions_championId`, `bannedChampions_teamId`, `bannedChampions_pickTurn`) VALUES (%s,%s,%s,%s)"
            banned_champions_to_insert = []
            banned_champions = json.get('bannedChampions', [])
            if banned_champions != [] and isinstance(banned_champions, list):
                for champion in banned_champions:
                    banned_champions_to_insert.append((inserted_match_id, champion.get("championId", None), champion.get("teamId", None), champion.get("pickTurn", None)))
                if len(banned_champions_to_insert) > 0:
                    self.db_cursor.executemany(banned_champions_insert, banned_champions_to_insert)
                    self.db.commit()
                    logger.log('Info', 'SpectatorDatabase','Banned champions inserted, inserted ' + str(len(banned_champions_to_insert)) + ' champions!')
            else:
                logger.log('Info', 'SpectatorDatabase', 'No banned champions found!')

            participants = json.get("participants", [])
            for participant in participants:
                perks = self.find_in_dict_levels(participant, ["perks", "perkIds"])
                participant_data = [
                    inserted_match_id,
                    participant.get("teamId", None),
                    participant.get("spell1Id", None),
                    participant.get("spell2Id", None),
                    participant.get("championId", None),
                    participant.get("profileIconId", None),
                    participant.get("summonerName", None),
                    participant.get("bot", None),
                    participant.get("summonerId", None),
                    self.find_in_dict_levels(participant, ['perks', 'perkStyle']),
                    self.find_in_dict_levels(participant, ['perks', 'perkSubStyle'])
                ]
                participant_data_insert = "INSERT INTO `spectator_participants`(`match_id`, `participants_teamId`, `participants_spell1Id`, `participants_spell2Id`, `participants_championId`, `participants_profileIconId`, `participants_summonerName`, `participants_bot`, `participants_summonerId`, `participants_perks_perkStyle`, `participants_perks_perkSubStyle`) VALUES (" + self.values_to_insert_values(participant_data) + ")"
                # Insert participant data
                self.db_cursor.execute(participant_data_insert)
                self.db.commit()
                participant_id = self.db_cursor.lastrowid
                self.spectator_participants.append(participant_id)

                perk_data_insert = "INSERT INTO `participant_perks` (`match_id`, `participant_perkId`, `participant_id`) VALUES (%s, %s, %s)"
                perks_to_insert = []
                if perks is not None and isinstance(perks, list):
                    for perk in perks:
                        perks_to_insert.append((inserted_match_id, perk, participant_id))
                    if len(perks_to_insert) > 0:
                        self.db_cursor.executemany(perk_data_insert, perks_to_insert)
                        self.db.commit()
                elif not isinstance(perks, list):
                    logger.log('Error', 'SpectatorDatabase','Perks found not to be list, found ' + str(type(perks)))

            logger.log('Info', 'SpectatorDatabase', str(len(participants)) + ' participants processed!')
        except Exception as e:
            logger.log("Error", 'SpectatorDatabase', 'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

    def close(self):
        try:
            # Close connection
            self.db_cursor.close()
            self.db.close()
            if len(self.participant_data_saved) > 0:
                self.logger.log('Info', 'SpectatorDatabase(addParticipantData)','Saved match id '+str(self.match_id)+' participant data for participants with ids ' + ", ".join(self.participant_data_saved) + '!')
            if len(self.participant_leagues_saved) > 0:
                self.logger.log('Info', 'SpectatorDatabase(addLeagues)','Saved match id '+str(self.match_id)+' participant leagues for participants with ids ' + ", ".join(self.participant_leagues_saved) + '!')
        except Exception as e:
            self.logger.log("Error", 'SpectatorDatabase(Close)','Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

    def add_leagues(self, league_json, participant_num):
        try:
            league_insert = "INSERT INTO `participant_leagues`(`match_id`, `participant_id`, `leagueId`, `summonerId`, `summonerName`, `queueType`, `tier`, `rank`, `leaguePoints`, `wins`, `losses`, `hotStreak`, `veteran`, `freshBlood`, `inactive`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            league_data_to_insert = []
            for json in league_json:
                league_data_to_insert.append(
                    (
                        self.match_id,
                        self.spectator_participants[participant_num],
                        json.get("leagueId", None),
                        json.get("summonerId", None),
                        json.get("summonerName", None),
                        json.get("queueType", None),
                        json.get("tier", None),
                        json.get("rank", None),
                        json.get("leaguePoints", None),
                        json.get("wins", None),
                        json.get("losses", None),
                        self.string_to_bool_int(json.get("hotStreak", None)),
                        self.string_to_bool_int(json.get("veteran", None)),
                        self.string_to_bool_int(json.get("freshBlood", None)),
                        self.string_to_bool_int(json.get("inactive", None))
                    )
                )
            self.db_cursor.executemany(league_insert, league_data_to_insert)
            self.db.commit()
            self.participant_leagues_saved.append(str(self.spectator_participants[participant_num]))
        except Exception as e:
            self.logger.log('Error', 'SpectatorDatabase(addLeagues)', 'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

    def add_participant_data(self, participant_json, participant_num):
        try:
            participant_data = [
                self.match_id,
                self.spectator_participants[participant_num],
                participant_json.get("id", None),
                participant_json.get("accountId", None),
                participant_json.get("puuid", None),
                participant_json.get("name", None),
                participant_json.get("profileIconId", None),
                participant_json.get("revisionDate", None),
                participant_json.get("summonerLevel", None),
            ]
            spectator_insert = "INSERT INTO `participant_data`(`match_id`, `participant_id`, `summonerId`, `accountId`, `puuid`, `summonerName`, `profileIconId`, `revisionDate`, `summonerLevel`) VALUES (" + self.values_to_insert_values(participant_data) + ")"
            self.db_cursor.execute(spectator_insert)
            self.db.commit()
            self.participant_data_saved.append(str(self.spectator_participants[participant_num]))
        except Exception as e:
            self.logger.log('Error', 'SpectatorDatabase(addParticipantData)', 'Something went wrong! Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))

    def string_to_bool_int(self, json_response):
        if json_response is not None:
            if isinstance(json_response, str):
                if json_response.lower() == "true":
                    return 1
                elif json_response.lower() == "false":
                    return 0
            elif isinstance(json_response, bool):
                return int(json_response)
        return None

    def values_to_insert_values(self, values):
        insert_values = ""
        for value in values:
            if type(value) == bool:
                value = int(value)
            insert_values += "\"" + (str(value) + "\",")
        return insert_values[:-1]

    def find_in_dict_levels(self, json, levels):
        if len(levels) == 0: return None
        currentLevel = None
        for level in levels:
            if currentLevel is None:
                currentLevel = json.get(level, None)
            else:
                currentLevel = currentLevel.get(level, None)
            if currentLevel is None:
                return None
        return currentLevel

    def epoch_to_datetime(self, epoch_time):
        if epoch_time is None:
            return None
        return datetime.datetime.fromtimestamp(epoch_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
