import os
import discord 
import json
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

#intents = discord.Intents.members + discord.Intents.default()
intents = discord.Intents.default()
UrnbyBot = discord.Bot(intents=intents)


@UrnbyBot.event
async def on_ready():
    print(f"{UrnbyBot.user} is online!")

cogs_list = [
    'clocks',
    'peeper',
    'campqueue',
]

for cog in cogs_list:
    UrnbyBot.load_extension(f'cogs.{cog}')

UrnbyBot.run(TOKEN)