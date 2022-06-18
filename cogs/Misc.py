from discord.ext import commands
import random
import traceback
import config.config as config


class Misc(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.logger = client.logger

    @commands.command()
    async def rand(self, ctx, *arg):
        try:
            list_i = list(arg)
            victor = random.randint(0, len(list_i) - 1)
            await ctx.send(list_i[victor])
        except Exception as e:
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'rand', str(e) + ' Traceback: ' + str(traceback.format_exc()))

    @commands.command()
    async def randl(self, ctx, *arg):
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
            self.logger.log(self.logger.LOG_TYPE_ERROR, 'randl', str(e) + ' Traceback: ' + str(traceback.format_exc()))

    @commands.command()
    async def api(self, ctx, key):
        if ctx.message.author.discriminator == self.client.roboobox_discord_id:
            config.riot_api_key = key
            self.logger.log(self.logger.LOG_TYPE_INFO, 'api_command', 'API key updated')
            await ctx.send("API key updated! :white_check_mark:")

    @commands.command()
    async def announce(self, ctx, channel_id, *message):
        self.logger.log_music_cmd(str(ctx.author), str(ctx.command), str(ctx.kwargs), str(ctx.channel),
                                  str(ctx.message.created_at))
        if ctx.author.id == self.client.roboobox_full_id:
            channel = self.client.get_channel(int(channel_id))
            if channel:
                if len(message) > 0:
                    try:
                        await channel.send(" ".join(message).replace('\\n', '\n'))
                    except Exception as e:
                        self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'announce', str(e))
                else:
                    await ctx.send(':x: Message is missing!')
            else:
                await ctx.send(':x: Channel not found!')
        else:
            self.logger.log_music(self.logger.LOG_TYPE_ERROR, 'announce',
                                  'Command used by different user: ' + str(ctx.author))

    @commands.command()
    async def ping(self, ctx):
        await ctx.send('Pong! {}'.format(round(self.client.latency * 1000)))


def setup(client):
    client.add_cog(Misc(client))
