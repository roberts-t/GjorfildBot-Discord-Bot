
class SummonerMatch:

    def __init__(self, summoner_match_data, summoner_match):
        self.matchObject = summoner_match
        self.kills = summoner_match_data['kills']
        self.deaths = summoner_match_data['deaths']
        self.assists = summoner_match_data['assists']
        self.championName = summoner_match_data['championName']
        self.championId = summoner_match_data['championId']
        self.championLevel = summoner_match_data['champLevel']
        self.position = summoner_match_data['teamPosition']
        self.lane = summoner_match_data['lane']
        self.gameTime = summoner_match_data['timePlayed']
        self.minionsKilled = summoner_match_data['totalMinionsKilled']
        self.visionScore = summoner_match_data['visionScore']
        self.isVictory = summoner_match_data['win']

    def get_kda_ratio(self):
        return str(round((self.kills + self.assists) / self.deaths, 2))

    def get_kda(self):
        return str(self.kills).zfill(2) + "/" + str(self.deaths).zfill(2) + "/" + str(self.assists).zfill(2)

    def get_cs_score(self):
        return str(self.minionsKilled).zfill(3) + " CS"

    def get_champion_info(self, champion_emoji = ""):
        game_status_symbol = ":blue_square:"
        if not self.isVictory:
            game_status_symbol = ":red_square:"
        return game_status_symbol + " " + champion_emoji + " " + str(self.championName) + " (" + str(self.championLevel) + ". lvl)"

    def get_position(self):
        if self.position == None or self.position == "":
            return "None"
        return str(self.position)

    def get_match_time(self):
        game_duration = int(self.matchObject.gameDuration)
        # Riot API: Treat the value as milliseconds if the gameEndTimestamp field isn't in the response and to treat the value as seconds if gameEndTimestamp is in the response
        if self.matchObject.gameEnd is None:
            game_duration /= 1000
        game_duration /= 60
        return str(int(game_duration)).zfill(2) + "m"

    def get_additional_summary(self):
        return self.get_cs_score() + " | " + self.get_match_time() + " | " + self.get_kda()
