from discord.ext import commands
import discord
import traceback
import datetime


class Mood(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        try:
            if user.bot:
                pass
            elif len(reaction.message.embeds) > 0 and reaction.message.embeds[0].title == "How are you feeling now?":
                await reaction.message.delete()
                emoji = reaction.emoji
                mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
                if user.discriminator == self.client.roboobox_discord_id:
                    mood_embed = discord.Embed(color=3066993, description=emoji, title="Mood right now is")
                elif user.discriminator == self.client.enchanted_discord_id:
                    mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
                mood_embed.set_author(name=user.name, icon_url=user.avatar_url)
                message_date = datetime.datetime.now()
                mood_embed.set_footer(text=str(message_date.day) + "/" + str(message_date.month) + "/" + str(
                    message_date.year) + " | " + str(message_date.hour) + ":" + str(message_date.strftime("%M")))
                await reaction.message.channel.send(embed=mood_embed)
                await self.create_mood_message(reaction.message.channel, False)
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'on_reaction_add',
                            str(e) + ' Traceback: ' + str(traceback.format_exc()))

    async def create_mood_message(self, ctx, first_start):
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
            embed_msg = discord.Embed(title="How are you feeling now?", color=15158332,
                                      description="--------------------------------------------")
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
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'create_mood_message', str(e))

    @commands.command()
    async def mood(self, ctx, emoji):
        try:
            user = ctx.author
            mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
            if user.discriminator == self.client.roboobox_discord_id:
                mood_embed = discord.Embed(color=3066993, description=emoji, title="Mood right now is")
            elif user.discriminator == self.client.enchanted_discord_id:
                mood_embed = discord.Embed(color=0x3398e6, description=emoji, title="Mood right now is")
            mood_embed.set_author(name=user.name, icon_url=user.avatar_url)
            message_date = datetime.datetime.now()
            mood_embed.set_footer(
                text=str(message_date.day) + "/" + str(message_date.month) + "/" + str(message_date.year) + " | " + str(
                    message_date.hour) + ":" + str(message_date.strftime("%M")))
            await ctx.message.delete()
            await ctx.channel.send(embed=mood_embed)
            await self.create_mood_message(ctx, True)
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'mood', str(e))


def setup(client):
    client.add_cog(Mood(client))
