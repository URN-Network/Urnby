# Builtin
import datetime
import json
import asyncio
import time

# External
import discord
from discord.ext import commands, tasks
from pytz import timezone
tz = timezone('EST')
utc_tz = timezone('UTC')

# Internal
import data.databaseapi as db
from static.common import get_hours_from_secs, SECS_IN_MINUTE
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember

REFRESH_TYPE = 'seconds'
REFRESH_TIME = 5

class Dashboard(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.printer.start()
        self.delay = {}
        
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
            channel = await guild.fetch_channel(config['dashboard_channel'])
            def chk(msg):
                if msg.author.id == self.bot.user.id:
                    return True
                return False
            await channel.purge(check=chk)
    
        
    def cog_unload(self):
        self.printer.stop()
        print('Dashboard update stopped', flush=True)
    
    @commands.slash_command(name="dashboardtimeleft")
    @is_member()
    @is_command_channel()
    @is_member_visible()
    async def _timeleft(self, ctx):
        now = datetime.datetime.now(utc_tz)
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
        await ctx.send_response(f"Enabling refresh for the next dashboard update")
        
    @tasks.loop(**{REFRESH_TYPE:REFRESH_TIME})
    async def printer(self):
        for guild in self.bot.guilds:
            config = get_config(guild.id)
            if not config or not config.get('dashboard_channel'):
                continue
            session_real = await db.get_session(guild.id)
            if self.delay.get(guild.id) and session_real:
                self.delay[guild.id] = False
                channel = await guild.fetch_channel(config['dashboard_channel'])
                def chk(msg):
                    if msg.author.id == self.bot.user.id:
                        return True
                    return False
                await channel.purge(check=chk)
                    
            elif self.delay.get(guild.id) and not session_real:
                continue
            
            now = datetime.datetime.now(tz)
            users = await db.get_unique_users(guild.id)
            
            res = await db.get_users_hours(guild.id, users)
            
            sorted_res = list(sorted(res, key= lambda user: user['total'], reverse=True))
            for item in sorted_res:
                try:
                    member = await guild.fetch_member(int(item['user']))
                except discord.errors.NotFound:
                    item['display_name'] = 'placeholder'
                else:
                    item['display_name'] = member.display_name
            
            actives = await db.get_all_actives(guild.id)
            
            for item in actives:
                try:
                    member = await guild.fetch_member(int(item['user']))
                except discord.errors.NotFound:
                    item['display_name'] = 'placeholder'
                else:
                    item['display_name'] = member.display_name

                item['delta'] = get_hours_from_secs(now.timestamp() - item['in_timestamp'])
            
            if not session_real:
                session = {'session': "None"}
                timestr = ''
            else:
                session = session_real
                timestr = datetime.datetime.fromtimestamp(session['start_timestamp'], tz).strftime("%b%d %I:%M%p")
            
            tod_dict = await db.get_tod(guild.id, mob_name="Drusella Sathir")
            mins_till_ds_str = "Unknown"
            if tod_dict:
                tod_datetime = datetime.datetime.fromtimestamp(tod_dict['tod_timestamp'], tz) + datetime.timedelta(days=1)
                mins_till_ds = int((tod_datetime - now).total_seconds()/SECS_IN_MINUTE)
                if mins_till_ds < 0:
                    mins_till_ds_str = "Unknown"
                else:
                    mins_till_ds_str = f'{mins_till_ds:4}mins'
            #TODO get camp queue
            camp_queue = []
            contentlines = ["```\n"]
            contentlines.append(f" {'Active Session':33}DS in: {mins_till_ds_str:8}|")
            contentlines.append(f"{'-'*49}-")
            contentlines.append(f" {session['session'][:27]:27} @ {timestr:13} EST |")
            contentlines.append(f"{'-'*49}|")
            contentlines.append(f" {'Active Users':25}Current / Session Total|") 
            contentlines.append(f"{'-'*49}|")
            for item in actives:
                tot = await db.get_user_current_session_hours(guild.id, int(item['user']))
                contentlines.append(f" {item['display_name'][:29]:36} {item['delta']:2.2f} / {tot:2.2f}|")
            contentlines.append(f"{'-'*49}|")
            contentlines.append(f" {'Camp Queue':33}Hours available|")
            contentlines.append(f"{'-'*49}|")
            for item in camp_queue:
                contentlines.append(f" {item['display_name'][:29]:30} {item['delta']:17.2f}|")
            lines = 2
            ex_lines = 7
            cont_lines = len(actives) + len(camp_queue)
            
            #Appending 2nd column
            contentlines[1] += f" Top {ex_lines+cont_lines} in Hours\n"
            contentlines[2] += f"{'-'*50}\n"
            for idx in range(ex_lines+cont_lines):
                if idx >= len(sorted_res):
                    contentlines[idx+3] += f"\n"
                    continue
                contentlines[idx+3] += f" {sorted_res[idx]['display_name'][:43]:43} {sorted_res[idx]['total']:.2f}\n"
            
            contentlines.append("```")
            content = ""
            for item in contentlines:
                content += item
                
            channel = await guild.fetch_channel(config['dashboard_channel'])
            if not session_real:
                await channel.send(content=content+"Paused till session start", silent=True)
                self.delay[guild.id] = True
            else:
                await channel.send(content=content, delete_after=REFRESH_TIME+.5, silent=True)
                self.delay[guild.id] = False
            

def get_config(guild_id):
    return json.load(open('data/config.json', 'r', encoding='utf-8')).get(str(guild_id))
        

def setup(bot):
    bot.add_cog(Dashboard(bot))
