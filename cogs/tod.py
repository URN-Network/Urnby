# Builtin
import datetime
import json

# External
import discord
from discord.ext import commands
from pytz import timezone
tz = timezone('EST')

# Internal
import data.databaseapi as db
from static.common import get_hours_from_secs
from views.ClearOutView import ClearOutView
from checks.IsAdmin import is_admin, NotAdmin
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember
from checks.IsInDev import is_in_dev, InDevelopment

class Tod(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        print('Initilization on tod complete')

    @commands.Cog.listener()
    async def on_ready(self):
        missing_tables = await db.check_tables(['tod'])
        if missing_tables:
            print(f"Warning, ToD reports missing the following tables in db: {missing_tables}")
    
    @commands.slash_command(name='tod', description='Entered tod must be todays date, or using the optional daybefore parameter, yesterday')
    async def _tod(self, ctx, 
                       tod: discord.Option(str, name='tod', description="Use when time is not 'now' - 24hour clock time EST (ex 14:49)" , default='now'),
                       mobname: discord.Option(str, name='mobname', default='Drusella Sathir'),
                       daybefore: discord.Option(bool, name='daybefore', description='Use if the tod was actually yesterday',  default=False)):
        now = datetime.datetime.now(tz)
        tod_datetime = {}
        if tod == 'now':
            tod_datetime = datetime.datetime.now(tz)
        if not tod_datetime and len(tod) == 4:
            tod = '0' + tod
        
        if not tod_datetime:    
            tod_datetime = datetime.datetime.combine(datetime.date.today()+datetime.timedelta(days=offset), datetime.time.fromisoformat(tod), tz)
        
        offset = 0
        if daybefore:
            offset = -1
        
        rec = {
               "mob": mobname, 
               "tod_timestamp": tod_datetime.timestamp(), 
               "submitted_timestamp": tod_datetime.timestamp(), 
               "submitted_by_id": ctx.author.id,
               "_DEBUG_submitted_datetime": now.isoformat(), 
               "_DEBUG_submitted_by": ctx.author.display_name, 
               "_DEBUG_tod_datetime": tod_datetime.isoformat(), 
               }
        row = await db.store_tod(ctx.guild.id, rec)
        await ctx.send_response(content=f"Set tod at {rec['_DEBUG_tod_datetime']}, spawn will happen at {(tod_datetime+datetime.timedelta(days=1)).isoformat()}")
        return
        
    @commands.slash_command(name='gettod')
    async def _get_tod(self, ctx):
        rec = await db.get_tod(ctx.guild.id)
        now = datetime.datetime.now(tz)
        hours_till = get_hours_from_secs(now.timestamp() - (datetime.datetime.fromtimestamp(rec['tod_timestamp'], tz)+datetime.timedelta(days=1)).timestamp())
        await ctx.send_response(content=f"ToD was {rec['_DEBUG_tod_datetime']} {rec['mob']} will spawn in {hours_till} hours", ephemeral=True)

async def time_delta_to_minutes(delta:datetime.timedelta) -> float:
    secs = delta.total_seconds()
    sec_to_min = 60
    mins = secs/sec_to_min
    return mins

def setup(bot):
    bot.add_cog(Tod(bot))