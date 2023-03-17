import os
import discord 
from discord.ext import commands
import json
import logging
from asyncio import sleep
from dotenv import load_dotenv

import static.common as com
import data.databaseapi as db

logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DEBUG = os.getenv('DEBUG')

if DEBUG:
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())

intents = discord.Intents.default()
UrnbyBot = discord.Bot(intents=intents)

cogs_list = [
    'clocks',
    'peeper',
    'campqueue',
    'misc',
    'dashboard',
    'tod',
    'channel_stats',
]


@UrnbyBot.event
async def on_ready():
    await db.init_database()
    print(f"{com.get_current_iso()} - {UrnbyBot.user} is online!", flush=True)

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

