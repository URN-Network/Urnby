# Builtin
import datetime
import json
import asyncio
import time

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
REFRESH_TIME = 15
CAMP_HOURS_TILL_DS = 18

class Dashboard(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.printer.start()
        self.delay = {}
        self.open_transitioned = {}
        
        print('Initilization on dashboard complete')
        
            
    @commands.Cog.listener()
    async def on_ready(self):
        missing_tables = await db.check_tables(['historical', 'session', 'session_history', 'active', 'tod'])
        if missing_tables:
            print(f"Warning, Dashboard reports missing the following tables in db: {missing_tables}")
            
        for guild in self.bot.guilds:
            config = get_config(guild.id)
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
        config = get_config(guild.id)
        channel = await guild.fetch_channel(config['dashboard_channel'])
        def chk(msg):
            if msg.author.id == self.bot.user.id:
                return True
            return False
        await channel.purge(check=chk)
    
    @tasks.loop(**{REFRESH_TYPE:REFRESH_TIME})
    async def printer(self):
        for guild in self.bot.guilds:
            config = get_config(guild.id)
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
                item['ses_delta'] = round(item['ses_delta'],2)
            
            if not session_real:
                session = {'session': "None"}
                timestr = ''
            else:
                session = session_real
                timestr = com.datetime_from_timestamp(session['start_timestamp']).strftime("%b%d %I:%M%p")
            
            #TODO get camp queue
            camp_queue = []
            
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
            
            
            contentlines = ["```\n"]
            contentlines.append(f" {'Active Session':20}{_open:13}DS in: {mins_till_ds_str:8}|")
            contentlines.append(f"{'-'*49}-")
            contentlines.append(f" {session['session'][:27]:27} @ {timestr:13} EST |")
            contentlines.append(f"{'-'*49}|")
            contentlines.append(f" {'Active Users':19}Hours at camp / Session Total|") 
            contentlines.append(f"{'-'*49}|")
            for item in actives:
                contentlines.append(f" {item['display_name'][:29]:30} {item['delta']:>9.2f} / {item['ses_delta']:>5.2}|")
            contentlines.append(f"{'-'*49}|")
            contentlines.append(f" {'Camp Queue':33}Hours available|")
            contentlines.append(f"{'-'*49}|")
            for item in camp_queue:
                contentlines.append(f" {item['display_name'][:29]:30} {item['delta']:>9.2f} / {item['ses_delta']:>5.2}|")
            
            
            #Appending 2nd column
            contentlines[1] += f" Top {ex_lines+cont_lines} in Hours\n"
            contentlines[2] += f"{'-'*50}\n"
            for idx in range(ex_lines+cont_lines):
                if idx >= len(res):
                    contentlines[idx+3] += f"\n"
                    continue
                contentlines[idx+3] += f" {res[idx]['display_name'][:42]:42} {res[idx]['total']:>6.2f}\n"
            
            contentlines.append("```")
            content = ""
            for item in contentlines:
                content += item
                
            channel = await guild.fetch_channel(config['dashboard_channel'])
            if not session_real:
                content += "Paused till session start. "
                if self.open_transitioned.get(guild.id):
                    content += "Camp is open!"
                    #self.open_transitioned[guild.id]
                await channel.send(content=content, silent=True)
                self.delay[guild.id] = True
            else:
                await channel.send(content=content, delete_after=REFRESH_TIME+.5, silent=True)
                self.open_transitioned[guild.id] = False
                self.delay[guild.id] = False
            

def get_config(guild_id):
    return json.load(open('data/config.json', 'r', encoding='utf-8')).get(str(guild_id))
        

def setup(bot):
    bot.add_cog(Dashboard(bot))
