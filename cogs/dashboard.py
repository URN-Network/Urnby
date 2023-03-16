# Builtin
import datetime
import json
import asyncio
import time
import os

# External
import discord
from discord.ext import commands, tasks

# Internal
import data.databaseapi as db
import static.common as com
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember

REFRESH_TYPE = 'seconds'
REFRESH_TIME = 60
CAMP_HOURS_TILL_DS = 18

DEBUG = os.getenv('DEBUG')
if DEBUG:
    REFRESH_TIME = 15

class Dashboard(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.delay = {}
        self.open_transitioned = {}
        self.cache_datetime = None
        self.config_cache = {}
        self.refresh_cache_config()
        self.printer.start()
        print('Initilization on dashboard complete')
        
            
    @commands.Cog.listener()
    async def on_ready(self):
        missing_tables = await db.check_tables(['historical', 'session', 'session_history', 'active', 'tod'])
        if missing_tables:
            print(f"Warning, Dashboard reports missing the following tables in db: {missing_tables}")
            
        for guild in self.bot.guilds:
            config = self.get_config(guild.id)
            if not config or not config.get('dashboard_channel'):
                continue
            await self._purge_dashboard(guild)
    
        
    def cog_unload(self):
        self.printer.stop()
        print('Dashboard update stopped', flush=True)
    
    @commands.slash_command(name="dashboardtimeleft")
    @is_member()
    @is_command_channel()
    @is_member_visible()
    async def _timeleft(self, ctx):
        now = com.get_current_datetime()
        delta = "Printer not scheduled"
        if self.printer.next_iteration:
            delta = self.printer.next_iteration - now
        await ctx.send_response(content=f'Time till dashboard refresh check {delta}')
        
    @commands.slash_command(name="dashboardrefresh")
    @is_member()
    @is_command_channel()
    @is_member_visible()
    async def _refresh(self, ctx):
        session = await db.get_session(ctx.guild.id)
        if self.delay.get(ctx.guild.id) and not session:
            self.delay[ctx.guild.id] = False
        await self._purge_dashboard(ctx.guild)
        await ctx.send_response(f"Enabling refresh for the next dashboard update")
    
    async def _purge_dashboard(self, guild):
        def chk(msg):
            if msg.author.id == self.bot.user.id:
                return True
            return False
        config = self.get_config(guild.id)
        if config.get('dashboard_channel'):
            print(f'{com.get_current_iso()} [{guild.id}] - Purging dashboard', flush=True)
            channel = await guild.fetch_channel(config['dashboard_channel'])
            await channel.purge(check=chk)
        if config.get('mobile_dash_channel'):
            print(f'{com.get_current_iso()} [{guild.id}] - Purging mobile dash', flush=True)
            mobile_channel = await guild.fetch_channel(config['mobile_dash_channel'])
            await mobile_channel.purge(check=chk)
    
    @tasks.loop(**{REFRESH_TYPE:REFRESH_TIME})
    async def printer(self):
        for guild in self.bot.guilds:
            
            config = self.get_config(guild.id)
            if not config or not config.get('dashboard_channel'):
                continue
            session_real = await db.get_session(guild.id)
            historical_recs_from_session = []
            if session_real:
                historical_recs_from_session = await db.get_historical_session(guild.id, session_real['session'])
            now = com.get_current_datetime()
            tod_dict = await db.get_tod(guild.id, mob_name="Drusella Sathir")
            mins_till_ds_str = "Unknown"
            if tod_dict:
                tod_datetime = com.datetime_from_timestamp(tod_dict['tod_timestamp']) + datetime.timedelta(days=1)
                mins_till_ds = int((tod_datetime - now).total_seconds()/com.SECS_IN_MINUTE)
                if mins_till_ds < 0:
                    mins_till_ds_str = "Unknown"
                else:
                    mins_till_ds_str = f'{mins_till_ds:4}mins'
            _open = ""
            if mins_till_ds >= 0 and mins_till_ds <= com.MINUTE_IN_HOUR * CAMP_HOURS_TILL_DS:
                _open = "<OPEN>"
                # If we are in delayed mode, and we havent refreshed with the new transition, refresh automatically
                if self.delay.get(guild.id) and not self.open_transitioned.get(guild.id):
                    self.open_transitioned[guild.id] = True
                    self.delay[guild.id] = False
                    await self._purge_dashboard(guild)
            if self.delay.get(guild.id) and session_real:
                self.delay[guild.id] = False
                await self._purge_dashboard(guild)
                    
            elif self.delay.get(guild.id) and not session_real:
                continue
            
            
            actives = await db.get_all_actives(guild.id)
            
            for item in actives:
                item['display_name'] = 'placeholder'
                item['delta'] = com.get_hours_from_secs(now.timestamp() - item['in_timestamp'])
                mem_historical = [_ for _ in historical_recs_from_session if _['user'] == item['user']]
                item['ses_delta'] = item['delta']
                try:
                    member = await guild.fetch_member(int(item['user']))
                except discord.errors.NotFound:
                    member = None
                if member:
                    item['display_name'] = member.display_name
                for _item in mem_historical:
                   item['ses_delta'] += com.get_hours_from_secs(_item['out_timestamp'] - _item['in_timestamp'])
                item['ses_delta'] = round(item['ses_delta'], 2)
            
            if not session_real:
                session = {'session': "None"}
                timestr = ''
            else:
                session = session_real
                timestr = com.datetime_from_timestamp(session['start_timestamp']).strftime("%b%d %I:%M%p")
            
            #TODO get camp queue
            camp_queue = await db.get_replacement_queue(guild.id)
            
            # NOTE! Actives and Camp queue must be completed before this step as we are limiting based on the number of the aforementioned 
            lines = 2
            ex_lines = 7
            cont_lines = len(actives) + len(camp_queue)
            users = await db.get_unique_users(guild.id)
            
            res = await db.get_users_hours(guild.id, users, limit = ex_lines+cont_lines)
            
            for item in res:
                item['display_name'] = 'placeholder'
                if guild.get_member(int(item['user'])):
                    item['display_name'] = next((x.display_name for x in guild.members if x.id == int(item['user'])), None)
                else:
                    try:
                        member = await guild.fetch_member(int(item['user']))
                    except discord.errors.NotFound:
                        continue
                    item['display_name'] = member.display_name
            
            def get_seperator(mobile=False):
                reduce = 0
                if mobile:
                    reduce = 6
                return f"{'-'*(45-reduce)}"
            
            def get_col1(mobile=False):
                col1 = []
                reduce = 0
                if mobile:
                    reduce = 6
                seperator = get_seperator(mobile)
                # 1st column 50 spaces 
                col1.append(f"{' Active Session':15}{_open:^{14-reduce}}{'DS in: ':7}{mins_till_ds_str:8}{' ':1}")
                col1.append(seperator)
                col1.append(f"{' ' + session['session'][:23]:{25-reduce}}{'@ ':2}{timestr:13}{' EST ':5}")
                col1.append(seperator)
                col1.append(f"{' Active Users':<{29-reduce}}{'Current / Total':>15}{' ':1}") 
                col1.append(seperator)
                for item in actives:
                    col1.append(f"{' ' + item['display_name'][:29]:{31-reduce}}{item['delta']:>5.2f}{' / ':3}{item['ses_delta']:>5.2f}{' ':1}")
                col1.append(seperator)
                col1.append(f"{' Camp Queue':{29-reduce}}{'Hours available':>15}{' ':1}")
                col1.append(seperator)
                for item in camp_queue:
                    col1.append(f"{' ' + item['name'][:44]:{45-reduce}}")
                return col1
            
            def get_col2(mobile=False):
                #Appending 2nd column
                col2 = []
                reduce = 0
                if mobile:
                    reduce = 6
                seperator = get_seperator(mobile)
                col2.append(f" Top {ex_lines+cont_lines} in Hours")
                col2.append(seperator)
                for idx in range(ex_lines+cont_lines):
                    if idx >= len(res):
                        col2.append(f"")
                        continue
                    col2.append(f"{' ' + res[idx]['display_name'][:36]:{37-reduce}}{' ':1}{res[idx]['total']:>6.2f}{' ':1}")
                return col2
            
            col1 = get_col1()
            col2 = get_col2()
            desktop_dash = "```\n"
            for idx, _ in enumerate(col1):
                div = '|'
                if idx == 1:
                    div = '-'
                desktop_dash += col1[idx] + div + col2[idx] + '\n'
            desktop_dash += "```\n"
            
            mcol1 = get_col1(True)
            mcol2 = get_col2(True)
            mobile_dash = "```\n"
            for idx in range(len(mcol1)):
                mobile_dash += mcol1[idx] + '\n'
            mobile_dash += '\n' + get_seperator(True) + '\n'
            for idx in range(len(mcol2)):
                mobile_dash += mcol2[idx] + '\n'
            mobile_dash += "```\n"
            
            channel = await guild.fetch_channel(config['dashboard_channel'])
            if not session_real:
                desktop_dash += "Paused till session start. "
                mobile_dash += "Paused till session start. "
                
                if self.open_transitioned.get(guild.id):
                    desktop_dash += "Camp is open!"
                    mobile_dash += "Camp is open!"
                    
                await channel.send(content=desktop_dash, silent=True)
                
                if config.get('mobile_dash_channel'):
                    mobile_channel = await guild.fetch_channel(config['mobile_dash_channel'])
                    
                    if mobile_channel and mobile_channel.permissions_for(guild.get_member(self.bot.user.id)).send_messages:
                        await mobile_channel.send(content=mobile_dash, silent=True)
                    else:
                        print(f'mobile channel {mobile_channel} could not send maybe permissions?')
                
                self.delay[guild.id] = True
            else:
                await channel.send(content=desktop_dash, delete_after=REFRESH_TIME+.5, silent=True)
                
                if config.get('mobile_dash_channel'):
                    mobile_channel = await guild.fetch_channel(config['mobile_dash_channel'])
                    if mobile_channel and mobile_channel.permissions_for(guild.get_member(self.bot.user.id)).send_messages:
                        await mobile_channel.send(content=mobile_dash, delete_after=REFRESH_TIME+.5, silent=True)
                    else:
                        print(f'mobile channel {mobile_channel} could not send maybe permissions?')
                
                self.open_transitioned[guild.id] = False
                self.delay[guild.id] = False
    
    def get_config(self, guild_id):
        now = com.get_current_datetime()
        if self.cache_datetime and (now - self.cache_datetime).total_seconds() > 5 * com.SECS_IN_MINUTE:
            self.refresh_cache_config()
        if self.config_cache:
            return self.config_cache.get(str(guild_id))
        else:
            return None
    
    def refresh_cache_config(self):
        self.cache_datetime = com.get_current_datetime()
        self.config_cache = json.load(open('data/config.json', 'r', encoding='utf-8'))
        

    

def setup(bot):
    bot.add_cog(Dashboard(bot))
