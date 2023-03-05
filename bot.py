import os
import discord 
from discord.ext import commands
import json
import logging
from asyncio import sleep, set_event_loop_policy, WindowsSelectorEventLoopPolicy
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')

if DEBUG:
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

#intents = discord.Intents.members + discord.Intents.default()
intents = discord.Intents.default()
UrnbyBot = discord.Bot(intents=intents)

cogs_list = [
    'clocks',
    'peeper',
    'campqueue',
    'misc',
    'dashboard',
    'tod',
]

@UrnbyBot.event
async def on_ready():
    print(f"{UrnbyBot.user} is online!")
    '''
    if DEBUG == "True":
        for guild in UrnbyBot.guilds:
            await guild.get_member(UrnbyBot.user.id).edit(nick='Baul Pearer')
    else:
        for guild in UrnbyBot.guilds:
            await guild.get_member(UrnbyBot.user.id).edit(nick='Paul Bearer')
    '''

@UrnbyBot.command()
@commands.is_owner()
async def ownershutdown(ctx):
    for cog in cogs_list:
        print(f'Unloading {cog}')
        UrnbyBot.unload_extension(f'cogs.{cog}')
    print("Shut down all cogs")
    await ctx.send_response(content="Cogs shut down, bot logging off")
    await sleep(1)
    print("Bot logging off")
    # for any cleanup close will need to be overridden which will require contextulizing the bot
    await UrnbyBot.close()
    
@UrnbyBot.command()
@commands.is_owner()
async def ownerrestart(ctx):
    for cog in cogs_list:
        UrnbyBot.reload_extension(f'cogs.{cog}')
    print('Cogs restarted')
    await ctx.send_response(content="Restarted!")

for cog in cogs_list:
    UrnbyBot.load_extension(f'cogs.{cog}')
    
UrnbyBot.run(TOKEN)

