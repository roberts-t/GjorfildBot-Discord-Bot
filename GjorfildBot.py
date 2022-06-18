#!/usr/bin/python3
import discord
from discord.ext import commands
from logger.CustomLog import *
from classes.Database import Database
import mysql.connector

intents = discord.Intents().all()

command_prefix = '!'
client = commands.Bot(command_prefix=command_prefix, help_command=None, intents=intents)

# Client global variables
client.database = mysql.connector.connect(
    host=config_db.database['host'],
    user=config_db.database['user'],
    password=config_db.database['password'],
    database=config_db.database['database']
)
client.db = Database(client.database)
client.logger = Log(client.database)
client.enchanted_discord_id = config.enchanted_discord_id
client.roboobox_discord_id = config.roboobox_discord_id
client.roboobox_summoner_name = config.roboobox_summoner_name
client.enchanted_summoner_name = config.enchanted_summoner_name
client.roboobox_full_id = 225596511818350592
# Purple embed color
client.embed_default = 7419530
# Red embed color
client.embed_error = 10038562

# Available cogs
initial_extensions = ['cogs.Music',
                      'cogs.Helper',
                      'cogs.PmlpCog',
                      'cogs.LeagueVersion',
                      'cogs.Misc',
                      'cogs.Mood',
                      'cogs.LeagueStats',
                      'cogs.LeagueMatch']
# Loading cogs
if __name__ == '__main__':
    for extension in initial_extensions:
        client.load_extension(extension)


@client.event
async def on_ready():
    client.logger.log(client.logger.LOG_TYPE_INFO, 'on_ready', 'Bot is ready!')


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.CommandNotFound):
        await ctx.send("No such command found :(")
    elif isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
        await ctx.send("This command requires argument to be passed!")


# Gjorfild_Bot
if config.production_env:
    client.run(config.discord_api_key)

# DevBot
if not config.production_env:
    client.run(config.discord_dev_api_key)
