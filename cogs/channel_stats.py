# Builtin
import json
import datetime
import os
import re

# External
import discord
from discord.ext import commands, tasks

# Internal
import static.common as com
import data.databaseapi as db

# Can only change channel name twice every 10 minutes
REFRESH_TYPE = 'seconds'
REFRESH_TIME = 360

CAMP_HOURS_TILL_DS = 18

DEBUG = os.getenv('DEBUG')
if DEBUG:
    REFRESH_TIME = 360

class Channel_Stats(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.printer.start()
        self.last_data = {}
        print('Initilization on channel stats complete')
        
    @commands.Cog.listener()
    async def on_ready(self):
        missing_tables = await db.check_tables(['historical'])
        if missing_tables:
            print(f"Warning, Dashboard reports missing the following tables in db: {missing_tables}")
    
    def guild_have_manage_channels(self, guild):
        res = []
        for role in guild.get_member(self.bot.user.id).roles:
            if role.permissions.manage_channels:
                return True
        return False
        
    def cog_unload(self):
        self.printer.stop()
        print('Channel Stats update stopped', flush=True)
    
    @tasks.loop(**{REFRESH_TYPE:REFRESH_TIME})
    async def printer(self):
        for guild in self.bot.guilds:
            if not self.guild_have_manage_channels(guild):
                continue
            config = get_config(guild.id)
            if not config or not config.get('channel_stats'):
                continue
            print(f"{com.get_current_iso()} [{guild.id}] - Refreshing channel stats")
            l = len(config['channel_stats'])
            
            users = await db.get_unique_users(guild.id)
            
            res = await db.get_users_hours(guild.id, users, limit = l)
            def ordinal(n: int):
                if 11 <= (n % 100) <= 13:
                    suffix = 'th'
                else:
                    suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
                return str(n) + suffix
            if res != self.last_data.get(guild.id):
                self.last_data[guild.id] = res
                for idx, chan in enumerate(config['channel_stats']):
                    try:
                        member = await guild.fetch_member(res[idx]['user'])
                    except discord.errors.NotFound:
                        member = None
                    disp = 'placehold'
                    if member:
                        disp = member.display_name
                        nonletter = re.search(r'[^\w]', disp)
                        if nonletter:
                            disp = disp[:nonletter.start()]
                    name = f"{ordinal(idx+1)} {disp[:10]} - {res[idx]['total']}"
                    channel = None
                    for g_chan in guild.channels:
                        if g_chan.id == chan:
                            channel = g_chan
                    if not channel:
                        continue
                    print(f'{com.get_current_iso()} [{guild.id}] - Setting channel {channel.name} to {name}')
                    await channel.edit(name=name)
                
            now = com.get_current_datetime()
            tod_dict = await db.get_tod(guild.id, mob_name="Drusella Sathir")
            mins_till_ds = -1
            mins_till_ds_str = "Unknown ToD"
            if tod_dict:
                tod_datetime = com.datetime_from_timestamp(tod_dict['tod_timestamp']) + datetime.timedelta(days=1)
                mins_till_ds = int((tod_datetime - now).total_seconds()/com.SECS_IN_MINUTE)
                if mins_till_ds < 0:
                    mins_till_ds_str = "Unknown ToD"
                else:
                    mins_till_ds_str = f'DS in: {mins_till_ds:4}mins'
            channel = None
            if config.get('countdown_stats'):
                channel = next((c for c in guild.channels if c.id == config['countdown_stats']), None)
                if channel and channel.name != mins_till_ds_str and channel.permissions_for(guild.get_member(self.bot.user.id)).manage_channels:
                    print(f'setting channel {channel.name} to {mins_till_ds_str}')
                    await channel.edit(name=mins_till_ds_str)
            channel = None
            if config.get('campstatus_stats'):
                _open = "<CLOSED"
                if mins_till_ds >= 0 and mins_till_ds <= com.MINUTE_IN_HOUR * CAMP_HOURS_TILL_DS:
                    _open = "<OPEN"
                if mins_till_ds < 0:
                    _open = "<UNKNOWN"
                ses = await db.get_session(guild.id)
                if ses:
                    _open += "+ACTIVE"                
                _open += ">"
                channel = next((c for c in guild.channels if c.id == config['campstatus_stats']), None)
                if channel and channel.name != _open and channel.permissions_for(guild.get_member(self.bot.user.id)).manage_channels:
                    print(f'setting channel {channel.name} to {_open}')
                    await channel.edit(name=_open)
            channel = None
            if config.get('active_stats') and config.get('max_active'):
                _max = config.get('max_active')
                actives = await db.get_all_actives(guild.id)
                
                _current = len(actives)
                s = f'Actives {_current}/{_max}'
                reps = await db.get_replacement_queue(guild.id)
                if reps:
                    s += f'+{len(reps)}'
                channel = next((c for c in guild.channels if c.id == config['active_stats']), None)
                if channel and channel.name != s and channel.permissions_for(guild.get_member(self.bot.user.id)).manage_channels:
                    print(f'setting channel {channel.name} to {s}')
                    await channel.edit(name=s)
            

def get_config(guild_id):
    return json.load(open('data/config.json', 'r', encoding='utf-8')).get(str(guild_id))
        

def setup(bot):
    bot.add_cog(Channel_Stats(bot))