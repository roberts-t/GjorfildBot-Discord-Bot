from discord.ext import commands
import discord


class Helper(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger
        self.command_prefix = client.command_prefix

    @commands.command()
    async def help(self, ctx):
        embed_msg = discord.Embed(title="Bot commands", color=15158332)
        embed_msg.add_field(name="!playtime ", value="Find out League of legends play time", inline=False)
        embed_msg.add_field(name="!rand [item_1 item_2 ...] ", value="Pick one thing out of the list at random",
                            inline=False)
        embed_msg.add_field(name="!randl  [item_1 item_2 ...]", value="Returns randomly ordered list of the items",
                            inline=False)
        embed_msg.add_field(name="!mood [emoji]", value="Creates mood message with your mood", inline=False)
        embed_msg.add_field(name="!a [champion] ", value="Get ARAM data for specified champion", inline=False)
        embed_msg.add_field(name="!autogamedata", value="Enables or disables automatic live game data", inline=False)
        embed_msg.add_field(name="!gd [summoner_number]",
                            value="Returns detailed data about player from current or last game", inline=False)
        embed_msg.add_field(name="!tft [champ1 champ2...]", value="Returns TFT comps for specified champions",
                            inline=False)
        embed_msg.add_field(name="!spectate [summoner_name]", value="Returns live game data of the summoner",
                            inline=False)
        embed_msg.add_field(name="!ult [champion]", value="Returns link to ultimate spellbook build", inline=False)
        embed_msg.add_field(name="!summoner [new_summoner_name]",
                            value="Change your summoner name in Gjorfilds settings", inline=False)
        embed_msg.add_field(name="!summoners [roboobox_summoner_name, enchanteddragon_summoner_name]",
                            value="Change both names in Gjorfilds settings", inline=False)
        embed_msg.add_field(name="!premades", value="Returns premades from current or last game", inline=False)
        embed_msg.add_field(name="!pmlp", value="Enable or Disable PMLP booking notifications", inline=False)
        embed_msg.add_field(name="!pmlp_change [location_id, service_id]",
                            value="Change PMLP location and service to check", inline=False)
        embed_msg.add_field(name="!pmlp_channel [channel_id]", value="Change PMLP notification channel", inline=False)
        embed_msg.add_field(name="!pmlp_weeks [week_count]",
                            value="Change PMLP week count to check (default is 10)", inline=False)
        embed_msg.add_field(name="!pmlp_delay [minutes]",
                            value="Change PMLP delay between checks in minutes (default is 30)", inline=False)

        await ctx.send(embed=embed_msg)

    @commands.command(aliases=['commandsMusic', 'music', 'helpm'])
    async def helpmusic(self, ctx):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        help_text = f"""
        **:musical_note: Music commands :musical_note:**\n
        **{self.command_prefix}play [youtube_link|spotify_link|title]** - Plays the track/s or adds to queue
        **{self.command_prefix}playn [youtube_link|spotify_link|title]** - Adds track/s after currently playing track
        **{self.command_prefix}playi track_number [youtube_link|spotify_link|title]** - Adds track/s after specified track number
        **{self.command_prefix}skip** - Skips to next track in queue
        **{self.command_prefix}stop** - Stops the bot and clears playlist
        **{self.command_prefix}pause** - Pauses the current track
        **{self.command_prefix}resume** - Resumes the paused track
        **{self.command_prefix}disconnect** - Disconnects bot from voice channel
        **{self.command_prefix}clear** - Clears everything from queue
        **{self.command_prefix}loop** - Loops the currently playing track
        **{self.command_prefix}shuffle** - Randomizes the queue track order
        **{self.command_prefix}queue** - Shows the currect track queue
        **{self.command_prefix}shazam** - Shows the currently playing track
        \n**:notes: Alternative music commands :notes:**\n
        {self.command_prefix}play = **{self.command_prefix}p**
        {self.command_prefix}playn = **{self.command_prefix}play_next**
        {self.command_prefix}playi = **{self.command_prefix}play_insert**
        {self.command_prefix}skip = **{self.command_prefix}next**
        {self.command_prefix}resume = **{self.command_prefix}start**
        {self.command_prefix}disconnect = **{self.command_prefix}leave** = **{self.command_prefix}dc**
        {self.command_prefix}queue = **{self.command_prefix}q**
        {self.command_prefix}shazam = **{self.command_prefix}sm**
        """
        embed_msg = discord.Embed(title="",
                                  description=help_text,
                                  color=self.client.embed_default)
        await ctx.send(embed=embed_msg)

    @commands.command()
    async def helpadmin(self, ctx):
        embed_msg = discord.Embed(title="Bot config commands", color=15158332)
        embed_msg.add_field(name="!ping ", value="Returns bot response time", inline=False)
        embed_msg.add_field(name="!hd_rank", value="Enable or disable new rank icons in match embeds", inline=False)
        embed_msg.add_field(name="!version_check", value="Perform Data Dragon version check manually", inline=False)
        embed_msg.add_field(name="!api [key]", value="Change Riot API key", inline=False)
        await ctx.send(embed=embed_msg)


def setup(client):
    client.add_cog(Helper(client))
