#!/usr/bin/python3

import discord
import requests
from discord.ext import commands
import random
import difflib
import urllib.request
import json
import aiohttp
import traceback
import config.config as config
import config.database as config_db

# import logging
from logger.CustomLog import *
from classes.Database import Database
from classes.SpectatorDatabase import SpectatorDatabase
from classes.RiotApiLogger import RiotApiLogger
# import summoner class
from classes.Summoner import Summoner
from classes.Match import Match
from classes.SummonerMatch import SummonerMatch
from classes.Champion import Champion
import datetime
import time
import mysql.connector
from bs4 import BeautifulSoup

from classes.pmlp.Pmlp import Pmlp

LOG_TYPE_INFO = 'info'
LOG_TYPE_ERROR = 'error'

pmlp_notif_enabled = True
new_rank_icons_enabled = True
last_game_account_ids = []
last_game_summoners = []
last_game_data_gathered = False
last_game_data_gathered = False
last_game_champion_ids = []
last_game_champions = {}
last_version_check = datetime.datetime.now()
live_game_refreshed = datetime.datetime.now()
league_champions = []
game_champions = []
game_champion_ids = []
game_champion_keys = []
dd_newest_version = ""

intents = discord.Intents().all()
command_prefix = '!'
client = commands.Bot(command_prefix=command_prefix, help_command=None, intents=intents)

database = mysql.connector.connect(
  host=config_db.database['host'],
  user=config_db.database['user'],
  password=config_db.database['password'],
  database=config_db.database['database']
)

db = Database(database)
logger = Log(database)

@client.event
async def on_ready():
    global activity_task
    await resource_version_check()
    await id_update_check()
    await schedule_pmlp_check()
    # await create_mood_message(client.get_channel(815994895402795048), True)
    logger.log(LOG_TYPE_INFO, 'on_ready', 'Bot is ready!')


async def resource_version_check():
    # Opens page which contains all (patch) versions
    versions_page = urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json")
    versions = json.loads(versions_page.read().decode())
    global dd_newest_version, last_version_check, league_champions
    # Selects newest version which is first
    dd_newest_version = versions[0]
    # Saves update time as time right now
    last_version_check = datetime.datetime.now()

    # Gets league champion objects and game_champions array with only champion formatted names
    league_champions = await get_all_champions()

    logger.log(LOG_TYPE_INFO, 'resource_version_check', 'Version check completed! Version: ' + str(dd_newest_version))


async def id_update_check():
    try:
        global enchanted_id, enchanted_account_id, roboobox_id, roboobox_account_id

        url_enchanted = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/by-name/" + enchanted_summoner_name + "?api_key=" + api_key
        url_robo = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/by-name/" + roboobox_summoner_name + "?api_key=" + api_key

        page = urllib.request.urlopen(url_enchanted)
        j = json.loads(page.read().decode())
        enchanted_id = j['id']
        enchanted_account_id = j['accountId']

        page = urllib.request.urlopen(url_robo)
        j = json.loads(page.read().decode())
        roboobox_id = j['id']
        roboobox_account_id = j['accountId']

        logger.log(LOG_TYPE_INFO, 'id_update_check', 'Summoner ID check completed!  New Robo ID:' + roboobox_id + ', new Enchanted ID:' + enchanted_id)
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'id_update_check', str(e))


@client.event
async def on_member_update(before, after):
    try:
        file_data = []
        # Checks if before and after activity is not the same and if activity user ir Roboobox or Enchanted dragon (by discriminator)
        if before.activity != after.activity and (before.discriminator == roboobox_discord_id or before.discriminator == enchanted_discord_id):
            # Checks if new activity is League of Legends
            if after.activity is not None and after.activity.name == "League of Legends":
                # Reads playtime file data and saves lines in file_data variable
                roboobox_playtime = db.query_select_one("SELECT is_online, last_online FROM gjorfild_playtime WHERE `member` = '#8998'")
                dragon_playtime = db.query_select_one("SELECT is_online, last_online FROM gjorfild_playtime WHERE `member` = '#9101'")
                notifications_enabled = db.query_select_one("SELECT notifications_enabled FROM gjorfild_settings LIMIT 1")
                if not roboobox_playtime or not roboobox_playtime or not notifications_enabled:
                    raise Exception('Failed to get playtime data from database')

                # Checks if activity user ir EnchantedDragon or Roboobox and if playtime file indicated that user is not in game then updates game start
                # time and sets in game value as true, writes updated file_data to file
                if after.discriminator == roboobox_discord_id and roboobox_playtime[0] == 0 and (after.activity.state == "In Champion Select" or after.activity.state == "In Game"):
                    if not db.query_modify("UPDATE gjorfild_playtime SET is_online = 1, last_online = %s WHERE `member` = '#8998'", [datetime.datetime.now()]):
                        raise Exception('Failed to update roboobox is_online to 1')

                    logger.log(LOG_TYPE_INFO, 'on_member_update', 'Playtime modified: Roboobox is in game')
                elif after.discriminator == enchanted_discord_id and dragon_playtime[0] == 0 and (after.activity.state == "In Champion Select" or after.activity.state == "In Game"):
                    if not db.query_modify("UPDATE gjorfild_playtime SET is_online = 1, last_online = %s WHERE `member` = '#9101'", [datetime.datetime.now()]):
                        raise Exception('Failed to update enchanted_dragon is_online to 1')

                    logger.log(LOG_TYPE_INFO, 'on_member_update', 'Playtime modified: EnchantedDragon is in game')
                # Checks if sending automatic notifications is enabled
                if notifications_enabled[0]:
                    global live_game_refreshed
                    # Checks if Roboobox or EnchantedDragon is in game from the file and if activity state is In Game
                    # Check if 60 seconds passed between displaying live game data so two requests don't get sent when both players enter the game at the same time
                    if ((after.discriminator == enchanted_discord_id and dragon_playtime[0] == 1) or (after.discriminator == roboobox_discord_id and roboobox_playtime[0] == 1)) and after.activity.state == "In Game" and (datetime.datetime.now() - live_game_refreshed).total_seconds() >= 60:
                        live_game_refreshed = datetime.datetime.now()
                        if after.discriminator == roboobox_discord_id:
                            summoner_to_lookup = roboobox_discord_id
                        else:
                            summoner_to_lookup = enchanted_discord_id
                        logger.log(LOG_TYPE_INFO, 'on_member_update', 'Player ' + str(summoner_to_lookup) + ' is in game, waiting before game data retrieval')
                        # Waits a bit for game to load before checking live game data
                        time.sleep(5)
                        await live_game_data(summoner_to_lookup)
            # If after activity is not League of Legends then calculates playtime by subtracting start time from time right now
            # Saves millisecond value of that in file and sets that player is not in game
            elif after.activity is None or after.activity.name != "League of Legends":
                roboobox_playtime = db.query_select_one("SELECT is_online, last_online, playtime_duration FROM gjorfild_playtime WHERE `member` = '#8998'")
                dragon_playtime = db.query_select_one("SELECT is_online, last_online, playtime_duration FROM gjorfild_playtime WHERE `member` = '#9101'")

                if after.discriminator == roboobox_discord_id and roboobox_playtime[0] == 1:
                    playtime_diff = datetime.datetime.now() - roboobox_playtime[1]
                    playtime_seconds = int(playtime_diff.total_seconds())

                    if not db.query_modify("UPDATE gjorfild_playtime SET is_online = 0, playtime_duration = %s WHERE `member` = '#8998'", [(roboobox_playtime[2] + playtime_seconds)]):
                        raise Exception('Failed to update roboobox playtime')

                    logger.log(LOG_TYPE_INFO, 'on_member_update', 'Modifying playtime: Roboobox stopped being in game, new playtime ms: ' + str(playtime_seconds) + ' time played: ' + str(playtime_diff) )
                elif after.discriminator == enchanted_discord_id and dragon_playtime[0] == 1:
                    playtime_diff = datetime.datetime.now() - dragon_playtime[1]
                    playtime_seconds = int(playtime_diff.total_seconds())

                    if not db.query_modify("UPDATE gjorfild_playtime SET is_online = 0, playtime_duration = %s WHERE `member` = '#9101'", [(dragon_playtime[2] + playtime_seconds)]):
                        raise Exception('Failed to update EnchantedDragon playtime')

                    logger.log(LOG_TYPE_INFO, 'on_member_update', 'Modifying playtime: EnchantedDragon stopped being in game, new playtime seconds: ' + str(playtime_seconds) + ' time played: ' + str(playtime_diff))
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'on_member_update', str(e))


@client.command(pass_context=True)
async def playtime(ctx):
    try:
        # Checks if message author is Roboobox or EnchantedDragon
        if ctx.message.author.discriminator == roboobox_discord_id or ctx.message.author.discriminator == enchanted_discord_id:
            played_secs = 0
            # Selects ms field based on user which requested command and uses rstrip to remove newline char from line and then converts to int
            if ctx.message.author.discriminator == roboobox_discord_id:
                played_secs = db.query_select_one("SELECT playtime_duration FROM gjorfild_playtime WHERE `member` = '#8998'")[0]
            elif ctx.message.author.discriminator == enchanted_discord_id:
                played_secs = db.query_select_one("SELECT playtime_duration FROM gjorfild_playtime WHERE `member` = '#9101'")[0]

            hours = played_secs // 3600
            minutes = (played_secs - (hours * 3600)) // 60
            seconds = (played_secs - hours * 3600 - minutes * 60)
            message = "Your playtime is " + str(hours) + (" hour, " if hours == 1 else " hours, ") + str(minutes) + (" minute and " if minutes == 1 else " minutes and ") + str(seconds) + (" second" if seconds == 1 else " seconds")
            embed_msg = discord.Embed(description=message, color=3447003)
            embed_msg.set_author(icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/5/53/Riot_Games_logo_icon.png/revision/latest/scale-to-width-down/124?cb=20190417213704", name="League of Legends")
            await ctx.send(embed=embed_msg)
        else:
            logger.log(LOG_TYPE_ERROR, 'playtime_command', 'Wrong author discriminator: ' + str(ctx.message.author.discriminator))
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'playtime', str(e))


async def get_closest_champion(champion: str):
    try:
        if len(champion) > 0:
            closest_champion_winner = ""
            closest_champions = difflib.get_close_matches(champion.lower().replace(" ", ""), game_champions, n=3,
                                                          cutoff=0.4)
            if len(closest_champions) > 0:
                logger.log(LOG_TYPE_INFO, 'get_closest_champion',
                           'Closest champions found for (' + champion + ') are ' + str(closest_champions))

                for close_champion in closest_champions:
                    if close_champion.startswith(champion.lower().replace(" ", "")):
                        closest_champion_winner = close_champion
                        break
                if closest_champion_winner == "":
                    closest_champion_winner = closest_champions[0]
                print(closest_champion_winner)
                logger.log(LOG_TYPE_INFO, 'get_closest_champion','Closest champion found as ' + str(closest_champion_winner))
                return closest_champion_winner
            else:
                return ""
        else:
            return ""
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'get_closest_champion', str(e))


@client.command(aliases=['spellbook'])
async def ult(ctx, *champion):
    try:
        if len(champion) > 0:
            champion = " ".join(champion)
            closest_champion = (await get_closest_champion(champion)).lower()
            if len(closest_champion) > 0:
                await ctx.send("https://www.metasrc.com/ultbook/champion/" + closest_champion)
            else:
                await ctx.send(":exclamation:Champion was not found :pensive::exclamation:")
        else:
            await ctx.send("You forgot to specify champion name :pensive::exclamation:")
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'ult', str(e))


@client.command()
async def ping(ctx):
    await ctx.send('Pong! {}'.format(round(client.latency * 1000)))


@client.command(aliases=['aram'])
async def a(ctx, *arg):
    try:
        # Checks if there are passed arguments
        if len(arg) > 0:
            # Joins arguments for creating a link and makes it lowercase, uses champion name guessing
            champion_to_check = (await get_closest_champion(" ".join(arg))).lower()
            if champion_to_check != "":
                # Gets ARAM champion page data
                aram_url = "https://www.metasrc.com/aram/na/champion/"+champion_to_check
                page = requests.get(aram_url, allow_redirects=False)
                # Checks if there was no redirection which would mean that passed champion was not found
                if page.status_code != 301:
                    soup = BeautifulSoup(page.text, 'lxml')
                    page.close()

                    cnt = 1
                    i = 0
                    embed_s = discord.Embed(color=9807270)
                    # Selects rune image tags from html
                    rune_data = soup.select('div._sfh2p9 svg image')
                    logger.log(LOG_TYPE_INFO, 'a_command', 'Rune data found: ')
                    for link in rune_data:
                        # Creates embeds runes
                        if "communitydragon" in link['data-xlink-href'] and i < 8:
                            # Puts two images in one embed with help of cnt
                            if cnt == 1:
                                # Decides embed color based on rune type
                                if "domination" in link['data-xlink-href']:
                                    embed_s = discord.Embed(color=15158332)
                                elif "precision" in link['data-xlink-href']:
                                    embed_s = discord.Embed(color=12745742)
                                elif "sorcery" in link['data-xlink-href']:
                                    embed_s = discord.Embed(color=10181046)
                                elif "resolve" in link['data-xlink-href']:
                                    embed_s = discord.Embed(color=3066993)
                                elif "inspiration" in link['data-xlink-href']:
                                    embed_s = discord.Embed(color=3447003)
                                embed_s.set_author(name="Rune", icon_url=link['data-xlink-href'])
                                cnt += 1
                            elif cnt == 2:
                                embed_s.set_footer(text="Rune", icon_url=link['data-xlink-href'])
                                await ctx.send(embed=embed_s)
                                # If all runes have been sent as embeds, sends final message which contains three symbols of rune shards
                                if i == 7:
                                    await ctx.send(str(await decide_symbol(rune_data[i+1]['data-xlink-href']) + " | " + await decide_symbol(rune_data[i+2]['data-xlink-href']) + " | " + await decide_symbol(rune_data[i+3]['data-xlink-href'])))
                                cnt = 1
                        i += 1
                    # Selects img tags of summoner spells
                    spells_div = soup.select('._h8qwbj ._dcqhsp div img')
                    # Selects td tags of ability upgrade sequence
                    ability_data = soup.select('table._4pvjjd tr._eveje5 td')
                    i = 0
                    # Dictionary which contains which the final champion level that ability was upgraded
                    abilities = {"Q": 0, "W": 0, "E": 0}
                    for data in ability_data:
                        # Ignores every 19th td because it contains ability image not letter of ability
                        # Ignores td which do not contain text and R ability
                        if i % 19 != 0 and data.text != '' and data.text != 'R':
                            if i > 19:
                                # If i > 19 then subtracts value to get value below 19 | Example 29; 29-(29/19)*19 = 29-1*19 = 10
                                cnt = i - (int(i / 19)) * 19
                            else:
                                cnt = i
                            # Saves number in ability dictionary
                            abilities[data.text] = cnt
                        i += 1
                    logger.log(LOG_TYPE_INFO, 'a_command', 'Ability values found: ' + str(abilities))
                    # Sorts abilities dictionary by key so abilities are sorted by their last level upgraded which is ability upgrade order
                    abilities = sorted(abilities, key=abilities.get)
                    ability_order = ""
                    # Creates string with uprgade order
                    for ability in abilities:
                        ability_order += ability+" > "
                    # Removes last three symbols which are " > "
                    ability_order = ability_order[:-3]
                    # Selects champion image url
                    # [5:-2] to remove url(' at beginning and ') at the end
                    champion_image = soup.select_one('._40ug81 a._hmag7l')['data-background-image'][5:-2]

                    # Concatenates and sends embeds with data
                    start_items = ""
                    build_items = ""
                    spells = spells_div[0]['alt'] + "\n" + spells_div[1]['alt']
                    logger.log(LOG_TYPE_INFO, 'a_command', 'Spells found: ' + str(spells) + ', champion image found: ' + str(champion_image))
                    embed_s = discord.Embed(title="ARAM setup: " + '\n' + aram_url, color=11027200)
                    embed_s.set_thumbnail(url=champion_image)
                    for link in soup.select('div._5cna4p div._c8xw44:nth-of-type(2) div._dtoou._59r45k._dcqhsp div div img'):
                        if "ddragon" in link['data-src']:
                            start_items += link['alt'] + "\n"
                    i = 1
                    for link in soup.select('div._5cna4p div._c8xw44:nth-of-type(3) div._h8qwbj div div img'):
                        if "ddragon" in link['data-src']:
                            build_items += str(i)+". " + link['alt'] + "\n"
                            i += 1
                    embed_s.add_field(name="Starting items", value=start_items)
                    embed_s.add_field(name="Final build", value=build_items)
                    embed_s.add_field(name="Spells", value=spells)
                    embed_s.set_footer(text="Abilities: " + ability_order)
                    await ctx.send(embed=embed_s)
                else:
                    await ctx.send(":exclamation:Champion was not found :pensive::exclamation:")
            else:
                await ctx.send(":exclamation:Champion was not found :pensive::exclamation:")
        else:
            await ctx.send(":o: Please enter a champion! :o:")
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'a', str(e) + ' Traceback: ' + str(traceback.format_exc()))


async def decide_symbol(element):
    if "cdrscaling" in element:
        return ":white_circle:"
    elif "armor" in element:
        return ":red_circle:"
    elif "healthscaling" in element:
        return ":green_circle:"
    elif "adaptiveforce" in element:
        return ":large_blue_diamond:"
    elif "attackspeed" in element:
        return ":yellow_circle:"


async def decide_symbol_tft(element):
    symbol = " "
    if "chromatic" in element:
        symbol += ":purple_circle:"
    elif "gold" in element:
        symbol += ":yellow_circle:"
    elif "bronze" in element:
        symbol += ":brown_circle:"
    elif "silver" in element:
        symbol += ":white_circle:"
    if "chosen" in element:
        symbol += " :purple_square:"
    return symbol


async def determine_queue(queue_id):
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


async def determine_rank(tier):
    global new_rank_icons_enabled
    if new_rank_icons_enabled:
        return await deter_rank_new(tier)

    if tier == "SILVER":
        return ":white_circle:"
    elif tier == "GOLD":
        return ":yellow_circle:"
    elif tier == "BRONZE":
        return ":brown_circle:"
    elif tier == "PLATINUM":
        return ":green_circle:"
    elif tier == "DIAMOND":
        return ":blue_circle:"
    elif tier == "MASTER":
        return ":purple_circle:"
    elif tier == "GRANDMASTER":
        return ":red_circle:"
    elif tier == "CHALLENGER":
        return ":crown:"
    elif tier == "IRON":
        return ":wastebasket:"
    else:
        return ""


async def deter_rank_new(tier):
    emoji = get(client.get_guild(505410172265562123).emojis, name=tier.lower())
    if emoji is not None:
        return str(emoji)
    return ""


async def get_champion_emoji(champion_id):
    champion_emoji_guilds = [806602174700191754, 926269709844906074, 926270216386797588, 926270803182514248]
    for i in champion_emoji_guilds:
        emoji = discord.utils.get(client.get_guild(i).emojis, name=champion_id)
        if emoji is not None:
            return str(emoji)
    unknown_emoji = discord.utils.get(client.get_guild(926270803182514248).emojis, name="Unknown")
    if unknown_emoji is not None:
        return str(unknown_emoji)
    return ""


async def get_position_emoji(position_name):
    # 806602174700191754 - Dev 2 server
    emoji = discord.utils.get(client.get_guild(806602174700191754).emojis, name=position_name.lower())
    if emoji is not None:
        return emoji
    return ""


async def get_league_champion(champion_key):
    try:
        global dd_newest_version, league_champions
        if dd_newest_version == "" or (datetime.datetime.now() - last_version_check).total_seconds() >= 86400:
            logger.log(LOG_TYPE_INFO, 'get_league_champions', 'Checking for resource updates!')
            await resource_version_check()
        return league_champions.get(int(champion_key))
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'get_league_champion', str(e) + ' Traceback: ' + str(traceback.format_exc()))


async def get_all_champions():
    try:
        global game_champions
        champions_page = urllib.request.urlopen("http://ddragon.leagueoflegends.com/cdn/" + str(dd_newest_version) + "/data/en_US/champion.json")
        champion_json_array = json.loads(champions_page.read().decode())
        champions = {}
        game_champions = []
        for champion in champion_json_array['data']:
            # Create assoc array with champion key and champion object
            champion_json = champion_json_array['data'][champion]
            game_champions.append(champion_json['id'])
            champions[int(champion_json['key'])] = Champion(champion_json)
        logger.log(LOG_TYPE_INFO, 'get_all_champions', 'Retrieved ' + str(len(champions)) + ' champions')
        return champions
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'get_all_champions', str(e) + ' Traceback: ' + str(traceback.format_exc()))

@client.command()
async def rand(ctx, *arg):
    try:
        list_i = list(arg)
        victor = random.randint(0, len(list_i) - 1)
        await ctx.send(list_i[victor])
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'rand', str(e) + ' Traceback: ' + str(traceback.format_exc()))

@client.command()
async def randl(ctx, *arg):
    try:
        list_i = list(arg)
        random.shuffle(list_i)
        output = ""
        i = 1
        for element in list_i:
            output += str(i) + ". " + element + "\n"
            i += 1
        await ctx.send(output)
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'randl', str(e) + ' Traceback: ' + str(traceback.format_exc()))


@client.command(aliases=['notifications'])
async def autogamedata(ctx):
    try:
        notifications_enabled = db.query_select_one("SELECT notifications_enabled FROM gjorfild_settings LIMIT 1")
        if not notifications_enabled:
            raise Exception('Failed to check if notifications are enabled')

        final_value = notifications_enabled[0]

        if not notifications_enabled[0]:
            if not db.query_modify("UPDATE gjorfild_settings SET notifications_enabled = 1"):
                raise Exception('Failed to update notifications to enabled')
            final_value = 1
            await ctx.send("Live game data enabled :white_check_mark:")
        elif notifications_enabled[0]:
            if not db.query_modify("UPDATE gjorfild_Settings SET notifications_enabled = 0"):
                raise Exception('Failed to update notifications to disabled')
            final_value = 0
            await ctx.send("Live game data disabled :no_entry_sign:")
        logger.log(LOG_TYPE_INFO, 'autogamedata_command', 'Live game data value changed to ' + str(final_value))
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'autogamedata', str(e))


async def live_game_data(player_id):
    try:
        global enchanted_id, enchanted_account_id, roboobox_id, roboobox_account_id
        if player_id == roboobox_discord_id:
            # Channel garmik-lolmatch
            await get_league_spectator_data(roboobox_summoner_name, client.get_channel(808040232162295849), error_response_enabled=False)
        elif player_id == enchanted_discord_id:
            # Channel garmik-lolmatch
            await get_league_spectator_data(enchanted_summoner_name, client.get_channel(808040232162295849), error_response_enabled=False)
        else:
            logger.log(LOG_TYPE_ERROR, 'live_game_data', 'Trying to get game data for incorrect player id: ' + str(player_id))
            return []
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'live_game_data', str(e) + ' Traceback: ' + str(traceback.format_exc()))


async def gather_match_data():
    global last_game_data_gathered, last_game_summoners
    try:
        for summoner in last_game_summoners:
            summoner.matches = await get_summoner_match_data(await get_summoner_match_ids(summoner.puuid))
        last_game_data_gathered = True
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'gather_match_data', str(e) + ' Traceback: ' + str(traceback.format_exc()))

@client.command()
async def hd_rank(ctx):
    try:
        global new_rank_icons_enabled
        new_rank_icons_enabled = not new_rank_icons_enabled
        if new_rank_icons_enabled:
            await ctx.send("HD ranks enabled :white_check_mark:")
        else:
            await ctx.send("HD ranks data disabled :no_entry_sign:")
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'enable_hd_rank', str(e) + ' Traceback: ' + str(traceback.format_exc()))


async def get_league_spectator_data(summoner_name, response_channel, error_response_enabled = True):
    try:
        global last_game_summoners, last_game_data_gathered, last_game_champions
        if len(summoner_name) > 0:
            if isinstance(summoner_name, list) or isinstance(summoner_name, tuple):
                summoner_name = "%20".join(summoner_name)
            url = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/by-name/" + str(summoner_name) + "?api_key=" + api_key
            page = urllib.request.urlopen(url)
            summoner_data = json.loads(page.read().decode())
            page.close()
            RiotApiLogger(logger).log("SUMMONER-V4", "get_league_spectator_data", summoner_data)
            if len(summoner_data) > 0 and "status" not in summoner_data:
                summoner = Summoner()
                summoner.set_summoner_id(summoner_data['id'])

                try:
                    url = "https://eun1.api.riotgames.com/lol/spectator/v4/active-games/by-summoner/" + summoner.summoner_id + "?api_key=" + api_key
                    page = urllib.request.urlopen(url)
                    live_match_data = json.loads(page.read().decode())
                    # Log spectator API data to database
                    is_live_game = not error_response_enabled
                    spec_db = SpectatorDatabase(live_match_data, is_live_game, logger)
                    RiotApiLogger(logger).log("SPECTATOR-V4", "get_league_spectator_data", live_match_data)
                except Exception as e:
                    if error_response_enabled:
                        embed_msg = discord.Embed(title=":x: Summoner is not in an active game! :x:", color=15105570)
                        embed_msg.set_footer(text="Try again later.")
                        await response_channel.send(embed=embed_msg)
                    else:
                        logger.log(LOG_TYPE_INFO, 'get_league_spectator_data', 'Error response suppressed: Summoner ' + str(summoner_name) + ' is not in an active game!')
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
                last_game_champions.clear()

                # Get participant LEAGUE (tier) data with async API requests
                participant_league_lookup_urls = []
                for participant in participant_summoners:
                    url = "https://eun1.api.riotgames.com/lol/league/v4/entries/by-summoner/" + participant['summonerId'] + "?api_key=" + api_key
                    participant_league_lookup_urls.append(url)
                participant_leagues_json = await multi_url_api_request(participant_league_lookup_urls, "LEAGUE-V4", 'get_league_spectator_data')
                if len(participant_leagues_json) < 10:
                    raise Exception('Failed to collect all player league data, collected ' + str(len(participant_leagues_json)))
                logger.log(LOG_TYPE_INFO, 'get_league_spectator_data', 'Match summoner league data gathered!')

                for participant in participant_summoners:
                    participant_summoner = Summoner()
                    participant_summoner.set_name(participant['summonerName'])
                    participant_summoner.set_summoner_id(participant['summonerId'])
                    participant_summoner.set_profile_icon(participant['profileIconId'])
                    game_summoners.append(participant_summoner)

                    # Get live match data

                    # Get champion and its emoji
                    match_champion = await get_league_champion(participant['championId'])
                    participant_summoner.set_champion(match_champion)

                    champion_emoji = await get_champion_emoji(match_champion.get_id_name())

                    last_game_champions[participant_summoner.summoner_id] = match_champion
                    embed_champions += champion_emoji + " " + str(player_nr) + '. ' + str(match_champion.get_name()) + "\n"

                    # Get summoner rank
                    try:
                        # Get league data from previous async requests
                        league_data = participant_leagues_json[player_nr-1]
                        spec_db.add_leagues(league_data, player_nr - 1)

                        data = None
                        for league in league_data:
                            if league['queueType'] == 'RANKED_SOLO_5x5' or "RANKED_SOLO" in league['queueType']:
                                data = league
                                break
                        if data is not None:
                            embed_rank += await determine_rank(data['tier']) + " " + data['tier'] + " " + data[
                                'rank'] + " (" + str(data['leaguePoints']) + "LP)" + "\n"
                            embed_winrate += str(
                                int((data['wins'] / (data['losses'] + data['wins'])) * 100)) + "% (W" + str(
                                data['wins']) + " : " + str(data['losses']) + "L)" + "\n"
                        else:
                            embed_rank += ":black_medium_small_square: UNRANKED\n"
                            embed_winrate += "UNRANKED\n"
                    except Exception as e:
                        logger.log(LOG_TYPE_ERROR, 'spectate', 'Failed to lookup summoner '+participant_summoner.name+' league data. Exception: ' + str(e))
                        embed_rank += ":black_medium_small_square: UNRANKED**?**\n"
                        embed_winrate += "UNRANKED**?**\n"

                    # Create embed footer with nickname and player number
                    embed_footer += str(match_champion.get_name()) + " - " + participant_summoner.name + " (" + str(player_nr) + ") | "

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

                last_game_data_gathered = False
                last_game_summoners = game_summoners

                # Collect summoners puuid, account id and summoner level
                # Get participant data with async requests
                participant_lookup_urls = []
                for participant in participant_summoners:
                    url = "https://eun1.api.riotgames.com/lol/summoner/v4/summoners/" + participant['summonerId'] + "?api_key=" + api_key
                    participant_lookup_urls.append(url)
                participant_summoners_json = await multi_url_api_request(participant_lookup_urls, "SUMMONER-V4", "get_league_spectator_data")

                if len(participant_summoners_json) < 10:
                    raise Exception('Failed to collect all player summoner data, collected ' + str(len(participant_summoners_json)))
                logger.log(LOG_TYPE_INFO, 'get_league_spectator_data', 'Match summoner additional data gathered!')
                i = 0
                for participant in participant_summoners_json:
                    summoner = game_summoners[i]
                    summoner.set_puuid(participant['puuid'])
                    summoner.set_account_id(participant['accountId'])
                    summoner.set_summoner_level(participant['summonerLevel'])
                    spec_db.add_participant_data(participant, i)
                    i += 1

                spec_db.close()
                logger.log(LOG_TYPE_INFO, 'get_league_spectator_data', 'Starting match data gather!')


                await gather_match_data()
                logger.log(LOG_TYPE_INFO, 'get_league_spectator_data', 'Match data gather completed! Adding reactions')
                if second_msg is not None:
                    reaction_options = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟', '🤝']
                    for reaction in reaction_options:
                        await second_msg.add_reaction(reaction)
            else:
                if error_response_enabled:
                    embed_msg = discord.Embed(title=":x: Summoner not found! :x:", color=15105570)
                    await response_channel.send(embed=embed_msg)
                else:
                    logger.log(LOG_TYPE_INFO, 'get_league_spectator_data', 'Error response suppressed: Summoner ' + str(summoner_name) + ' not found!')

    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'get_league_spectator_data', str(e) + ' Traceback: ' + str(traceback.format_exc()))
        embed_msg = discord.Embed(title="Something went wrong while getting game data! :x::pensive:", color=15105570)
        await response_channel.send(embed=embed_msg)


@client.command(aliases=['gg'])
async def spectate(ctx, *summoner_name):
    try:
        if len(summoner_name) == 0:
            global enchanted_id, enchanted_account_id, roboobox_id, roboobox_account_id
            if ctx.message.author.discriminator == roboobox_discord_id:
                await get_league_spectator_data(roboobox_summoner_name, ctx)
            elif ctx.message.author.discriminator == enchanted_discord_id:
                await get_league_spectator_data(enchanted_summoner_name, ctx)
            else:
                embed_msg = discord.Embed(title="", description="Summoner name is required! :x:", color=music_error_color)
        else:
            await get_league_spectator_data(summoner_name, ctx)
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'spectate', str(e) + ' Traceback: ' + str(traceback.format_exc()))
        embed_msg = discord.Embed(title="Something went wrong while getting spectate data! :x::pensive:", color=15105570)
        await ctx.send(embed=embed_msg)


async def get_summoner_match_ids(summoner_puuid: str, match_start_index: int = 0, match_count: int = 4):
    try:
        try:
            url = "https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/"+summoner_puuid+"/ids?start="+str(match_start_index)+"&count="+str(match_count)+"&api_key=" + api_key
            page = urllib.request.urlopen(url)
            match_data = json.loads(page.read().decode())
            RiotApiLogger(logger).log("MATCH-V5", "get_summoner_match_ids", match_data)
        except Exception as e:
            logger.log(LOG_TYPE_ERROR, 'get_summoner_match_ids','Failed to get match data for puuid ' + str(summoner_puuid) + ' Exception:' + str(e))
            return []
        match_ids = []
        for match_id in match_data:
            match_ids.append(match_id)
        if len(match_ids) == 0:
            logger.log(LOG_TYPE_INFO, 'get_summoner_match_ids','Did not find any matches for summoner PUUID: ' + str(summoner_puuid))
        return match_ids

    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'get_summoner_match_ids', 'Failed to get match ID data, Exception:' + str(e) + ' Traceback: ' + str(traceback.format_exc()))
        return []


async def get_summoner_match_data(match_ids: list):
    try:
        if len(match_ids) < 1:
            return []
        matches = []
        match_urls = []
        responses = []
        for match_id in match_ids:
            match_urls.append("https://europe.api.riotgames.com/lol/match/v5/matches/"+str(match_id)+"?api_key=" + api_key)
        try:
            async with aiohttp.ClientSession() as session:
                for url in match_urls:
                    async with session.get(url) as resp:
                        responses.append(await resp.json())
        except Exception as e:
            logger.log(LOG_TYPE_ERROR, 'get_summoner_match_data','Failed to get batch match data, Exception:' + str(e))
            return []
        for r in responses:
            if "status" not in r:
                matches.append(Match(r))
        # RiotApiLogger(logger).log_multiple("MATCH-V5", "get_summoner_match_data", responses)
        return matches
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'get_summoner_match_data', 'Failed to get match data, Exception:' + str(e) + ' Traceback: ' + str(traceback.format_exc()))
        return []


async def multi_url_api_request(urls: list, api_endpoint: str, log_function_name: str):
    try:
        api_responses = []
        async with aiohttp.ClientSession() as session:
            for url in urls:
                async with session.get(url) as resp:
                    json_response = await resp.json()
                    api_responses.append(json_response)
                    RiotApiLogger(logger).log(api_endpoint, log_function_name, json_response)
        return api_responses
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'multi_url_api_request', 'Exception:' + str(e))
        return []

# Command for getting chosen summoner match history stats
@client.command(aliases=['gd'])
async def match_summoner(ctx, summoner_number: int):
    try:
        global last_game_summoners
        summoner = last_game_summoners[summoner_number-1]
        champion = summoner.champion

        if len(summoner.matches) < 1:
            embed_msg = discord.Embed(title="Not enough data for this summoner! :x::pensive:", color=15105570)
            await ctx.send(embed=embed_msg)
            return
        additional_match_ids = await get_summoner_match_ids(summoner.puuid, 5, 5)
        additional_matches = await get_summoner_match_data(additional_match_ids)
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
                raise Exception('Summoner '+summoner.name+' was not found in match '+match.matchId+' participants')
            summoner_match_data.append(SummonerMatch(summoner_participant, match))

        match_champions = []
        match_roles = []
        champion_data_embed = ""
        kda_embed = ""
        additional_info_embed = ""
        for summoner_match in summoner_match_data:
            summoner_champion = await get_league_champion(summoner_match.championId)
            match_champions.append(summoner_champion.get_key())
            if summoner_match.position is not None and summoner_match.position != "":
                match_roles.append(summoner_match.position)
            champion_emoji = await get_champion_emoji(summoner_champion.get_id_name())
            champion_data_embed += summoner_match.get_champion_info(champion_emoji) + "\n"
            kda_embed += summoner_match.get_kda() + "\n"
            additional_info_embed += str(summoner_match.get_additional_summary()) + " | " + str(await determine_queue(summoner_match.matchObject.queueId)) + ":" + str(await get_position_emoji(summoner_match.position)) + "\n"
        most_played_champion = max(set(match_champions), key=match_champions.count, default="Unknown")
        most_played_role = max(set(match_roles), key=match_roles.count, default="Unknown")

        most_played_champion_string = most_played_role_string = "Unknown"
        most_played_champion_title = "Most played champion:\n"
        most_played_role_title = "Most played role:\n"
        if most_played_champion != "Unknown":
            champion_played_times = match_champions.count(most_played_champion)
            # Get champion object
            most_played_champion = await get_league_champion(most_played_champion)
            most_played_champion_string = (await get_champion_emoji(most_played_champion.get_id_name())) + " " + most_played_champion.get_name()
            most_played_champion_title = "Most played champion (*" + str(champion_played_times) + " of " + str(len(summoner_match_data)) + " matches*):\n"
        if most_played_role != "Unknown":
            role_played_time = match_roles.count(most_played_role)
            most_played_role_string = str(await get_position_emoji(most_played_role)) + " " + most_played_role.title()
            most_played_role_title = "Most played role (*" + str(role_played_time) + " of " + str(len(summoner_match_data)) + " matches*):\n"


        embed_msg = discord.Embed(color=3066993, description="*Currently playing:* " + (await get_champion_emoji(champion.get_id_name())) + " *" + str(champion.get_name()) + "*")
        embed_msg.set_author(name=str(summoner.name), icon_url="http://ddragon.leagueoflegends.com/cdn/" + str(dd_newest_version) + "/img/profileicon/" + str(summoner.profile_icon_id) + ".png")
        embed_msg.add_field(name=most_played_role_title, value=most_played_role_string, inline=True)
        embed_msg.add_field(name=most_played_champion_title, value=most_played_champion_string, inline=False)
        embed_msg.add_field(name="Champion", value=champion_data_embed, inline=True)
        embed_msg.add_field(name="KDA", value=kda_embed)
        embed_msg.add_field(name="Additional information", value=additional_info_embed)
        await ctx.send(embed=embed_msg)

    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'match_data', str(e))
        embed_msg = discord.Embed(title="Something went wrong while getting data! :x::pensive:", color=15105570)
        await ctx.send(embed=embed_msg)


@client.command()
async def premades(ctx):
    try:
        global last_game_data_gathered, last_game_summoners
        embed_content = ""
        embed_msg = discord.Embed(title="Match premades:", color=15105570)
        embed_summoner = ""
        embed_premades = ""
        if last_game_data_gathered:
            summoners_checked = []
            for summ in last_game_summoners:
                if summ.name not in summoners_checked:
                    match_premades = summ.get_premades(last_game_summoners)
                    logger.log(LOG_TYPE_INFO, 'premades', "Premade request result: " + str(match_premades))
                    summoners_checked.append(summ.name)
                    summoners_checked = summoners_checked + match_premades[0]
                    match_premades = match_premades[1]
                    embed_summoner = embed_summoner + "*" + summ.champion.get_name() + "*\n"
                    if len(match_premades) > 0:
                        embed_premades = embed_premades + (" **║** ".join(match_premades)) + "\n"
                    else:
                        embed_premades = embed_premades + "None\n"
                    #embed_content += summ.name + " - " + " - ".join(match_premades) + "\n\n"

            embed_msg.add_field(name="Champion", value=embed_summoner)
            embed_msg.add_field(name="Premades", value=embed_premades)
            await ctx.send(embed=embed_msg)
        else:
            embed_msg = discord.Embed(title="Match data not yet available! :x:", color=15105570)
            embed_msg.set_footer(text="Perhaps try a bit later.")
            await ctx.send(embed=embed_msg)
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'premades', str(e) + ' Traceback: ' + str(traceback.format_exc()))

@client.command()
async def summoner(ctx, *summoner_name):
    try:
        global roboobox_summoner_name, enchanted_summoner_name
        if len(summoner_name) > 0:
            summoner_name = " ".join(summoner_name)
            if ctx.message.author.discriminator == roboobox_discord_id:
                roboobox_summoner_name = summoner_name.replace(" ", "%20")
                logger.log(LOG_TYPE_INFO, 'summoner', "Roboobox summoner name changed to " + str(summoner_name))
            elif ctx.message.author.discriminator == enchanted_discord_id:
                enchanted_summoner_name = summoner_name.replace(" ", "%20")
                logger.log(LOG_TYPE_INFO, 'summoner', "EnchantedDragon summoner name changed to " + str(summoner_name))
            await id_update_check()
            await ctx.message.add_reaction('✅')
        else:
            embed_msg = discord.Embed(title="", description="New summoner name is required! :x:",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)
    except Exception as e:
        embed_msg = discord.Embed(title="", description="Unable to change summoner name! :pensive:",
                                  color=music_error_color)
        await ctx.send(embed=embed_msg)
        logger.log(LOG_TYPE_ERROR, 'summoner', str(e) + ' Traceback: ' + str(traceback.format_exc()))


@client.command()
async def summoners(ctx, *summoner_names):
    try:
        global roboobox_summoner_name, enchanted_summoner_name
        if len(summoner_names) > 1:
            summoner_names = " ".join(summoner_names)
            summoner_names = summoner_names.split(",")
            if len(summoner_names) == 2:
                roboobox_summoner_name = summoner_names[0].replace(" ", "%20")
                enchanted_summoner_name = summoner_names[1].replace(" ", "%20")
                logger.log(LOG_TYPE_INFO, 'summoners', "Summoner names changed to " + str(roboobox_summoner_name) + " and " + str(enchanted_summoner_name))
                await id_update_check()
                await ctx.message.add_reaction('✅')
            else:
                embed_msg = discord.Embed(title="", description="Both summoner names are required! :x:",
                                          color=music_error_color)
                await ctx.send(embed=embed_msg)
        else:
            embed_msg = discord.Embed(title="", description="Both summoner names are required! :x:",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)
    except Exception as e:
        embed_msg = discord.Embed(title="", description="Unable to change summoners! :pensive:",
                                  color=music_error_color)
        await ctx.send(embed=embed_msg)
        logger.log(LOG_TYPE_ERROR, 'summoners', str(e) + ' Traceback: ' + str(traceback.format_exc()))



@client.command()
async def tft(ctx, *chmp):
    try:
        page = requests.get("https://lolchess.gg/meta", allow_redirects=False)
        soup = BeautifulSoup(page.text, 'lxml')
        page.close()
        list_names = []
        list_traits = []
        list_champions = []
        list_prices = []
        comps = soup.select("div.guide-meta__deck-box")
        backup_comps = []
        for comp in comps:
            found = 0
            backup_comp = []
            comp_champions = comp.select('div.tft-champion img[src*="/tft/champions/"]')
            comp_prices = comp.select("div.tft-champion span")
            traits = ""
            champions = ""
            comp_name = ""
            i = 0
            for champion in comp_champions:
                champions += champion['alt'] + " (" + comp_prices[i].text + ") | "
                champion_formatted = champion['alt'].replace(" ", "").replace("'", "").lower()
                for user_champion in chmp:
                    user_champion_formatted = user_champion.replace(" ", "").replace("'", "").lower()
                    if champion_formatted == user_champion_formatted:
                        found += 1
                        backup_comp.append(user_champion)
                        if found == len(chmp):
                            break
                    elif len(user_champion_formatted) >= 3 and user_champion_formatted in champion_formatted:
                        found += 1
                        backup_comp.append(user_champion)
                        if found == len(chmp):
                            break
                i += 1
            if found == len(chmp):
                trait_test = comp.select("div.traits div.tft-hexagon-image")
                comp_names = comp.select("div.guide-meta__deck__column.name.mr-3")
                comp_traits = comp.select("div.tft-hexagon-image img")
                list_prices.append(comp.select_one("span.d-block").text)

                for name in comp_names:

                    test = name.text.split("\n")
                    final = ""
                    for data in test:
                        if data != "":
                            final = data
                            break
                    comp_name = final.lstrip()
                list_names.append(comp_name)
                i = 0
                for trait in comp_traits:
                    traits += trait['alt'] + await decide_symbol_tft(trait_test[i]['class'][1]) + " | "
                    i += 1
                list_traits.append(traits)
                list_champions.append(champions)
            elif len(backup_comp) > 0:
                if backup_comp not in backup_comps:
                    backup_comps.append(backup_comp)

        if len(list_names) > 0:
            i = 0
            for name in list_names:
                embed_msg = discord.Embed(color=3447003)
                embed_msg.set_author(name="Comp: " + name, icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/6/67/Teamfight_Tactics_icon.png/revision/latest/scale-to-width-down/64?cb=20191018215638")
                embed_msg.add_field(name="Traits", value=list_traits[i])
                embed_msg.add_field(name="Champions", value=list_champions[i])
                embed_msg.add_field(name="Min Gold", value="     :coin:" + list_prices[i])
                await ctx.send(embed=embed_msg)
                i += 1
        else:
            embed_msg_err = discord.Embed(color=15158332)
            embed_msg_err.set_author(name="No comps found!", icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/6/67/Teamfight_Tactics_icon.png/revision/latest/scale-to-width-down/64?cb=20191018215638")
            embed_msg_err.description = "Did not find any comp for these champion/s :pensive: :no_entry_sign: !"
            if len(backup_comps) > 0:
                backup_comps_text = ""
                for backup_c in backup_comps:
                    backup_comps_text += "!tft"
                    for champion in backup_c:
                        backup_comps_text += " " + champion
                    backup_comps_text += "\n"
                embed_msg_err.add_field(name="This should be working :blush::", value=backup_comps_text)
            await ctx.send(embed=embed_msg_err)
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'tft', str(e) + ' Traceback: ' + str(traceback.format_exc()))

@client.command()
async def version_check(ctx):
    global roboobox_full_id
    try:
        if ctx.author.id == roboobox_full_id:
            await resource_version_check()
            await ctx.send('Performed Data Dragon version check! :white_check_mark:')
        else:
            logger.log(LOG_TYPE_INFO, 'version_check', 'Version check tried by unauthorized user: ' + str(ctx.author))
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'version_check','Error: ' + str(e) + ' Traceback: ' + str(traceback.format_exc()))


@client.command()
async def api(ctx, key):
    if ctx.message.author.discriminator == roboobox_discord_id:
        global api_key
        api_key = key
        logger.log(LOG_TYPE_INFO, 'api_command', 'API key updated')
        await ctx.send("API key updated! :white_check_mark:")


async def create_mood_message(ctx, first_start):
    try:
        if first_start:
            history = await ctx.history(limit=8).flatten()
            for msg in history:
                embeds = msg.embeds
                if len(embeds) > 0:
                    for embed in embeds:
                        if embed.to_dict()['title'] == "How are you feeling now?":
                            await msg.delete()
        mood_emojis = ["😊", "😁", "😏", "🙂", "😶", "🙁", "😣", "😑", "😡"]
        embed_msg = discord.Embed(title="How are you feeling now?", color=15158332, description="--------------------------------------------")
        embed_msg.add_field(name="Amazing", value=":blush:")
        embed_msg.add_field(name="Happy", value=":grin:")
        embed_msg.add_field(name="You know..", value=":smirk:")
        embed_msg.add_field(name="Passive", value=":slight_smile:")
        embed_msg.add_field(name="Lil sad", value=":no_mouth:")
        embed_msg.add_field(name="Sad", value=":slight_frown:")
        embed_msg.add_field(name="Depressed", value=":persevere:")
        embed_msg.add_field(name="Annoyed", value=":expressionless:")
        embed_msg.add_field(name="Angry", value=":rage:")
        embed_msg.set_footer(text="-----------------------------------------------------")
        message = await ctx.send(embed=embed_msg)
        for emoji in mood_emojis:
            await message.add_reaction(emoji)
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'create_mood_message', str(e))

@client.event
async def on_reaction_add(reaction, user):
    try:
        if user.bot:
            pass
        elif len(reaction.message.embeds) > 0 and reaction.message.embeds[0].title == "How are you feeling now?":
            await reaction.message.delete()
            emoji = reaction.emoji
            mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
            if user.discriminator == roboobox_discord_id:
                mood_embed = discord.Embed(color=3066993, description=emoji, title="Mood right now is")
            elif user.discriminator == enchanted_discord_id:
                mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
            mood_embed.set_author(name=user.name, icon_url=user.avatar_url)
            message_date = datetime.datetime.now()
            mood_embed.set_footer(text=str(message_date.day) + "/" + str(message_date.month) + "/" + str(message_date.year) + " | " + str(message_date.hour) + ":" + str(message_date.strftime("%M")))
            await reaction.message.channel.send(embed=mood_embed)
            await create_mood_message(reaction.message.channel, False)
        elif len(reaction.message.embeds) > 0 and reaction.message.embeds[0].title == "Team 2:":
            reaction_options = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
            command = reaction.emoji
            i = 1
            if command == '🤝':
                await premades(reaction.message.channel)
            else:
                for option in reaction_options:
                    if option == command:
                        await match_summoner(reaction.message.channel, i)
                        break
                    i += 1
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'on_reaction_add', str(e) + ' Traceback: ' + str(traceback.format_exc()))

@client.command()
async def mood(ctx, emoji):
    try:
        user = ctx.author
        mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
        if user.discriminator == roboobox_discord_id:
            mood_embed = discord.Embed(color=3066993, description=emoji, title="Mood right now is")
        elif user.discriminator == enchanted_discord_id:
            mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
        mood_embed.set_author(name=user.name, icon_url=user.avatar_url)
        message_date = datetime.datetime.now()
        mood_embed.set_footer(
            text=str(message_date.day) + "/" + str(message_date.month) + "/" + str(message_date.year) + " | " + str(
                message_date.hour) + ":" + str(message_date.strftime("%M")))
        await ctx.message.delete()
        await ctx.channel.send(embed=mood_embed)
        await create_mood_message(ctx, True)
    except Exception as e:
        logger.log(LOG_TYPE_ERROR, 'mood', str(e))

async def pmlp_check():
    global pmlp_notif_enabled
    if pmlp_notif_enabled:
        pmlp = Pmlp(logger)
        bookings = pmlp.request(10)
        pmlp.close()
        available_booking = bookings.get_available_booking()

        if available_booking is not None:
            channel = client.get_channel(505410172819079169)
            logger.log(LOG_TYPE_INFO, 'pmlp_check', 'Sending booking notification, booking:' + available_booking.get_booking())
            await channel.send(':scream_cat: :rotating_light: @everyone Atrasts brīvs pieraksta laiks PMLP 3. nodaļā ' + available_booking.get_info() + '. Piesakies https://pmlp.qticket.app/lv/locations/68/bookings/247 vai https://www.pmlp.gov.lv/lv/pieraksts')

async def schedule_pmlp_check():
    global pmlp_notif_enabled
    # Run first time
    if pmlp_notif_enabled:
        await pmlp_check()

    # 30 mins before another pmlp check in day time
    day_wait = 1800
    # 3 h before another pmlp check in night time
    night_wait = 10800

    now = datetime.datetime.now().time()
    night_start = datetime.time(1, 0, 0)
    night_end = datetime.time(6, 30, 0)

    if night_start <= now < night_end:
        dt_now = datetime.datetime.combine(datetime.date.today(), now)
        dt_night_end = datetime.datetime.combine(datetime.date.today(), night_end)
        till_night_end = int((dt_night_end-dt_now).total_seconds())
        # Check if till night end is less time than night wait
        if till_night_end < night_wait:
            if till_night_end > 0:
                wait = till_night_end + 30
            else:
                wait = day_wait
        else:
            wait = night_wait
    else:
        wait = day_wait

    while pmlp_notif_enabled:
        logger.log(LOG_TYPE_INFO, 'schedule_pmlp_check','Scheduled PMLP check after ' + str(wait) + ' second sleep, current time: ' + datetime.now().strftime("%H:%M:%S"))
        await asyncio.sleep(wait)
        await pmlp_check()

@client.command()
async def pmlp(ctx):
    global pmlp_notif_enabled
    pmlp_notif_enabled = not pmlp_notif_enabled

    if pmlp_notif_enabled:
        ctx.send('PMLP notifications enabled! :white_check_mark:')
        logger.log(LOG_TYPE_INFO, 'pmlp', 'PMLP notifications enabled by command!')
        await schedule_pmlp_check()
    else:
        logger.log(LOG_TYPE_INFO, 'pmlp', 'PMLP notifications disabled by command!')
        ctx.send('PMLP notifications disabled! :x:')


@client.command()
async def help(ctx):
    embed_msg = discord.Embed(title="Bot commands", color=15158332)
    embed_msg.add_field(name="!playtime ", value="Find out League of legends play time", inline=False)
    embed_msg.add_field(name="!rand [item_1 item_2 ...] ", value="Pick one thing out of the list at random", inline=False)
    embed_msg.add_field(name="!randl  [item_1 item_2 ...]", value="Returns randomly ordered list of the items", inline=False)
    embed_msg.add_field(name="!mood [emoji]", value="Creates mood message with your mood", inline=False)
    embed_msg.add_field(name="!a [champion] ", value="Get ARAM data for specified champion", inline=False)
    embed_msg.add_field(name="!autogamedata", value="Enables or disables automatic live game data",inline=False)
    embed_msg.add_field(name="!gd [summoner_number]", value="Returns detailed data about player from current or last game", inline=False)
    embed_msg.add_field(name="!tft [champ1 champ2...]", value="Returns TFT comps for specified champions", inline=False)
    embed_msg.add_field(name="!spectate [summoner_name]", value="Returns live game data of the summoner", inline=False)
    embed_msg.add_field(name="!ult [champion]", value="Returns link to ultimate spellbook build", inline=False)
    embed_msg.add_field(name="!summoner [new_summoner_name]", value="Change your summoner name in Gjorfilds settings",inline=False)
    embed_msg.add_field(name="!summoners [roboobox_summoner_name, enchanteddragon_summoner_name]",value="Change both names in Gjorfilds settings", inline=False)
    embed_msg.add_field(name="!premades", value="Returns premades from current or last game", inline=False)
    embed_msg.add_field(name="!pmlp", value="Enable or Disable PMLP booking notifications", inline=False)

    await ctx.send(embed=embed_msg)

@client.command()
async def helpAdmin(ctx):
    embed_msg = discord.Embed(title="Bot config commands", color=15158332)
    embed_msg.add_field(name="!ping ", value="Returns bot response time", inline=False)
    embed_msg.add_field(name="!hd_rank", value="Enable or disable new rank icons in match embeds",inline=False)
    embed_msg.add_field(name="!version_check", value="Perform Data Dragon version check manually",inline=False)
    embed_msg.add_field(name="!api [key]", value="Change Riot API key", inline=False)
    await ctx.send(embed=embed_msg)


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        await ctx.send("No such command found :(")
    elif isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
        await ctx.send("This command requires argument to be passed!")


# --------------------- MUSIC BOT FUNCTIONALITY ---------------------

# Discord imports
import asyncio
from discord import FFmpegPCMAudio
from discord.utils import get

# Custom classes imports
from classesMusic.Playlist import Playlist
from classesMusic.Audio import Audio
from classesMusic.SpotifyAPI import SpotifyAPI

# Additional imports
import re
import yt_dlp

roboobox_full_id = 225596511818350592
LOG_TYPE_INFO = 'info'
LOG_TYPE_ERROR = 'error'
url_regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

# Music variables
playlists = dict()
activity_task = None
currently_playing = None
music_log = Log(database)
spotify = SpotifyAPI(logger=music_log)
YDL_OPTIONS = {'format': 'bestaudio/best',
               'exctractaudio': True,
               'nocheckcertificate': True,
               'ignoreerrors': False,
               'quiet': True,
               'noplaylist': True,
               'logtostderr': False,
               'no_warnings': True,
               'restrictfilenames': True,
               'default_search': 'auto',
               'source_address': '0.0.0.0'}
FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
}

# Embed colors
# DARK_PURPLE
music_embed_color = 7419530
# RED
music_error_color = 10038562

async def schedule_activity_check():
    while True:
        # 7 minutes
        await asyncio.sleep(420)
        await check_activity()


async def check_activity():
    global activity_task
    music_log.log_music(LOG_TYPE_INFO, 'check_activity', 'Performing activity check!')
    if len(playlists) > 0:
        music_log.log_music(LOG_TYPE_INFO, 'check_activity', 'Found active playlists!')
        to_del = []
        for channel_id, playlist in playlists.items():
            channel = client.get_channel(int(channel_id))
            voice = get(client.voice_clients, guild=channel.guild)
            if voice:
                if not voice.is_playing() and len(playlist.get_queue()) < 1:
                    to_del.append(channel_id)
                    await voice.disconnect()
                elif len(channel.members) < 2:
                    to_del.append(channel_id)
                    await voice.disconnect()
        music_log.log_music(LOG_TYPE_INFO, 'check_activity', 'Inactivity result: ' + str(to_del))
        for channel_id in to_del:
            del playlists[channel_id]
        if len(playlists) == 0:
            activity_task.cancel()
            activity_task = None
    elif len(playlists) == 0:
        activity_task.cancel()
        activity_task = None


async def is_user_in_voice(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        user = await ctx.guild.fetch_member(ctx.author.id)
        if "DJ" in [role.name for role in user.roles] or user.guild_permissions.administrator:
            return True
        else:
            embed_msg = discord.Embed(title="", description="You do not have permission :pensive:",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)
            return False
    else:
        embed_msg = discord.Embed(title="", description=":x: You are not connected to a voice channel",
                                  color=music_error_color)
        await ctx.send(embed=embed_msg)
        return False


async def determine_url_type(url):
    if ("youtube" in url or "youtu.be" in url) and ("list" in url or "playlist" in url):
        return "yt-playlist"
    elif "youtube" in url or "youtu.be" in url:
        return "youtube"
    elif "spotify" in url and re.match(url_regex, url):
        if "/track/" in url:
            return "sp-track"
        elif "/playlist/" in url:
            return "sp-playlist"
        return "unsupported"
    elif re.match(url_regex, url) is None:
        return "search"
    else:
        return "unsupported"


async def get_playlist_urls(playlist_url):
    video_urls = dict()
    try:
        dl_options = dict(YDL_OPTIONS)
        dl_options['extract_flat'] = True
        yt_downloader = yt_dlp.YoutubeDL(dl_options)
        yt_info = yt_downloader.extract_info(playlist_url, download=False)

        for info in yt_info['entries']:
            video_urls[info['title']] = info['url']
        music_log.log_music(LOG_TYPE_INFO, 'get_playlist_urls', 'Returning playlist urls: ' + str(video_urls))
    except Exception as e:
        music_log.log_music(LOG_TYPE_ERROR, 'get_playlist_urls', str(e))
    return video_urls


@client.command(aliases=['p'])
async def play(ctx, *url):
    global activity_task
    audio = playlist_audios = playlist_titles = None
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel), str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        try:
            if len(url) == 0:
                return
            channel = ctx.author.voice.channel
            url = ' '.join(map(str, url))
            url_type = await determine_url_type(url)

            music_log.log_music(LOG_TYPE_INFO, 'play', 'Url type detected: ' + str(url_type))

            youtube_url = url
            if url_type == "youtube" or url_type == "search":
                if url_type == "youtube":
                    youtube_url = url.split("&list=")[0]

            if url_type == "search":
                audio = Audio(youtube_url, True, logger=music_log)
            elif url_type == "youtube":
                audio = Audio(youtube_url, False, logger=music_log)
            elif url_type == "sp-track":
                audio = Audio(spotify.get_track_title(url), True, logger=music_log)
            elif url_type == "yt-playlist":
                playlist_audios = await get_playlist_urls(youtube_url)
            elif url_type == "sp-playlist":
                playlist_titles = spotify.get_playlist_titles(url)
            else:
                raise Exception("Unsupported url type")

            if channel.id in playlists:
                if url_type != "yt-playlist" and url_type != "sp-playlist":
                    playlists[channel.id].add(audio)
                    music_log.log_music(LOG_TYPE_INFO, 'play', 'Adding to playlist: ' + str(audio.url))
                elif url_type == "yt-playlist":
                    music_log.log_music(LOG_TYPE_INFO, 'play', 'Adding from playlist: ' + str(playlist_audios.items())[:50])
                    for title, url in playlist_audios.items():
                        audio = Audio(url, False, title, logger=music_log)
                        playlists[channel.id].add(audio)
                elif url_type == "sp-playlist":
                    music_log.log_music(LOG_TYPE_INFO, 'play', 'Adding from playlist: ' + str(playlist_titles)[:50])
                    for title in playlist_titles:
                        audio = Audio(title, True, title, logger=music_log)
                        playlists[channel.id].add(audio)
            else:
                if url_type != "yt-playlist" and url_type != "sp-playlist":
                    playlists[channel.id] = Playlist(channel.id, audio, YDL_OPTIONS)
                    music_log.log_music(LOG_TYPE_INFO, 'play', 'Creating playlist (' + str(channel.id) + '): ' + str(audio.url))
                elif url_type == "yt-playlist":
                    cnt = 0
                    music_log.log_music(LOG_TYPE_INFO, 'play', 'Creating playlist (' + str(channel.id) + ') from playlist: ' + str(playlist_audios.items())[:50])
                    for title, url in playlist_audios.items():
                        audio = Audio(url, False, title, logger=music_log)
                        if cnt == 0:
                            playlists[channel.id] = Playlist(channel.id, audio, YDL_OPTIONS)
                        else:
                            playlists[channel.id].add(audio)
                        cnt += 1
                elif url_type == "sp-playlist":
                    cnt = 0
                    music_log.log_music(LOG_TYPE_INFO, 'play', 'Creating playlist (' + str(channel.id) + ') from playlist: ' + str(playlist_titles)[:50])
                    for title in playlist_titles:
                        audio = Audio(title, True, title, logger=music_log)
                        if cnt == 0:
                            playlists[channel.id] = Playlist(channel.id, audio, YDL_OPTIONS)
                        else:
                            playlists[channel.id].add(audio)
                        cnt += 1

            playlist = playlists[channel.id]

            if playlist.is_stopped:
                playlist.is_stopped = False

            def play_next(error = None):
                source = playlist.next(False)
                if source is not None and not playlist.is_stopped:
                    voice.play(FFmpegPCMAudio(source, **FFMPEG_OPTIONS), after=play_next)

            if ctx.guild.voice_client is None:
                music_log.log_music(LOG_TYPE_INFO, 'play', 'Connecting to voice!')
                voice = await channel.connect()
            else:
                voice = ctx.voice_client

            if not voice.is_playing():
                if activity_task is None:
                    music_log.log_music(LOG_TYPE_INFO, 'play', 'Starting activity checking!')
                    activity_task = asyncio.create_task(schedule_activity_check())
                play_next()
                if url_type != "yt-playlist" and url_type != "sp-playlist":
                    embed_msg = discord.Embed(title="",
                                              description="Queued: :musical_note: **" + audio.title + "** :musical_note:",
                                              color=music_embed_color)
                else:
                    track_count = 0
                    if url_type == "yt-playlist":
                        track_count = str(len(playlist_audios))
                    elif url_type == "sp-playlist":
                        track_count = str(len(playlist_titles))
                    embed_msg = discord.Embed(title="",
                                              description="Queued: :notes: **" + str(track_count) + " tracks** :notes:",
                                              color=music_embed_color)
                await ctx.send(embed=embed_msg)
            else:
                if url_type != "yt-playlist" and url_type != "sp-playlist":
                    audio.retrieve_audio_data(YDL_OPTIONS)
                    embed_msg = discord.Embed(title="",
                                              description="Added to the queue: :arrow_right: **" + audio.title + "**",
                                              color=music_embed_color)
                else:
                    track_count = 0
                    if url_type == "yt-playlist":
                        track_count = str(len(playlist_audios))
                    elif url_type == "sp-playlist":
                        track_count = str(len(playlist_titles))
                    embed_msg = discord.Embed(title="",
                                                    description="**" + str(track_count) + " tracks** added to the queue: :arrow_right:",
                                                    color=music_embed_color)
                await ctx.send(embed=embed_msg)
        except Exception as e:
            music_log.log_music(LOG_TYPE_ERROR, 'play', str(e))
            embed_msg = discord.Embed(title="", description=":x: Unable to play \"" + url + "\" :pensive:", color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command(aliases=['q'])
async def queue(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        channel = ctx.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and voice.is_playing():
            playlist = playlists[channel.id]
            queue = playlist.get_queue()
            queue_string = "Currently playing: [" + playlist.currentAudio.title + "](" + playlist.currentAudio.url + ")"
            if len(queue) > 0:
                queue_string += "\n\nUp next :arrow_forward:"
                i = 1
                for audio in queue:
                    if i > 10:
                        queue_string += "\n\n " + str(len(queue) - 10) + " more track/s"
                        break
                    if audio.is_search:
                        queue_string += "\nā™«) " + audio.title
                    else:
                        queue_string += "\nā™«) [" + audio.title + "](" + audio.url + ")"
                    i += 1
            embed_msg = discord.Embed(title="Queue:", description=queue_string, color=music_embed_color)
            await ctx.send(embed=embed_msg)
        else:
            embed_msg = discord.Embed(title="", description=":x: Queue is empty!",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command(aliases=['sm'])
async def shazam(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        channel = ctx.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and voice.is_playing():
            playlist = playlists[channel.id]
            embed_msg = discord.Embed(title="", description="Currently playing: [" + playlist.currentAudio.title + "](" + playlist.currentAudio.url + ")", color=music_embed_color)
            await ctx.send(embed=embed_msg)
        else:
            embed_msg = discord.Embed(title="", description=":x: Nothing is playing!",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command()
async def stop(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        channel = ctx.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and voice.is_playing():
            playlist = playlists[channel.id]
            playlist.is_stopped = True
            playlist.clear()
            voice.stop()
            await ctx.message.add_reaction('🛑')
        else:
            embed_msg = discord.Embed(title="", description=":x: Nothing to stop!",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command(aliases=['next'])
async def skip(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and voice.is_playing():
            voice.pause()
            voice.stop()
            await ctx.message.add_reaction('⏭️')
        else:
            embed_msg = discord.Embed(title="", description=":x: Nothing to skip!",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command()
async def pause(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        voice = get(client.voice_clients, guild=ctx.guild)

        if voice is not None and voice.is_playing():
            voice.pause()
            await ctx.message.add_reaction('⏸️')
        else:
            embed_msg = discord.Embed(title="", description=":x: Nothing to pause!",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command(aliases=['start'])
async def resume(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        voice = get(client.voice_clients, guild=ctx.guild)

        if voice is not None and not voice.is_playing():
            voice.resume()
            await ctx.message.add_reaction('▶️')
        else:
            embed_msg = discord.Embed(title="", description=":x: Nothing to resume!",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command()
async def shuffle(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        channel = ctx.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and voice.is_playing():
            playlist = playlists[channel.id]
            if len(playlist.get_queue()) > 1:
                playlist.shuffle()
                await ctx.message.add_reaction('🔀')
            else:
                embed_msg = discord.Embed(title=":x: There is nothing to shuffle :thinking:", color=music_error_color)
                await ctx.send(embed=embed_msg)
        else:
            embed_msg = discord.Embed(title=":x: There is nothing to shuffle :thinking:", color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command()
async def clear(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        channel = ctx.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and voice.is_playing():
            playlist = playlists[channel.id]
            if len(playlist.get_queue()) > 1:
                playlist.clear()
                await ctx.message.add_reaction('✅')
            else:
                embed_msg = discord.Embed(title=":x: There is nothing to clear :thinking:", color=music_error_color)
                await ctx.send(embed=embed_msg)
        else:
            embed_msg = discord.Embed(title=":x: There is nothing to clear :thinking:", color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command()
async def loop(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        channel = ctx.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and voice.is_playing():
            playlist = playlists[channel.id]
            if playlist.is_looping:
                playlist.is_looping = False
                embed_msg = discord.Embed(title="", description="Looping disabled :repeat:", color=music_embed_color)
            else:
                playlist.is_looping = True
                embed_msg = discord.Embed(title="", description="Looping enabled :repeat:", color=music_embed_color)
            await ctx.send(embed=embed_msg)
        else:
            embed_msg = discord.Embed(title="", description=":x: Nothing to loop!",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command(aliases=['leave', 'dc'])
async def disconnect(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    if await is_user_in_voice(ctx):
        channel = ctx.author.voice.channel
        voice = get(client.voice_clients, guild=ctx.guild)
        if voice is not None and ctx.guild.voice_client:
            del playlists[channel.id]
            await ctx.message.add_reaction('👋')
            await ctx.guild.voice_client.disconnect()
        else:
            embed_msg = discord.Embed(title="", description=":x: I am not in a voice channel :thinking:",
                                      color=music_error_color)
            await ctx.send(embed=embed_msg)


@client.command(aliases=['commandsMusic', 'music', 'helpm'])
async def helpMusic(ctx):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel), str(ctx.message.created_at))
    help_text = f"""
    **:musical_note: Music commands :musical_note:**\n
    **{command_prefix}play [youtube_link|spotify_link|title]** - Plays the track/s or adds to queue
    **{command_prefix}skip** - Skips to next track in queue
    **{command_prefix}stop** - Stops the bot and clears playlist
    **{command_prefix}pause** - Pauses the current track
    **{command_prefix}resume** - Resumes the paused track
    **{command_prefix}disconnect** - Disconnects bot from voice channel
    **{command_prefix}clear** - Clears everything from queue
    **{command_prefix}loop** - Loops the currently playing track
    **{command_prefix}shuffle** - Randomizes the queue track order
    **{command_prefix}queue** - Shows the currect track queue
    **{command_prefix}shazam** - Shows the currently playing track
    \n**:notes: Alternative music commands :notes:**\n
    {command_prefix}play = **{command_prefix}p**
    {command_prefix}skip = **{command_prefix}next**
    {command_prefix}resume = **{command_prefix}start**
    {command_prefix}disconnect = **{command_prefix}leave** = **{command_prefix}dc**
    {command_prefix}queue = **{command_prefix}q**
    {command_prefix}shazam = **{command_prefix}sm**
    """
    embed_msg = discord.Embed(title="",
                              description=help_text,
                              color=music_embed_color)
    await ctx.send(embed=embed_msg)

@client.command()
async def announce(ctx, channel_id, *message):
    music_log.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                            str(ctx.message.created_at))
    global roboobox_full_id
    if ctx.author.id == roboobox_full_id:
        channel = client.get_channel(int(channel_id))
        if channel:
            if len(message) > 0:
                await channel.send(" ".join(message).replace('\\n', '\n'))
            else:
                await ctx.send(':x: Message is missing!')
        else:
            await ctx.send(':x: Channel not found!')
    else:
        music_log.log_music(LOG_TYPE_ERROR, 'announce', 'Command used by different user: ' + str(ctx.author))

# --------------------- END OF MUSIC BOT FUNCTIONALITY ---------------------


api_key = config.riot_api_key
roboobox_summoner_name = config.roboobox_summoner_name
enchanted_summoner_name = config.enchanted_summoner_name
roboobox_id = ""
enchanted_id = ""
roboobox_account_id = ""
enchanted_account_id = ""
enchanted_discord_id = config.enchanted_discord_id
roboobox_discord_id = config.roboobox_discord_id

# Gjorfild_Bot
client.run(config.discord_api_key)

# DevBot
# client.run(config.discord_dev_api_key)
