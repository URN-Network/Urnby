# Builtin
import datetime
import json

# External
import discord
from discord.ext import commands
from pytz import timezone
tz = timezone('EST')
from pathlib import Path

# Internal

from checks.IsInDev import is_in_dev, InDevelopment

CLASSES = json.load(open('static/classes.json', 'r', encoding='utf-8'))

class CampQueue(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        print('Initilization on campqueue complete')

    @commands.Cog.listener()
    @is_in_dev()
    async def on_connect(self):
        print(f'campqueue connected to discord')
        data_dirs = ['data/campqueue.json']
        # Set up initilized db files if not existing and all guilds are initilized
        for _dir in data_dirs:
            if not Path(_dir).exists():
                print(f'init path - {_dir}')
                file = {}
            else:
                file = json.load(open(_dir, 'r', encoding='utf-8'))
            
            for guild in self.bot.guilds:
                if str(guild.id) not in list(file.keys()):
                    print(f'init guild - {guild.id} for {_dir}')
                    if 'session' in _dir:
                        file[str(guild.id)] = {}
                    else:
                        file[str(guild.id)] = []
                    
            json.dump(file, open(_dir, 'w', encoding='utf-8'), indent=1)

    @commands.slash_command(name='campqueue')
    @is_in_dev()
    async def _campqueue(self, ctx, 
                         character: discord.Option(name='character', input_type=str, required=True),
                         _class: discord.Option(name='class', choices=CLASSES, required=True),
                         hours: discord.Option(name='hours', description='Estimated hours till you leave the camp or queue', input_type=int, required=True),
                         extra: discord.Option(name='extra', description='Extra information if you have additional classes etc', input_type=str, required=False, default='')
                         ):
        queue = await self.get_queue(ctx.guild.id)
        for player in queue:
            if player['user'] == ctx.author.id:
                await ctx.send_response(content=f'You are already in the queue! To change values in a queue use campeditqueue or camp dequeue to leave the queue')
        
        pass
    
    @commands.slash_command(name='campdequeue')
    @is_in_dev()
    async def _campdequeue(self, ctx):
        pass
        
    @commands.slash_command(name='campeditqueue')
    @is_in_dev()
    async def _campeditqueue(self, ctx):
        pass

    # ==============================================================================
    # Database functions
    # ==============================================================================
    

def setup(bot):
    bot.add_cog(CampQueue(bot))