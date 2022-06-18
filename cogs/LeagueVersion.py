from discord.ext import commands
import urllib.request
import json
import requests
import datetime
import traceback
from classes.Champion import Champion
import config.config as config


class LeagueVersion(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger
        self.api_key = config.riot_api_key

    @commands.Cog.listener()
    async def on_ready(self):
        await self.resource_version_check()
        await self.id_update_check()

    async def resource_version_check(self):
        # Opens page which contains all (patch) versions
        versions_page = urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json")
        versions = json.loads(versions_page.read().decode())
        # Selects newest version which is first
        self.client.dd_newest_version = versions[0]
        # Saves update time as time right now
        self.client.last_version_check = datetime.datetime.now()

        # Gets league champion objects and game_champions array with only champion formatted names
        self.client.league_champions = await self.get_all_champions()

        self.logger.log(self.logger.LOG_TYPE_INFO, 'resource_version_check',
                        'Version check completed! Version: ' + str(self.client.dd_newest_version))

    async def get_all_champions(self):
        try:
            champions_page = urllib.request.urlopen(
                "http://ddragon.leagueoflegends.com/cdn/" + str(
                    self.client.dd_newest_version) + "/data/en_US/champion.json")
            champion_json_array = json.loads(champions_page.read().decode())
            champions = {}
            self.client.game_champions = []
            for champion in champion_json_array['data']:
                # Create assoc array with champion key and champion object
                champion_json = champion_json_array['data'][champion]
                self.client.game_champions.append(champion_json['id'])
                champions[int(champion_json['key'])] = Champion(champion_json)
            self.logger.log(self.logger.LOG_TYPE_INFO, 'get_all_champions',
                                   'Retrieved ' + str(len(champions)) + ' champions')
            return champions
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_all_champions',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    async def id_update_check(self):
        try:
            url_enchanted = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/by-name/" + self.client.enchanted_summoner_name + "?api_key=" + self.api_key
            url_robo = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/by-name/" + self.client.roboobox_summoner_name + "?api_key=" + self.api_key

            page = urllib.request.urlopen(url_enchanted)
            j = json.loads(page.read().decode())
            self.client.enchanted_id = j['id']
            self.client.enchanted_account_id = j['accountId']

            page = urllib.request.urlopen(url_robo)
            j = json.loads(page.read().decode())
            self.client.roboobox_id = j['id']
            self.client.roboobox_account_id = j['accountId']

            self.logger.log(self.logger.LOG_TYPE_INFO, 'id_update_check',
                            'Summoner ID check completed!  New Robo ID:' + self.client.roboobox_id + ', new Enchanted ID:' + self.client.enchanted_id)
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'id_update_check', str(e))

    @commands.command()
    async def version_check(self, ctx):
        try:
            if ctx.author.id == self.client.roboobox_full_id:
                await self.resource_version_check()
                await ctx.send('Performed Data Dragon version check! :white_check_mark:')
            else:
                self.logger.log(self.logger.LOG_TYPE_INFO, 'version_check',
                                'Version check tried by unauthorized user: ' + str(ctx.author))
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'version_check',
                            'Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))


def setup(client):
    client.add_cog(LeagueVersion(client))
