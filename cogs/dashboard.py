# Builtin
import datetime
import json
import asyncio
import time
import os
from enum import Enum

# External
import discord
from discord.ext import commands, tasks

# Internal
import data.databaseapi as db
import static.common as com
from checks.IsAdmin import is_admin, NotAdmin
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember
from checks.IsInDev import is_in_dev, InDevelopment

REFRESH_TYPE = 'seconds'
REFRESH_TIME = 60
CAMP_HOURS_TILL_DS = 18
HOURS_SOFTCAP = 5
MOBILE_REDUCE_SPACE = 10

DEBUG = os.getenv('DEBUG')
if DEBUG:
    REFRESH_TIME = 15

class Format(Enum):
    Normal = 0
    Bold = 1
    Underline = 4

class TextColor(Enum):
    Gray   = 30 
    Red    = 31 
    Green  = 32 
    Yellow = 33 
    Blue   = 34 
    Pink   = 35 
    Cyan   = 36 
    White  = 37 

class BackgroundColor(Enum):
    FireflyDarkBlue  = 40 
    Orange           = 41 
    MarbleBlue       = 42 
    GreyishTurquoise = 43 
    Gray             = 44 
    Indigo           = 45 
    LightGray        = 46 
    White            = 47 

def ansi_format(t: str, format : Format = Format.Normal, exformat : Format = None, background : BackgroundColor = None , color : TextColor = None):
    # TODO make it better for having two formating options, maybe move to common module
    uni_esc = f'\u001b'
    format_start = '['
    format_end = 'm'
    res = uni_esc + format_start
    if format:
        res += str(format.value)
    else:
        res += str(Format.Normal.value)
    if exformat:
        res += ';' + str(exformat.value)
    if background:
        res += ';' + str(background.value)
    if color:
        res += ';' + str(color.value)
    res += format_end + t + uni_esc + format_start + str(Format.Normal.value) + format_end
    return res

class Dashboard(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.delay = {}
        self.open_transitioned = {}
        self.cache_datetime = None
        self.config_cache = {}
        self.refresh_cache_config()
        self.printer.start()
        self.dash_message = {}
        self.dash_mobile_message = {}
        print('Initilization on dashboard complete')
        
    # ==============================================================================
    # Error Handlers
    # ==============================================================================
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        now = com.get_current_datetime()
        guild_id = None
        channel_name = None
        if not ctx.guild:
            guild_id = 'DM'
            channel_name = 'DM'
        else:
            guild_id = ctx.guild.id
            channel_name = ctx.channel.name
        print(f'{now.isoformat()} [{guild_id}] - Error in command {ctx.command.qualified_name} by {ctx.author.name} - {ctx.author.id} {error}', flush=True)
        _error = {
            'level': 'error', 
            'command_name': ctx.command.qualified_name, 
            'options': str(ctx.selected_options), 
            'author_id': ctx.author.id, 
            'author_name': ctx.author.name, 
            'channel_name': channel_name, 
            'error': str(type(error)),
        }
        
        if isinstance(error, NotAdmin):
            await ctx.send_response(content=f"You do not have permissions to use this function, {ctx.command} - {ctx.selected_options}")
            return
        elif isinstance(error, NotCommandChannel):
            await ctx.send_response(content=f"You can not perform this command in this channel", ephemeral=True)
            return
        elif isinstance(error, NotMemberVisible):
            await ctx.send_response(content=f"This command can not be performed where other members can not see the command", ephemeral=True)
            return
        elif isinstance(error, NotMember):
            await ctx.send_response(content=f"You must be a member of higher privileges to invoke this command", ephemeral=False)
            return
        elif isinstance(error, InDevelopment):
            await ctx.send_response(content=f"This function is unavailable due to it's development status", ephemeral=True)
            return
        else:
            print(type(error), flush=True)
            raise error
        return
 
    @commands.Cog.listener()
    async def on_ready(self):
        missing_tables = await db.check_tables(['historical', 'session', 'session_history', 'active', 'tod'])
        if missing_tables:
            print(f"Warning, Dashboard reports missing the following tables in db: {missing_tables}")
            
        for guild in self.bot.guilds:
            config = self.get_config(guild.id)
            if not config:
                continue
            await self._purge_dashboard(guild)

    def cog_unload(self):
        self.printer.stop()
        print('Dashboard update stopped', flush=True)
    
    '''
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
    '''
    
    @commands.slash_command(name="dashboardrefresh")
    @is_member()
    @is_command_channel()
    @is_member_visible()
    async def _refresh(self, ctx):
        session = await db.get_session(ctx.guild.id)
        if self.delay.get(ctx.guild.id) and not session:
            self.delay[ctx.guild.id] = False
            await ctx.send_response(f"Enabling refresh for the next dashboard update")
        else:
            self.delay[ctx.guild.id] = False
            await ctx.send_response(f"Refeshing should be enabled. Forcing update, if no update comes, contact admin")
    
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
            self.dash_message[guild.id] = await channel.send(content=f'Starting Dashboard...', silent=True)

        if config.get('mobile_dash_channel'):
            print(f'{com.get_current_iso()} [{guild.id}] - Purging mobile dash', flush=True)
            mobile_channel = await guild.fetch_channel(config['mobile_dash_channel'])
            await mobile_channel.purge(check=chk)
            self.dash_mobile_message[guild.id] = await mobile_channel.send(content=f'Starting Dashboard...', silent=True)

    
    @tasks.loop(**{REFRESH_TYPE:REFRESH_TIME})
    async def printer(self):
        for guild in self.bot.guilds:
            
            config = self.get_config(guild.id)
            if not config or not config.get('dashboard_channel'):
                continue
            channel = await guild.fetch_channel(config['dashboard_channel'])
            mobile_channel = None
            if config.get('mobile_dash_channel'):
                mobile_channel = await guild.fetch_channel(config['mobile_dash_channel'])
            if not self.dash_message.get(guild.id):
                await channel.send(content=f'Starting Dashboard...', silent=True)
            if not self.dash_mobile_message.get(guild.id):
                await mobile_channel.send(content=f'Starting Dashboard...', silent=True)
            session_real = await db.get_session(guild.id)
            historical_recs_from_session = []
            if session_real:
                historical_recs_from_session = await db.get_historical_session(guild.id, session_real['session'])
            now = com.get_current_datetime()
            tod_dict = await db.get_tod(guild.id, mob_name="Drusella Sathir")
            mins_till_ds_str = "Unknown"
            mins_till_ds = -1
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
                    if "PCT_BONUS" in _item['character']:
                        continue
                    item['ses_delta'] += com.get_hours_from_secs(_item['out_timestamp'] - _item['in_timestamp'])
                item['ses_delta'] = round(item['ses_delta'], 2)
            
            if not session_real:
                session = {'session': "None"}
                timestr = ''
            else:
                session = session_real
                timestr = com.datetime_from_timestamp(session['start_timestamp']).strftime("%b%d %I:%M%p")
            
            camp_queue = await db.get_replacement_queue(guild.id)
            
            # NOTE! Actives and Camp queue must be completed before this step as we are limiting based on the number of the aforementioned 
            lines = 2
            ex_lines = 7
            cont_lines = len(actives) + len(camp_queue)
            users = await db.get_unique_users(guild.id)
            
            res = await db.get_users_hours_v2(guild.id, users, limit = ex_lines+cont_lines, trim_afk=True)
            
            for item in res:
                item['display_name'] = str(item['user'])
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
                    reduce = MOBILE_REDUCE_SPACE
                return f"{'-'*(50-reduce)}"
            
            async def get_col1(mobile=False):
                col1 = []
                reduce = 0
                if mobile:
                    reduce = MOBILE_REDUCE_SPACE
                seperator = get_seperator(mobile)
                # 1st column 50 spaces 
                col1.append(f"{' Active Session':15}{_open:^{19-reduce}}{'DS in: ':7}{mins_till_ds_str:8}{' ':1}")
                col1.append(seperator)
                col1.append(f"{' ' + session['session'][:28-reduce]:{30-reduce}}{'@ ':2}{timestr:13}{' EST ':5}")
                col1.append(seperator)
                col1.append(f"{' Active Users':<{34-reduce}}{'Current / Total':>15}{' ':1}") 
                col1.append(seperator)
                for item in actives:
                    if item['ses_delta'] >= HOURS_SOFTCAP:
                        color = TextColor.Red
                    else:
                        color = TextColor.Green
                    formated_times = ansi_format(f"{item['delta']:>5.2f}{' / ':3}{item['ses_delta']:>5.2f}{' ':1}", format=Format.Bold, color=color)
                    col1.append(f"{' ' + item['display_name'][:24-reduce]:{36-reduce}}{formated_times:14}")
                col1.append(seperator)
                col1.append(f"{' Camp Queue':{36-reduce}}{'Mins in queue':>13}{' ':1}")
                col1.append(seperator)
                now = com.get_current_datetime()
                for item in camp_queue:
                    mins = int((now - com.datetime_from_timestamp(item['in_timestamp'])).total_seconds()/com.SECS_IN_MINUTE)
                    tots = await db.get_user_hours_v2(guild.id, item['user'])
                    ses_hours = ""
                    if tots['session_total'] >= HOURS_SOFTCAP:
                        color = TextColor.Red
                        ses_hours = f"{{{tots['session_total']}}}"
                    elif tots['session_total']:
                        color = TextColor.Green
                        ses_hours = f"{{{tots['session_total']}}}"
                    else:
                        color = TextColor.Green
                    formated_queue_item = ansi_format(f"{' ' + item['name'][:35-reduce] + ses_hours:{37-reduce}}{' @ ':3}{mins:3}{' ':1}", format=Format.Bold, color = color)
                    col1.append(formated_queue_item)
                return col1
            
            async def get_col2(mobile=False):
                #Appending 2nd column
                col2 = []
                reduce = 0
                if mobile:
                    reduce = 10
                seperator = get_seperator(mobile)
                col2.append(f" Top {ex_lines+cont_lines} in Hours")
                col2.append(seperator)
                for idx in range(ex_lines+cont_lines):
                    if idx >= len(res):
                        col2.append(f"")
                        continue
                    match idx:
                        case 0:
                            medal='🥇'
                        case 1:
                            medal='🥈'
                        case 2:
                            medal='🥉'
                        case _:
                            medal=''
                    col2.append(f"{' ' + res[idx]['display_name'][:41-reduce]:{42-reduce}}{' ':1}{res[idx]['total']:>6.2f}{' ':1}{medal}")
                return col2
            
            col1 = await get_col1()
            col2 = await get_col2()
            now = com.get_current_datetime()
            rec = await db.get_tod(guild.id)
            if rec:
                spawn_timestamp = int((com.datetime_from_timestamp(rec["tod_timestamp"]) + datetime.timedelta(days=1)).timestamp())
             
            title = f'_Last Updated: {now.time().isoformat()}.'
            if rec and spawn_timestamp > now.timestamp():
                title += f' DS Spawn <t:{spawn_timestamp}:R> at <t:{spawn_timestamp}>'
            title += f'_ ```ansi\n'
            tail = "```\n"
            
            desktop_dash = title
            for idx, _ in enumerate(col1):
                div = '|'
                if idx == 1:
                    div = '-'
                desktop_dash += col1[idx] + div + col2[idx] + '\n'
            desktop_dash += tail
            
            mcol1 = await get_col1(True)
            mcol2 = await get_col2(True)
            
            mobile_dash = title
            
            for idx in range(len(mcol1)):
                mobile_dash += mcol1[idx] + '\n'
            mobile_dash += '\n' + get_seperator(True) + '\n'
            for idx in range(len(mcol2)):
                mobile_dash += mcol2[idx] + '\n'
            mobile_dash += tail
            
            
            if not session_real:
                desktop_dash += "Paused till session start. "
                mobile_dash += "Paused till session start. "
                
                if self.open_transitioned.get(guild.id):
                    desktop_dash += "Camp is open!"
                    mobile_dash += "Camp is open!"
                    
                await self.dash_message[guild.id].edit(content=desktop_dash)
                
                
                if mobile_channel and mobile_channel.permissions_for(guild.get_member(self.bot.user.id)).send_messages:
                    await self.dash_mobile_message[guild.id].edit(content=mobile_dash)
                else:
                    print(f'{guild.id} mobile channel {mobile_channel} could not sent permissions or config not in')
                
                self.delay[guild.id] = True
            else:
                await self.dash_message[guild.id].edit(content=desktop_dash)
                
                if mobile_channel and mobile_channel.permissions_for(guild.get_member(self.bot.user.id)).send_messages:
                    await self.dash_mobile_message[guild.id].edit(content=mobile_dash)
                else:
                    print(f'{guild.id} mobile channel {mobile_channel} could not sent permissions or config not in')
                
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
