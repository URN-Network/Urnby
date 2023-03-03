import os
import discord 
import json
from asyncio import sleep
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')

#intents = discord.Intents.members + discord.Intents.default()
intents = discord.Intents.default()
UrnbyBot = discord.Bot(intents=intents)


@UrnbyBot.event
async def on_ready():
    print(f"{UrnbyBot.user} is online!")
    if DEBUG == "True":
        for guild in UrnbyBot.guilds:
            await guild.get_member(UrnbyBot.user.id).edit(nick='Baul Pearer')
    else:
        for guild in UrnbyBot.guilds:
            await guild.get_member(UrnbyBot.user.id).edit(nick='Paul Bearer')

@UrnbyBot.command()
@is_owner()
async def shutdown(ctx):
    for cog in cogs_list:
        UrbyBot.remove_cog(cog)
    print("Shut down all cogs")
    await sleep(1)
    exit()
    
@UrnbyBot.command()
@is_owner()
async def restart(ctx):
    cog_objs = []
    for cog in cogs_list:
        cog_objs.append(UrnbyBot.get_cog(cog))
        UrnbyBot.remove_cog(cog)
    await sleep(1)
    for cog in cog_objs:
        if cog:
            UrnbyBot.add_cog(cog)

cogs_list = [
    'clocks',
    'peeper',
    'campqueue',
    'misc',
    'dashboard',
]

for cog in cogs_list:
    UrnbyBot.load_extension(f'cogs.{cog}')

UrnbyBot.run(TOKEN)