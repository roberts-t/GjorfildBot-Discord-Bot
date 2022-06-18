from discord.ext import commands
import discord
import difflib
import requests
import urllib.request
from bs4 import BeautifulSoup
import json
import traceback


class LeagueStats(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger
        self.db = client.db
        self.game_champions = None

    @commands.command(pass_context=True)
    async def playtime(self, ctx):
        try:
            # Checks if message author is Roboobox or EnchantedDragon
            if ctx.message.author.discriminator == self.client.roboobox_discord_id or ctx.message.author.discriminator == self.client.enchanted_discord_id:
                played_secs = 0
                # Selects ms field based on user which requested command and uses rstrip to remove newline char from line and then converts to int
                if ctx.message.author.discriminator == self.client.roboobox_discord_id:
                    played_secs = \
                        self.db.query_select_one(
                            "SELECT playtime_duration FROM gjorfild_playtime WHERE `member` = '#8998'")[0]
                elif ctx.message.author.discriminator == self.client.enchanted_discord_id:
                    played_secs = \
                        self.db.query_select_one(
                            "SELECT playtime_duration FROM gjorfild_playtime WHERE `member` = '#9101'")[0]

                hours = played_secs // 3600
                minutes = (played_secs - (hours * 3600)) // 60
                seconds = (played_secs - hours * 3600 - minutes * 60)
                message = "Your playtime is " + str(hours) + (" hour, " if hours == 1 else " hours, ") + str(
                    minutes) + (" minute and " if minutes == 1 else " minutes and ") + str(seconds) + (
                              " second" if seconds == 1 else " seconds")
                embed_msg = discord.Embed(description=message, color=3447003)
                embed_msg.set_author(
                    icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/5/53/Riot_Games_logo_icon.png/revision/latest/scale-to-width-down/124?cb=20190417213704",
                    name="League of Legends")
                await ctx.send(embed=embed_msg)
            else:
                self.logger.log(self.logger.LOG_TYPE_ERROR, 'playtime_command',
                                'Wrong author discriminator: ' + str(ctx.message.author.discriminator))
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'playtime', str(e))

    async def get_all_champions(self):
        try:
            champions_page = urllib.request.urlopen(
                "http://ddragon.leagueoflegends.com/cdn/" + str(
                    self.client.dd_newest_version) + "/data/en_US/champion.json")
            champion_json_array = json.loads(champions_page.read().decode())
            self.game_champions = []
            for champion in champion_json_array['data']:
                # Create assoc array with champion key and champion object
                champion_json = champion_json_array['data'][champion]
                self.game_champions.append(champion_json['id'])
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_all_champions',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    async def get_closest_champion(self, champion: str):
        try:
            if len(champion) > 0:
                closest_champion_winner = ""
                closest_champions = difflib.get_close_matches(champion.lower().replace(" ", ""), self.game_champions,
                                                              n=3,
                                                              cutoff=0.4)
                if len(closest_champions) > 0:
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'get_closest_champion',
                                    'Closest champions found for (' + champion + ') are ' + str(closest_champions))

                    for close_champion in closest_champions:
                        if close_champion.startswith(champion.lower().replace(" ", "")):
                            closest_champion_winner = close_champion
                            break
                    if closest_champion_winner == "":
                        closest_champion_winner = closest_champions[0]
                    print(closest_champion_winner)
                    self.logger.log(self.logger.LOG_TYPE_INFO, 'get_closest_champion',
                                    'Closest champion found as ' + str(closest_champion_winner))
                    return closest_champion_winner
                else:
                    return ""
            else:
                return ""
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'get_closest_champion', str(e))

    async def decide_symbol(self, element):
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

    async def decide_symbol_tft(self, element):
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

    @commands.command(aliases=['spellbook'])
    async def ult(self, ctx, *champion):
        try:
            if len(champion) > 0:
                champion = " ".join(champion)
                closest_champion = (await self.get_closest_champion(champion)).lower()
                if len(closest_champion) > 0:
                    await ctx.send("https://www.metasrc.com/ultbook/champion/" + closest_champion)
                else:
                    await ctx.send(":exclamation:Champion was not found :pensive::exclamation:")
            else:
                await ctx.send("You forgot to specify champion name :pensive::exclamation:")
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'ult', str(e))

    @commands.command(aliases=['aram'])
    async def a(self, ctx, *arg):
        try:
            # Checks if there are passed arguments
            if len(arg) > 0:
                # Joins arguments for creating a link and makes it lowercase, uses champion name guessing
                champion_to_check = (await self.get_closest_champion(" ".join(arg))).lower()
                if champion_to_check != "":
                    # Gets ARAM champion page data
                    aram_url = "https://www.metasrc.com/aram/na/champion/" + champion_to_check
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
                        self.logger.log(self.logger.LOG_TYPE_INFO, 'a_command', 'Rune data found: ')
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
                                        await ctx.send(str(await self.decide_symbol(
                                            rune_data[i + 1]['data-xlink-href']) + " | " + await self.decide_symbol(
                                            rune_data[i + 2]['data-xlink-href']) + " | " + await self.decide_symbol(
                                            rune_data[i + 3]['data-xlink-href'])))
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
                        self.logger.log(self.logger.LOG_TYPE_INFO, 'a_command',
                                        'Ability values found: ' + str(abilities))
                        # Sorts abilities dictionary by key so abilities are sorted by their last level upgraded which is ability upgrade order
                        abilities = sorted(abilities, key=abilities.get)
                        ability_order = ""
                        # Creates string with uprgade order
                        for ability in abilities:
                            ability_order += ability + " > "
                        # Removes last three symbols which are " > "
                        ability_order = ability_order[:-3]
                        # Selects champion image url
                        # [5:-2] to remove url(' at beginning and ') at the end
                        champion_image = soup.select_one('._40ug81 a._hmag7l')['data-background-image'][5:-2]

                        # Concatenates and sends embeds with data
                        start_items = ""
                        build_items = ""
                        spells = spells_div[0]['alt'] + "\n" + spells_div[1]['alt']
                        self.logger.log(self.logger.LOG_TYPE_INFO, 'a_command',
                                        'Spells found: ' + str(spells) + ', champion image found: ' + str(
                                            champion_image))
                        embed_s = discord.Embed(title="ARAM setup: " + '\n' + aram_url, color=11027200)
                        embed_s.set_thumbnail(url=champion_image)
                        for link in soup.select(
                                'div._5cna4p div._c8xw44:nth-of-type(2) div._dtoou._59r45k._dcqhsp div div img'):
                            if "ddragon" in link['data-src']:
                                start_items += link['alt'] + "\n"
                        i = 1
                        for link in soup.select('div._5cna4p div._c8xw44:nth-of-type(3) div._h8qwbj div div img'):
                            if "ddragon" in link['data-src']:
                                build_items += str(i) + ". " + link['alt'] + "\n"
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
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'a', str(e) + ' Traceback: ' + str(traceback.format_exc()))

    @commands.command()
    async def tft(self, ctx, *chmp):
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
                        traits += trait['alt'] + await self.decide_symbol_tft(trait_test[i]['class'][1]) + " | "
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
                    embed_msg.set_author(name="Comp: " + name,
                                         icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/6/67/Teamfight_Tactics_icon.png/revision/latest/scale-to-width-down/64?cb=20191018215638")
                    embed_msg.add_field(name="Traits", value=list_traits[i])
                    embed_msg.add_field(name="Champions", value=list_champions[i])
                    embed_msg.add_field(name="Min Gold", value="     :coin:" + list_prices[i])
                    await ctx.send(embed=embed_msg)
                    i += 1
            else:
                embed_msg_err = discord.Embed(color=15158332)
                embed_msg_err.set_author(name="No comps found!",
                                         icon_url="https://static.wikia.nocookie.net/leagueoflegends/images/6/67/Teamfight_Tactics_icon.png/revision/latest/scale-to-width-down/64?cb=20191018215638")
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
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'tft', str(e) + ' Traceback: ' + str(traceback.format_exc()))


def setup(client):
    client.add_cog(LeagueStats(client))
