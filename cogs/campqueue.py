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
import data.databaseapi as db

class CampQueue(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        print('Initilization on campqueue complete')

    @commands.Cog.listener()
    async def on_connect(self):
        print(f'campqueue connected to discord')

    @commands.slash_command(name='getqueue')
    async def _getcampqueue(self, ctx):
        if ctx.guild is None:
            await ctx.send_response(content='This command can not be used in Direct Messages')
            return
        reps = await db.get_replacement_queue(ctx.guild.id)

        # Make Pretty.
        content = '_ _\nCurrent replacement order: '
        for rep in reps:
            content += f'<@{rep["user"]}> --> '
        content += f'<END>'
        await ctx.send_response(content=content, ephemeral=False, allowed_mentions=discord.AllowedMentions(users=False))


    @commands.slash_command(name='campenqueue')
    async def _campenqueue(self, ctx):
        now = datetime.datetime.now(tz)
        rep = {
            'user': ctx.author.id,
            'in_timestamp': int(now.timestamp())
        }
        added = await db.add_replacement(ctx.guild.id, rep)
        if added is not None:
            await ctx.send_response(content=f'{ctx.author.display_name} Successfully added to replacement queue')
        else:
            await ctx.send_response(content=f'You are already in the queue')
    
    @commands.slash_command(name='campdequeue')
    async def _campdequeue(self, ctx):
        removed = await db.remove_replacement(ctx.guild.id, ctx.author.id)
        if removed is not None:
            await ctx.send_response(content=f'{ctx.author.display_name} Successfully removed from replacement queue')
        else:
            await ctx.send_response(content=f'You are not in the queue')

    @commands.slash_command(name='admin_campenqueue')
    async def _admincampenqueue(self, ctx,
                _userid: discord.Option(int, name="userid", required=True),
                intime: discord.Option(int, name="intime", required=False, default=0)):

        if intime == 0:
            intime = int(datetime.datetime.now(tz).timestamp())
        
        rep = {
            'user': _userid,
            'name': "adminuser",
            'in_timestamp': intime
        }
        await db.add_replacement(ctx.guild.id, rep)
        await ctx.send_response(content=f'Added.')
        
    @commands.slash_command(name='admin_campdequeue')
    async def _admincampdequeue(self, ctx,
                _userid: discord.Option(str, name="userid", required=True)):
        await db.remove_replacement(ctx.guild.id, _userid)
        await ctx.send_response(content=f'Removed.')

    @commands.slash_command(name='admin_campqueueflush')
    async def _admincampqueueflush(self, ctx):
        await db.clear_replacement_queue(ctx.guild.id)
        await ctx.send_response(content=f'Queue cleared.')


def setup(bot):
    bot.add_cog(CampQueue(bot))