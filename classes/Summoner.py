
class Summoner:

    def __init__(self):
        self.account_id = None
        self.profile_icon_id = None
        self.name = None
        self.summoner_id = None
        self.puuid = None
        self.summoner_level = None
        self.matches = []
        self.champion = None

    def set_name(self, name):
        self.name = name

    def set_summoner_id(self, summoner_id):
        self.summoner_id = summoner_id

    def set_champion(self, champion):
        self.champion = champion

    def set_profile_icon(self, icon):
        self.profile_icon_id = icon

    def set_puuid(self, puuid):
        self.puuid = puuid

    def set_account_id(self, account_id):
        self.account_id = account_id

    def set_summoner_level(self, summoner_level):
        self.summoner_level = summoner_level

    def set_from_api(self, api_response):
        self.account_id = api_response['accountId']
        self.profile_icon_id = api_response['profileIconId']
        self.name = api_response['name']
        self.summoner_id = api_response['id']
        self.puuid = api_response['puuid']
        self.summoner_level = api_response['summonerLevel']

    def get_premades(self, current_game_participants: list):
        try:
            possible_premades = []
            confirmed_possible_premades = []
            full_confirmed_premades = []
            for match in self.matches:
                for match_participant_puuid in match.participantPuuids:
                    for current_participant in current_game_participants:
                        if match_participant_puuid == current_participant.puuid and current_participant.puuid != self.puuid:
                            if current_participant.name in possible_premades and current_participant.name not in confirmed_possible_premades:
                                confirmed_possible_premades.append(current_participant.name)
                                full_confirmed_premades.append("*" + str(current_participant.champion.get_name()) + "*")
                            elif current_participant.name not in possible_premades:
                                possible_premades.append(current_participant.name)
            return confirmed_possible_premades, full_confirmed_premades
        except Exception as e:
            print(e)
            return [], []
