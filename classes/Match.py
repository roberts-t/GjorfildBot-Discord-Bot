
class Match:

    def __init__(self, api_response):
        self.matchId = api_response['metadata']['matchId']
        self.participantPuuids = api_response['metadata']['participants']
        self.mapId = api_response['info']['mapId']
        self.queueId = api_response['info']['queueId']
        self.participants = api_response['info']['participants']
        self.gameDuration = api_response['info']['gameDuration']
        if "gameEndTimestamp" not in api_response['info']:
            self.gameEnd = None
        else:
            self.gameEnd = api_response['info']['gameEndTimestamp']