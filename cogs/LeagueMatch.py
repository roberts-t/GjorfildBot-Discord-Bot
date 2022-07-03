from discord.ext import commands
import discord
from discord.utils import get
import urllib.request
import aiohttp
import datetime
import json
import time
import traceback

import config.config
from classes.Summoner import Summoner
from classes.Match import Match
from classes.SummonerMatch import SummonerMatch
from classes.SpectatorDatabase import SpectatorDatabase
from classes.RiotApiLogger import RiotApiLogger


class LeagueMatch(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger
        self.db = client.db
        self.last_game_data_gathered = False
        self.last_game_summoners = []
        self.live_game_refreshed = datetime.datetime.now()
        self.api_key = config.config.riot_api_key
        self.last_game_champions = {}

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        try:
            file_data = []
            # Checks if before and after activity is not the same and if activity user ir Roboobox or Enchanted dragon (by discriminator)
            if before.activity != after.activity and (
                    before.discriminator == self.client.roboobox_discord_id or before.discriminator == self.client.enchanted_discord_id):
                # Checks if new activity is League of Legends
                if after.activity is not None and after.activity.name == "League of Legends":
                    # Reads playtime file data and saves lines in file_data variable
                    roboobox_playtime = self.db.query_select_one(
                        "SELECT is_online, last_online FROM gjorfild_playtime WHERE `member` = '#8998'")
                    dragon_playtime = self.db.query_select_one(
                        "SELECT is_online, last_online FROM gjorfild_playtime WHERE `member` = '#9101'")
                    notifications_enabled = self.db.query_select_one(
                        "SELECT notifications_enabled FROM gjorfild_settings LIMIT 1")
                    if not roboobox_playtime or not roboobox_playtime or not notifications_enabled:
                        raise Exception('Failed to get playtime data from database')

                    # Checks if activity user ir EnchantedDragon or Roboobox and if playtime file indicated that user is not in game then updates game start
                    # time and sets in game value as true, writes updated file_data to file
                    if after.discriminator == self.client.roboobox_discord_id and roboobox_playtime[0] == 0 and (
                            after.activity.state == "In Champion Select" or after.activity.state == "In Game"):
                        if not self.db.query_modify(
                                "UPDATE gjorfild_playtime SET is_online = 1, last_online = %s WHERE `member` = '#8998'",
                                [datetime.datetime.now()]):
                            raise Exception('Failed to update roboobox is_online to 1')

                        self.logger.log(self.logger.LOG_TYPE_INFO, 'on_member_update',
                                        'Playtime modified: Roboobox is in game')
                    elif after.discriminator == self.client.enchanted_discord_id and dragon_playtime[0] == 0 and (
                            after.activity.state == "In Champion Select" or after.activity.state == "In Game"):
                        if not self.db.query_modify(
                                "UPDATE gjorfild_playtime SET is_online = 1, last_online = %s WHERE `member` = '#9101'",
                                [datetime.datetime.now()]):
                            raise Exception('Failed to update enchanted_dragon is_online to 1')

                        self.logger.log(self.logger.LOG_TYPE_INFO, 'on_member_update',
                                        'Playtime modified: EnchantedDragon is in game')
                    # Checks if sending automatic notifications is enabled
                    if notifications_enabled[0]:
                        # Checks if Roboobox or EnchantedDragon is in game from the file and if activity state is In Game
                        # Check if 60 seconds passed between displaying live game data so two requests don't get sent when both players enter the game at the same time
                        if ((after.discriminator == self.client.enchanted_discord_id and dragon_playtime[0] == 1) or (
                                after.discriminator == self.client.roboobox_discord_id and roboobox_playtime[
                            0] == 1)) and after.activity.state == "In Game" and (
                                datetime.datetime.now() - self.live_game_refreshed).total_seconds() >= 60:
                            self.live_game_refreshed = datetime.datetime.now()
                            if after.discriminator == self.client.roboobox_discord_id:
                                summoner_to_lookup = self.client.roboobox_discord_id
                            else:
                                summoner_to_lookup = self.client.enchanted_discord_id
                            self.logger.log(self.logger.LOG_TYPE_INFO, 'on_member_update', 'Player ' + str(
                                summoner_to_lookup) + ' is in game, waiting before game data retrieval')
                            # Waits a bit for game to load before checking live game data
                            time.sleep(5)
                            await self.live_game_data(summoner_to_lookup)
                # If after activity is not League of Legends then calculates playtime by subtracting start time from time right now
                # Saves millisecond value of that in file and sets that player is not in game
                elif after.activity is None or after.activity.name != "League of Legends":
                    roboobox_playtime = self.db.query_select_one(
                        "SELECT is_online, last_online, playtime_duration FROM gjorfild_playtime WHERE `member` = '#8998'")
                    dragon_playtime = self.db.query_select_one(
                        "SELECT is_online, last_online, playtime_duration FROM gjorfild_playtime WHERE `member` = '#9101'")

                    if after.discriminator == self.client.roboobox_discord_id and roboobox_playtime[0] == 1:
                        playtime_diff = datetime.datetime.now() - roboobox_playtime[1]
                        playtime_seconds = int(playtime_diff.total_seconds())

                        if not self.db.query_modify(
                                "UPDATE gjorfild_playtime SET is_online = 0, playtime_duration = %s WHERE `member` = '#8998'",
                                [(roboobox_playtime[2] + playtime_seconds)]):
                            raise Exception('Failed to update roboobox playtime')

                        self.logger.log(self.logger.LOG_TYPE_INFO, 'on_member_update',
                                        'Modifying playtime: Roboobox stopped being in game, new playtime ms: ' + str(
                                            playtime_seconds) + ' time played: ' + str(playtime_diff))
                    elif after.discriminator == self.client.enchanted_discord_id and dragon_playtime[0] == 1:
                        playtime_diff = datetime.datetime.now() - dragon_playtime[1]
                        playtime_seconds = int(playtime_diff.total_seconds())

                        if not self.db.query_modify(
                                "UPDATE gjorfild_playtime SET is_online = 0, playtime_duration = %s WHERE `member` = '#9101'",
                                [(dragon_playtime[2] + playtime_seconds)]):
                            raise Exception('Failed to update EnchantedDragon playtime')

                        self.logger.log(self.logger.LOG_TYPE_INFO, 'on_member_update',
                                        'Modifying playtime: EnchantedDragon stopped being in game, new playtime seconds: ' + str(
                                            playtime_seconds) + ' time played: ' + str(playtime_diff))
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'on_member_update', str(e))

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        try:
            if user.bot:
                pass
            elif len(reaction.message.embeds) > 0 and reaction.message.embeds[0].title == "Team 2:":
                reaction_options = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
                command = reaction.emoji
                i = 1
                if command == '🤝':
                    await self.premades(reaction.message.channel)
                else:
                    for option in reaction_options:
                        if option == command:
                            await self.match_summoner(reaction.message.channel, i)
                            break
                        i += 1
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'on_reaction_add',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    async def determine_queue(self, queue_id):
        if queue_id == 400:
            return "Draft"
        elif queue_id == 420:
            return "Ranked"
        elif queue_id == 430:
            return "Norm"
        elif queue_id == 440:
            return "Flex"
        elif queue_id == 700:
            return "Clash"
        elif queue_id == 450:
            return "Aram"
        elif queue_id == 900:
            return "URF"
        elif queue_id == 1400:
            return "Spellbook"
        elif queue_id == 1300:
            return "Blitz"
        elif queue_id == 1020:
            return "OFA"
        else:
            return "Unknown"

    async def determine_rank(self, tier):
        emoji = get(self.client.get_guild(505410172265562123).emojis, name=tier.lower())
        if emoji is not None:
            return str(emoji)
        return ""

    async def get_champion_emoji(self, champion_id):
        champion_emoji_guilds = [806602174700191754, 926269709844906074, 926270216386797588, 926270803182514248]
        for i in champion_emoji_guilds:
            emoji = discord.utils.get(self.client.get_guild(i).emojis, name=champion_id)
            if emoji is not None:
                return str(emoji)
        unknown_emoji = discord.utils.get(self.client.get_guild(926270803182514248).emojis, name="Unknown")
        if unknown_emoji is not None:
            return str(unknown_emoji)
        return ""

    async def get_position_emoji(self, position_name):
        # 806602174700191754 - Dev 2 server
        emoji = discord.utils.get(self.client.get_guild(806602174700191754).emojis, name=position_name.lower())
        if emoji is not None:
            return emoji
        return ""

    async def get_league_champion(self, champion_key):
        try:
            if self.client.dd_newest_version == "" or (
                    datetime.datetime.now() - self.client.last_version_check).total_seconds() >= 86400:
                self.logger.log(self.logger.self.logger.LOG_TYPE_INFO, 'get_league_champions',
                                'Checking for resource updates!')
                await self.client.get_cog('LeagueVersion').resource_version_check()
            return self.client.league_champions.get(int(champion_key))
        except Exception as e:
            self.logger.log(self.logger.self.logger.LOG_TYPE_ERROR, 'get_league_champion',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    @commands.command(aliases=['notifications'])
    async def autogamedata(self, ctx):
        try:
            notifications_enabled = self.db.query_select_one(
                "SELECT notifications_enabled FROM gjorfild_settings LIMIT 1")
            if not notifications_enabled:
                raise Exception('Failed to check if notifications are enabled')

            final_value = notifications_enabled[0]

            if not notifications_enabled[0]:
                if not self.db.query_modify("UPDATE gjorfild_settings SET notifications_enabled = 1"):
                    raise Exception('Failed to update notifications to enabled')
                final_value = 1
                await ctx.send("Live game data enabled :white_check_mark:")
            elif notifications_enabled[0]:
                if not self.db.query_modify("UPDATE gjorfild_Settings SET notifications_enabled = 0"):
                    raise Exception('Failed to update notifications to disabled')
                final_value = 0
                await ctx.send("Live game data disabled :no_entry_sign:")
            self.logger.log(self.logger.LOG_TYPE_INFO, 'autogamedata_command',
                            'Live game data value changed to ' + str(final_value))
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'autogamedata', str(e))

    async def live_game_data(self, player_id):
        try:
            if player_id == self.client.roboobox_discord_id:
                # Channel garmik-lolmatch
                await self.get_league_spectator_data(self.client.roboobox_summoner_name,
                                                     self.client.get_channel(808040232162295849),
                                                     error_response_enabled=False)
            elif player_id == self.client.enchanted_discord_id:
                # Channel garmik-lolmatch
                await self.get_league_spectator_data(self.client.enchanted_summoner_name,
                                                     self.client.get_channel(808040232162295849),
                                                     error_response_enabled=False)
            else:
                self.logger.log(self.logger.LOG_TYPE_ERROR, 'live_game_data',
                                'Trying to get game data for incorrect player id: ' + str(player_id))
                return []
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'live_game_data',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    async def gather_match_data(self):
        try:
            for summoner in self.last_game_summoners:
                summoner.matches = await self.get_summoner_match_data(await self.get_summoner_match_ids(summoner.puuid))
            self.last_game_data_gathered = True
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'gather_match_data',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    async def get_league_spectator_data(self, summoner_name, response_channel, error_response_enabled=True):
        try:
            if len(summoner_name) > 0:
                if isinstance(summoner_name, list) or isinstance(summoner_name, tuple):
                    summoner_name = "%20".join(summoner_name)
                url = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/by-name/" + str(
                    summoner_name) + "?api_key=" + self.api_key
                page = urllib.request.urlopen(url)
                summoner_data = json.loads(page.read().decode())
                page.close()
                RiotApiLogger(self.logger).log("SUMMONER-V4", "get_league_spectator_data", summoner_data)
                if len(summoner_data) > 0 and "status" not in summoner_data:
                    summoner = Summoner()
                    summoner.set_summoner_id(summoner_data['id'])

                    try:
                        url = "https://eun1.api.riotgames.com/lol/spectator/v4/active-games/by-summoner/" + summoner.summoner_id + "?api_key=" + self.api_key
                        page = urllib.request.urlopen(url)
                        live_match_data = json.loads(page.read().decode())
                        # Log spectator API data to database
                        is_live_game = not error_response_enabled
                        spec_db = SpectatorDatabase(live_match_data, is_live_game, self.logger)
                        RiotApiLogger(self.logger).log("SPECTATOR-V4", "get_league_spectator_data", live_match_data)
                    except Exception as e:
                        if error_response_enabled:
                            embed_msg = discord.Embed(title=":x: Summoner is not in an active game! :x:",
                                                      color=15105570)
                            embed_msg.set_footer(text="Try again later.")
                            await response_channel.send(embed=embed_msg)
                        else:
                            self.logger.log(self.logger.LOG_TYPE_INFO, 'get_league_spectator_data',
                                            'Error response suppressed: Summoner ' + str(
                                                summoner_name) + ' is not in an active game!')
                        return

                    game_summoners = []
                    embed_msg = discord.Embed(title="Team 1:", color=3447003)
                    second_msg = None
                    embed_champions = ""
                    embed_rank = ""
                    embed_winrate = ""
                    embed_footer = ""

                    player_nr = 1
                    map_id = live_match_data['mapId']
                    participant_summoners = live_match_data['participants']
                    self.last_game_champions.clear()

                    # Get participant LEAGUE (tier) data with async API requests
                    participant_league_lookup_urls = []
                    for participant in participant_summoners:
                        url = "https://eun1.api.riotgames.com/lol/league/v4/entries/by-summoner/" + participant[
                            'summonerId'] + "?api_key=" + self.api_key
                        participant_league_lookup_urls.append(url)
                    participant_leagues_json = await self.multi_url_api_request(participant_league_lookup_urls,
                                                                                "LEAGUE-V4",
                                                                                'get_league_spectator_data')
                    if len(participant_leagues_json) < 10:
                        raise Exception(
                            'Failed to collect all player league data, collected ' + str(len(participant_leagues_json)))
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'get_league_spectator_data',
                                    'Match summoner league data gathered!')

                    for participant in participant_summoners:
                        participant_summoner = Summoner()
                        participant_summoner.set_name(participant['summonerName'])
                        participant_summoner.set_summoner_id(participant['summonerId'])
                        participant_summoner.set_profile_icon(participant['profileIconId'])
                        game_summoners.append(participant_summoner)

                        # Get live match data

                        # Get champion and its emoji
                        match_champion = await self.get_league_champion(participant['championId'])
                        participant_summoner.set_champion(match_champion)

                        champion_emoji = await self.get_champion_emoji(match_champion.get_id_name())

                        self.last_game_champions[participant_summoner.summoner_id] = match_champion
                        embed_champions += champion_emoji + " " + str(player_nr) + '. ' + str(
                            match_champion.get_name()) + "\n"

                        # Get summoner rank
                        try:
                            # Get league data from previous async requests
                            league_data = participant_leagues_json[player_nr - 1]
                            spec_db.add_leagues(league_data, player_nr - 1)

                            data = None
                            for league in league_data:
                                if league['queueType'] == 'RANKED_SOLO_5x5' or "RANKED_SOLO" in league['queueType']:
                                    data = league
                                    break
                            if data is not None:
                                embed_rank += await self.determine_rank(data['tier']) + " " + data['tier'] + " " + data[
                                    'rank'] + " (" + str(data['leaguePoints']) + "LP)" + "\n"
                                embed_winrate += str(
                                    int((data['wins'] / (data['losses'] + data['wins'])) * 100)) + "% (W" + str(
                                    data['wins']) + " : " + str(data['losses']) + "L)" + "\n"
                            else:
                                embed_rank += ":black_medium_small_square: UNRANKED\n"
                                embed_winrate += "UNRANKED\n"
                        except Exception as e:
                            self.logger.log(self.logger.LOG_TYPE_ERROR, 'spectate',
                                            'Failed to lookup summoner ' + participant_summoner.name + ' league data. Exception: ' + str(
                                                e))
                            embed_rank += ":black_medium_small_square: UNRANKED**?**\n"
                            embed_winrate += "UNRANKED**?**\n"

                        # Create embed footer with nickname and player number
                        embed_footer += str(match_champion.get_name()) + " - " + participant_summoner.name + " (" + str(
                            player_nr) + ") | "

                        if player_nr == 5 or player_nr == 10:
                            embed_msg.add_field(name="Champions", value=embed_champions)
                            embed_msg.add_field(name="Rank", value=embed_rank)
                            embed_msg.add_field(name="Winrate", value=embed_winrate)
                            embed_msg.set_footer(text=embed_footer)
                            if player_nr == 5:
                                # Set map name and icon to embed message
                                file = None
                                if map_id == 11:
                                    file = discord.File("assets/images/sr.png", filename="sr.png")
                                    embed_msg.set_author(name="Summoner's Rift", icon_url="attachment://sr.png")
                                elif map_id == 12:
                                    file = discord.File("assets/images/aram.png", filename="aram.png")
                                    embed_msg.set_author(name="Howling Abyss", icon_url="attachment://aram.png")
                                if file is not None:
                                    await response_channel.send(embed=embed_msg, file=file)
                                else:
                                    await response_channel.send(embed=embed_msg)
                                # Create new embed message for second team
                                embed_msg = discord.Embed(title="Team 2:", color=15158332)
                            elif player_nr == 10:
                                second_msg = await response_channel.send(embed=embed_msg)
                            embed_champions = ""
                            embed_rank = ""
                            embed_winrate = ""
                            embed_footer = ""
                        player_nr += 1

                    self.last_game_data_gathered = False
                    self.last_game_summoners = game_summoners

                    # Collect summoners puuid, account id and summoner level
                    # Get participant data with async requests
                    participant_lookup_urls = []
                    for participant in participant_summoners:
                        url = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/" + participant[
                            'summonerId'] + "?api_key=" + self.api_key
                        participant_lookup_urls.append(url)
                    participant_summoners_json = await self.multi_url_api_request(participant_lookup_urls,
                                                                                  "SUMMONER-V4",
                                                                                  "get_league_spectator_data")

                    if len(participant_summoners_json) < 10:
                        raise Exception('Failed to collect all player summoner data, collected ' + str(
                            len(participant_summoners_json)))
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'get_league_spectator_data',
                                    'Match summoner additional data gathered!')
                    i = 0
                    for participant in participant_summoners_json:
                        summoner = game_summoners[i]
                        summoner.set_puuid(participant['puuid'])
                        summoner.set_account_id(participant['accountId'])
                        summoner.set_summoner_level(participant['summonerLevel'])
                        spec_db.add_participant_data(participant, i)
                        i += 1

                    spec_db.close()
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'get_league_spectator_data',
                                    'Starting match data gather!')

                    await self.gather_match_data()
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'get_league_spectator_data',
                                    'Match data gather completed! Adding reactions')
                    if second_msg is not None:
                        reaction_options = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟', '🤝']
                        for reaction in reaction_options:
                            await second_msg.add_reaction(reaction)
                else:
                    if error_response_enabled:
                        embed_msg = discord.Embed(title=":x: Summoner not found! :x:", color=15105570)
                        await response_channel.send(embed=embed_msg)
                    else:
                        self.logger.log(self.logger.LOG_TYPE_INFO, 'get_league_spectator_data',
                                        'Error response suppressed: Summoner ' + str(summoner_name) + ' not found!')

        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_league_spectator_data',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="Something went wrong while getting game data! :x::pensive:",
                                      color=15105570)
            await response_channel.send(embed=embed_msg)

    @commands.command(aliases=['gg'])
    async def spectate(self, ctx, *summoner_name):
        try:
            if len(summoner_name) == 0:
                if ctx.message.author.discriminator == self.client.roboobox_discord_id:
                    await self.get_league_spectator_data(self.client.roboobox_summoner_name, ctx)
                elif ctx.message.author.discriminator == self.client.enchanted_discord_id:
                    await self.get_league_spectator_data(self.client.enchanted_summoner_name, ctx)
                else:
                    embed_msg = discord.Embed(title="", description="Summoner name is required! :x:",
                                              color=self.client.embed_error)
            else:
                await self.get_league_spectator_data(summoner_name, ctx)
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'spectate',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))
            embed_msg = discord.Embed(title="Something went wrong while getting spectate data! :x::pensive:",
                                      color=15105570)
            await ctx.send(embed=embed_msg)

    async def get_summoner_match_ids(self, summoner_puuid: str, match_start_index: int = 0, match_count: int = 4):
        try:
            try:
                url = "https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/" + summoner_puuid + "/ids?start=" + str(
                    match_start_index) + "&count=" + str(match_count) + "&api_key=" + self.api_key
                page = urllib.request.urlopen(url)
                match_data = json.loads(page.read().decode())
                RiotApiLogger(self.logger).log("MATCH-V5", "get_summoner_match_ids", match_data)
            except Exception as e:
                self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_summoner_match_ids',
                                'Failed to get match data for puuid ' + str(summoner_puuid) + ' Exception:' + str(e))
                return []
            match_ids = []
            for match_id in match_data:
                match_ids.append(match_id)
            if len(match_ids) == 0:
                self.logger.log(self.logger.LOG_TYPE_INFO, 'get_summoner_match_ids',
                                'Did not find any matches for summoner PUUID: ' + str(summoner_puuid))
            return match_ids

        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_summoner_match_ids',
                            'Failed to get match ID data, Exception:' + str(e) + ' Traceback: ' + str(
                                traceback.format_exc()))
            return []

    async def get_summoner_match_data(self, match_ids: list):
        try:
            if len(match_ids) < 1:
                return []
            matches = []
            match_urls = []
            responses = []
            for match_id in match_ids:
                match_urls.append(
                    "https://europe.api.riotgames.com/lol/match/v5/matches/" + str(
                        match_id) + "?api_key=" + self.api_key)
            try:
                async with aiohttp.ClientSession() as session:
                    for url in match_urls:
                        async with session.get(url) as resp:
                            responses.append(await resp.json())
            except Exception as e:
                self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_summoner_match_data',
                                'Failed to get batch match data, Exception:' + str(e))
                return []
            for r in responses:
                if "status" not in r:
                    matches.append(Match(r))
            # RiotApiLogger(logger).log_multiple("MATCH-V5", "get_summoner_match_data", responses)
            return matches
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_summoner_match_data',
                            'Failed to get match data, Exception:' + str(e) + ' Traceback: ' + str(
                                traceback.format_exc()))
            return []

    async def multi_url_api_request(self, urls: list, api_endpoint: str, log_function_name: str):
        try:
            api_responses = []
            async with aiohttp.ClientSession() as session:
                for url in urls:
                    async with session.get(url) as resp:
                        json_response = await resp.json()
                        api_responses.append(json_response)
                        RiotApiLogger(self.logger).log(api_endpoint, log_function_name, json_response)
            return api_responses
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'multi_url_api_request', 'Exception:' + str(e))
            return []

    # Command for getting chosen summoner match history stats
    @commands.command(aliases=['gd'])
    async def match_summoner(self, ctx, summoner_number: int):
        try:
            summoner = self.last_game_summoners[summoner_number - 1]
            champion = summoner.champion

            if len(summoner.matches) < 1:
                embed_msg = discord.Embed(title="Not enough data for this summoner! :x::pensive:", color=15105570)
                await ctx.send(embed=embed_msg)
                return
            additional_match_ids = await self.get_summoner_match_ids(summoner.puuid, 5, 5)
            additional_matches = await self.get_summoner_match_data(additional_match_ids)
            for match in additional_matches:
                summoner.matches.append(match)

            # Data collection
            summoner_match_data = []
            for match in summoner.matches:
                summoner_participant = None
                for participant in match.participants:
                    if participant['puuid'] == summoner.puuid:
                        summoner_participant = participant
                        break
                if summoner_participant is None:
                    raise Exception(
                        'Summoner ' + summoner.name + ' was not found in match ' + match.matchId + ' participants')
                summoner_match_data.append(SummonerMatch(summoner_participant, match))

            match_champions = []
            match_roles = []
            champion_data_embed = ""
            kda_embed = ""
            additional_info_embed = ""
            for summoner_match in summoner_match_data:
                summoner_champion = await self.get_league_champion(summoner_match.championId)
                match_champions.append(summoner_champion.get_key())
                if summoner_match.position is not None and summoner_match.position != "":
                    match_roles.append(summoner_match.position)
                champion_emoji = await self.get_champion_emoji(summoner_champion.get_id_name())
                champion_data_embed += summoner_match.get_champion_info(champion_emoji) + "\n"
                kda_embed += summoner_match.get_kda() + "\n"
                additional_info_embed += str(summoner_match.get_additional_summary()) + " | " + str(
                    await self.determine_queue(summoner_match.matchObject.queueId)) + ":" + str(
                    await self.get_position_emoji(summoner_match.position)) + "\n"
            most_played_champion = max(set(match_champions), key=match_champions.count, default="Unknown")
            most_played_role = max(set(match_roles), key=match_roles.count, default="Unknown")

            most_played_champion_string = most_played_role_string = "Unknown"
            most_played_champion_title = "Most played champion:\n"
            most_played_role_title = "Most played role:\n"
            if most_played_champion != "Unknown":
                champion_played_times = match_champions.count(most_played_champion)
                # Get champion object
                most_played_champion = await self.get_league_champion(most_played_champion)
                most_played_champion_string = (await self.get_champion_emoji(
                    most_played_champion.get_id_name())) + " " + most_played_champion.get_name()
                most_played_champion_title = "Most played champion (*" + str(champion_played_times) + " of " + str(
                    len(summoner_match_data)) + " matches*):\n"
            if most_played_role != "Unknown":
                role_played_time = match_roles.count(most_played_role)
                most_played_role_string = str(
                    await self.get_position_emoji(most_played_role)) + " " + most_played_role.title()
                most_played_role_title = "Most played role (*" + str(role_played_time) + " of " + str(
                    len(summoner_match_data)) + " matches*):\n"

            embed_msg = discord.Embed(color=3066993, description="*Currently playing:* " + (
                await self.get_champion_emoji(champion.get_id_name())) + " *" + str(champion.get_name()) + "*")
            embed_msg.set_author(name=str(summoner.name), icon_url="http://ddragon.leagueoflegends.com/cdn/" + str(
                self.client.dd_newest_version) + "/img/profileicon/" + str(summoner.profile_icon_id) + ".png")
            embed_msg.add_field(name=most_played_role_title, value=most_played_role_string, inline=True)
            embed_msg.add_field(name=most_played_champion_title, value=most_played_champion_string, inline=False)
            embed_msg.add_field(name="Champion", value=champion_data_embed, inline=True)
            embed_msg.add_field(name="KDA", value=kda_embed)
            embed_msg.add_field(name="Additional information", value=additional_info_embed)
            await ctx.send(embed=embed_msg)

        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'match_data', str(e))
            embed_msg = discord.Embed(title="Something went wrong while getting data! :x::pensive:", color=15105570)
            await ctx.send(embed=embed_msg)

    @commands.command()
    async def premades(self, ctx):
        try:
            embed_content = ""
            embed_msg = discord.Embed(title="Match premades:", color=15105570)
            embed_summoner = ""
            embed_premades = ""
            if self.last_game_data_gathered:
                summoners_checked = []
                for summ in self.last_game_summoners:
                    if summ.name not in summoners_checked:
                        match_premades = summ.get_premades(self.last_game_summoners)
                        self.logger.log(self.logger.LOG_TYPE_INFO, 'premades',
                                        "Premade request result: " + str(match_premades))
                        summoners_checked.append(summ.name)
                        summoners_checked = summoners_checked + match_premades[0]
                        match_premades = match_premades[1]
                        embed_summoner = embed_summoner + "*" + summ.champion.get_name() + "*\n"
                        if len(match_premades) > 0:
                            embed_premades = embed_premades + (" **║** ".join(match_premades)) + "\n"
                        else:
                            embed_premades = embed_premades + "None\n"
                        # embed_content += summ.name + " - " + " - ".join(match_premades) + "\n\n"

                embed_msg.add_field(name="Champion", value=embed_summoner)
                embed_msg.add_field(name="Premades", value=embed_premades)
                await ctx.send(embed=embed_msg)
            else:
                embed_msg = discord.Embed(title="Match data not yet available! :x:", color=15105570)
                embed_msg.set_footer(text="Perhaps try a bit later.")
                await ctx.send(embed=embed_msg)
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'premades',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    @commands.command()
    async def summoner(self, ctx, *summoner_name):
        try:
            if len(summoner_name) > 0:
                summoner_name = " ".join(summoner_name)
                if ctx.message.author.discriminator == self.client.roboobox_discord_id:
                    self.client.roboobox_summoner_name = summoner_name.replace(" ", "%20")
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'summoner',
                                    "Roboobox summoner name changed to " + str(summoner_name))
                elif ctx.message.author.discriminator == self.client.enchanted_discord_id:
                    self.client.enchanted_summoner_name = summoner_name.replace(" ", "%20")
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'summoner',
                                    "EnchantedDragon summoner name changed to " + str(summoner_name))
                await self.client.get_cog('LeagueVersion').id_update_check()
                await ctx.message.add_reaction('✅')
            else:
                embed_msg = discord.Embed(title="", description="New summoner name is required! :x:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)
        except Exception as e:
            embed_msg = discord.Embed(title="", description="Unable to change summoner name! :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'summoner',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    @commands.command()
    async def summoners(self, ctx, *summoner_names):
        try:
            if len(summoner_names) > 1:
                summoner_names = " ".join(summoner_names)
                summoner_names = summoner_names.split(",")
                if len(summoner_names) == 2:
                    self.client.roboobox_summoner_name = summoner_names[0].replace(" ", "%20")
                    self.client.enchanted_summoner_name = summoner_names[1].replace(" ", "%20")
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'summoners',
                                    "Summoner names changed to " + str(
                                        self.client.roboobox_summoner_name) + " and " + str(
                                        self.client.enchanted_summoner_name))
                    await self.client.get_cog('LeagueVersion').id_update_check()
                    await ctx.message.add_reaction('✅')
                else:
                    embed_msg = discord.Embed(title="", description="Both summoner names are required! :x:",
                                              color=self.client.embed_error)
                    await ctx.send(embed=embed_msg)
            else:
                embed_msg = discord.Embed(title="", description="Both summoner names are required! :x:",
                                          color=self.client.embed_error)
                await ctx.send(embed=embed_msg)
        except Exception as e:
            embed_msg = discord.Embed(title="", description="Unable to change summoners! :pensive:",
                                      color=self.client.embed_error)
            await ctx.send(embed=embed_msg)
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'summoners',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))


def setup(client):
    client.add_cog(LeagueMatch(client))
