# Builtin
import datetime
import json
import asyncio
import copy
from pathlib import Path

# External
import discord
from discord.ext import commands
from pytz import timezone
tz = timezone('EST')
from aiosqlite import OperationalError

# Internal
import data.databaseapi as db
from static.common import get_hours_from_secs
from views.ClearOutView import ClearOutView
from checks.IsAdmin import is_admin, NotAdmin
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember
from checks.IsInDev import is_in_dev, InDevelopment

# Since time is important for this application the strategy is as follows:
# Create datetime 
# Store as timestamp integer (this strips TZ info and stored value is not timezone specific)
# Any Values displayed will utilize discord <t:[timestamp]:f> for accessing
#   Unless monospaced format is wanted (ie: ``` ```) for formating purposes, will display as EST timezone (need to assign tz info)
# Any stored values NOT as integer timestamps are for info/debug ONLY do not access isoformats




class Clocks(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.state_lock = asyncio.Lock()
        
        print('Initilization on clocks complete', flush=True)
    
    def cog_check(self, ctx):
        if ctx.guild is None:
            raise NotCommandChannel()
        config = self.get_config(ctx.guild.id)
        if ctx.channel_id in config['command_channels']:
            return True
        raise NotCommandChannel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        missing_tables = await db.check_tables(['historical', 'session', 'session_history', 'active', 'commands'])
        if missing_tables:
            print(f"Warning, missing the following tables in db: {missing_tables}")
    
    async def cog_before_invoke(self, ctx):
        now = datetime.datetime.now(tz)
        now = now.replace(microsecond = 0)
        guild_id = None
        if not ctx.guild:
            guild_id = 'DM'
        else:
            guild_id = ctx.guild.id
        print(f'{now.isoformat()} [{guild_id}] - Command {ctx.command.qualified_name} by {ctx.author.name} - {ctx.author.id}', flush=True)
        command = {'command_name': ctx.command.qualified_name, 'options': str(ctx.selected_options), 'datetime': now.isoformat(), 'user': ctx.author.id, 'user_name': ctx.author.name, 'channel_name': ctx.channel.name}
        await db.store_command(guild_id, command)
        return
    
    # ==============================================================================
    # Error Handlers
    # ==============================================================================
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        now = datetime.datetime.now(tz).replace(microsecond = 0)
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
    
    # ==============================================================================
    # Init/Reconnection events
    # ==============================================================================
    @commands.Cog.listener()
    async def on_guild_join(guild):
        print(f'Joined {guild} guild', flush=True)
    
    @commands.Cog.listener()
    async def on_connect(self):
        print(f'clocks connected to discord',flush=True)
        await db.set_db_to_wal()
        
    # ==============================================================================
    # All User Commands
    # ============================================================================== 

    @commands.slash_command(name='getconfig', description='Ephemeral optional - Get bot configuration')
    async def _get_config(self, ctx, public: discord.Option(bool, name='public', default=False)):
        if ctx.guild is None:
            await ctx.send_response(content='This command can not be used in Direct Messages')
            return
        config = self.get_config(ctx.guild.id)
        await ctx.send_response(content=f"{config}", ephemeral=not public)
    
    # ==============================================================================
    # Activity Commands
    # ==============================================================================
    @commands.slash_command(name='getactive', description='Ephemeral optional - Get list of active users in the session')
    @is_member()
    async def _get_active(self, ctx, public: discord.Option(bool, name='public', default=False)):
        actives = await db.get_all_actives(ctx.guild.id)
        now = int(datetime.datetime.now().timestamp())
        if len(actives) == 0:
            await ctx.send_response(content=f"There are no active users at this time", ephemeral=not public)
            return
        content = "_ _\nActive Users:\n```"
        for active in actives:
            user = await ctx.guild.fetch_member(active['user'])
            delta = get_hours_from_secs(now - active['in_timestamp'])
            content += f"\n{user.display_name[:19]:20}{delta:.2f} hours active"
        content += "```"
        await ctx.send_response(content=content, ephemeral=not public)
    
    
    @commands.slash_command(name='clockin', description='Clock into the active session')
    @is_member()
    @is_member_visible()
    @is_command_channel()
    async def _clockin(self, ctx, character: discord.Option(str, name='character', required=False, default='')):
        # Session Check
        session = await db.get_session(ctx.guild.id)
        if not session:
            await ctx.send_response(content=f'Sorry, there is no current session to clock into')
            return
        # Already active check
        actives = await db.get_all_actives(ctx.guild.id)
        
        
        for active in actives:
            if active['user'] == ctx.author.id:
                await ctx.send_response(content=f'You are already active, did you mean to clockout?')
                return
        
        now = datetime.datetime.now(tz)
        # Create entry and store
        doc = {
                'user': ctx.author.id,
                'character': character,
                'session': session['session'],
                'in_timestamp': int(now.timestamp()),
                'out_timestamp': '',
                '_DEBUG_user_name': ctx.author.display_name,
                '_DEBUG_in': now.isoformat(),
                '_DEBUG_out': '',
                '_DEBUG_delta': '',
            }
        
        await db.store_active_record(ctx.guild.id, doc)
        await ctx.send_response(content=f'{ctx.author.display_name} Successfuly clocked in at <t:{doc["in_timestamp"]}:f>')
        
        config = self.get_config(ctx.guild.id)
        if 'max_active' in config.keys() and config['max_active'] < len(actives)+1:
            actives = await db.get_all_actives(ctx.guild.id)
            content = f'Max number of active users is {config["max_active"]}, we are at {len(actives)} currently'
            for active in actives:
                content += f', <@{active["user"]}>'
            content = content + " please reduce active users"
            await ctx.send_followup(content=content)
            return
        return
    
    @commands.slash_command(name='clockout', description='Clock out of the active session')
    @is_member()
    @is_member_visible()
    @is_command_channel()
    async def _clockout(self, ctx):
        res = await self._inner_clockout(ctx, ctx.author.id)
        await ctx.send_response(content=res['content'])
        if res['status'] == False:
            return
        bonus_sessions = await self.get_bonus_sessions(ctx.guild.id, res['record'], res['row'])
        for item in bonus_sessions:
            row = await db.store_new_historical(ctx.guild.id, item)
            tot = await db.get_user_hours(ctx.guild.id, ctx.author.id)
            await ctx.send_followup(content=f'{ctx.author.display_name} Obtained bonus hours, stored record #{row} for {item["_DEBUG_delta"]} hours. Your total is at {round(tot, 2)}')
            
    async def get_bonus_sessions(self, guild_id, record, row):
        config = self.get_config(guild_id)
        if not config.get('bonus_hours'):
            return None
        bonuses = []
        
        for bonus in config['bonus_hours']:
            _in = datetime.datetime.fromtimestamp(record['in_timestamp'], tz)
            _out = datetime.datetime.fromtimestamp(record['out_timestamp'], tz)
            for day in range((_out.date() - _in.date()).days+1):
                bonus_in = datetime.datetime.combine(_in.date()+datetime.timedelta(days=day), datetime.time.fromisoformat(bonus['start']), tz)
                bonus_out = datetime.datetime.combine(_in.date()+datetime.timedelta(days=day), datetime.time.fromisoformat(bonus['end']), tz)
                if _in <= bonus_out and _out >= bonus_in:
                    now = datetime.datetime.now(tz).replace(microsecond = 0)
                    print(f'{now.isoformat()} [{guild_id}] - Bonus hours found for {record["_DEBUG_user_name"]}', flush=True)
                    #we have an intersection
                    #duration calculation
                    duration = int(min(_out.timestamp()-_in.timestamp(), 
                                   _out.timestamp()-bonus_in.timestamp(), 
                                   bonus_out.timestamp()-_in.timestamp(), 
                                   bonus_out.timestamp()-bonus_in.timestamp()))
                    duration = int(duration * (bonus['pct']/100))
                    start = _in if _in > bonus_in else bonus_in
                    rec = copy.deepcopy(record)
                    rec['character'] = f'{bonus["pct"]}_PCT_BONUS_{bonus["start"]}_TO_{bonus["end"]} {row}'
                    rec['in_timestamp'] = int(start.timestamp())
                    rec['out_timestamp'] = int(start.timestamp()+duration)
                    rec['_DEBUG_in'] = start.isoformat()
                    rec['_DEBUG_out'] = (start + datetime.timedelta(seconds=duration)).isoformat()
                    rec['_DEBUG_delta'] = get_hours_from_secs(duration)
                    bonuses.append(rec)
        return bonuses

    async def _inner_clockout(self, ctx, user_id):
        # Session Check
        session = await db.get_session(ctx.guild.id)
        if not session:
            return {'status': False, 'record': None, 'row': None, 'content': f'Sorry, there is no current session to clock out of'}
        
        # Ensure user was unique in active
        actives = await db.get_all_actives(ctx.guild.id)
        found = [_ for _ in actives if _['user'] == user_id]
        if not found:
            return {'status': False, 'record': None, 'row': None, 'content': f'Did not find you in active records, did you forget to clock in?'}
        if len(found) > 1:
            #error somehow they are clocked in more then once
            raise ValueError(f'Error - user was clocked in more then once guild: {ctx.guild.id} - user: {user_id}')
            return {'status': False, 'record': found, 'row': None, 'content': f'Error - user was clocked in more then once guild: {ctx.guild.id} - user: {user_id}'}
        record = found[0]
        
        res = await db.remove_active_record(ctx.guild.id, record)
        
        
        _out = datetime.datetime.now(tz)
        record['_DEBUG_out'] = _out.isoformat()
        record['out_timestamp'] = int(_out.timestamp())
        record['_DEBUG_delta'] = get_hours_from_secs(record['out_timestamp']-record['in_timestamp'])
        
        res = await db.store_new_historical(ctx.guild.id, record)
        
        if not res:
            return {'status': False, 'record': record, 'row': None, 'content': f'Failed to store record to historical, contact admin\n{found}'}
        tot = await db.get_user_hours(ctx.guild.id, user_id)
        user = await ctx.guild.fetch_member(user_id)
        return {'status': True,'record': record, 'row': res, 'content': f'{user.display_name} Successfuly clocked out at <t:{record["out_timestamp"]}>, stored record #{res} for {record["_DEBUG_delta"]} hours. Your total is at {round(tot, 2)}'}
    

    # ==============================================================================
    # Session Commands
    # ==============================================================================
    @commands.slash_command(name='getsession', description='Ephemeral - Get information about the active session')
    @is_member()
    async def _getsession(self, ctx):
        session = await db.get_session(ctx.guild.id)
        if not session:
            content = f'There is no active session right now.'
            await ctx.send_response(content=content, ephemeral=True)
            return
        start_timestamp = session["start_timestamp"]
        content = f'Session \"{session["session"]}\" started at <t:{start_timestamp}:f> local'
        await ctx.send_response(content=content, ephemeral=True)
        return
        
    @commands.slash_command(name='sessionstart', description='Start an session, only one session is allowed at a time')
    @is_member()
    @is_member_visible()
    @is_command_channel()
    async def _sessionstart(self, ctx, sessionname: discord.Option(str, name="session_name", required=True)):
        content = f"I'm busy updating, please try again later"
        await self.state_lock.acquire()
        try:
            session = await db.get_session(ctx.guild.id)
            if not session:
                now = datetime.datetime.now(tz)
                session = {
                           'session': sessionname,
                           'created_by': ctx.author.id,
                           'ended_by': '',
                           'start_timestamp': int(now.timestamp()),
                           'end_timestamp': 0,
                           '_DEBUG_start': now.isoformat(),
                           '_DEBUG_started_by': ctx.author.name,
                           '_DEBUG_end': '',
                           '_DEBUG_ended_by': '',
                           '_DEBUG_delta': '',
                           }
                row = await db.set_session(ctx.guild.id, session)
                content = f'Session {session["session"]} started at <t:{session["start_timestamp"]}:f> - {row}'
                if not row:
                    content = f'Session start failed session names must be unique, try again or contact an administrator'
            else:
                content = f'Sorry, a session, {session["session"]}, is already in place, please end the session before starting a new one'
        finally:
            self.state_lock.release()
        await ctx.send_response(content=content)
        
      
    @commands.slash_command(name='sessionend', description='Ends active session, clocking out all active users in the process')
    @is_member()
    @is_member_visible()
    @is_command_channel()
    async def _sessionend(self, ctx):
        content = f"I'm busy updating, please try again later"
        await self.state_lock.acquire()
        try:
            session = await db.get_session(ctx.guild.id)
            if session:
                now = datetime.datetime.now(tz)
                session['ended_by'] = ctx.author.id
                session['end_timestamp'] = int(now.timestamp())
                session['_DEBUG_end'] = now.isoformat()
                session['_DEBUG_ended_by'] = ctx.author.name
                session['_DEBUG_delta'] = get_hours_from_secs(session['end_timestamp'] - 
                                                              session['start_timestamp'])
                
                actives = await db.get_all_actives(ctx.guild.id)
                close_outs = []
                fails = []
                
                for active in actives:
                    res = await self._inner_clockout(ctx, active["user"])
                    close_outs.append((res['record']['_DEBUG_user_name'], res['record']['_DEBUG_delta']))
                    if not res['status']:
                        fails.append(active)
                        continue
                    bonus_sessions = await self.get_bonus_sessions(ctx.guild.id, res['record'], res['row'])
                    for item in bonus_sessions:
                        row = await db.store_new_historical(ctx.guild.id, item)
                        close_outs.append((item['_DEBUG_user_name'], f'Bonus id#{row}', item['_DEBUG_delta']))
                content = f'Session, {session["session"]} ended and lasted {session["_DEBUG_delta"]} hours'
                if close_outs:       
                    content += f'\nAutomagically closed out {close_outs}'
                if fails:
                    content += f'\nFailed to close out record {fails}, contact administrator'
                
                await db.store_historical_session(ctx.guild.id, session)
                await db.delete_session(ctx.guild.id)
            else:
                content=f'Sorry there is no current session to end'
        finally:
            self.state_lock.release()
        await ctx.send_response(content=content)
    
    # ==============================================================================
    # Utility/Fetch Commands
    # ==============================================================================
    
        
    
    @commands.slash_command(name='list', description='Ephemeral optional - Gets list of users that have accrued time, ordered by highest hours urned')
    @is_member()
    async def _list(self, ctx, public: discord.Option(bool, name='public', default=False)):
        # List all users in ranked order
        # get unique users
        users = await db.get_unique_users(ctx.guild.id)
        
        res = await db.get_users_hours(ctx.guild.id, users)
        
        sorted_res = sorted(res, key= lambda user: user['total'], reverse=True)
        content = '_ _\nUsers sorted by total time:'
        for item in sorted_res:
            content += f'\n<@{item["user"]}> has {item["total"]:.2f}'
        await ctx.send_response(content=content, ephemeral=not public, allowed_mentions=discord.AllowedMentions(users=False))
        return
    
    @commands.slash_command(name='urn', description='For use when you have obtained an urn')
    @is_member()
    @is_member_visible()
    @is_command_channel()
    async def _urn(self, ctx):
        actives = await db.get_all_actives(ctx.guild.id)
        for active in actives:
            if active['user'] == ctx.author.id:
                await ctx.send_response(content=f'Please clock out before attempting to claim your Urn')
                return
        view = ClearOutView()
        await ctx.respond("Did you really get an URN!?! Are you ready to clear out your dkp/time to 0?", view=view)
        await view.wait()
        if view.result == None:
            # Time out
            return
        elif view.result == True:
            tot = await db.get_user_seconds(ctx.guild.id, ctx.author.id)
            session = await db.get_session(ctx.guild.id)
            session_name = ''
            if session:
                session_name = session['session']
            now = datetime.datetime.now(tz)
            hours = get_hours_from_secs(tot)
            doc = {
                'user': ctx.author.id,
                'character': f"URN_ZERO_OUT_EVENT -{hours}",
                'session': session_name,
                'in_timestamp': int(now.timestamp()),
                'out_timestamp': (now.timestamp())-tot,
                '_DEBUG_user_name': ctx.author.display_name,
                '_DEBUG_in': now.isoformat(),
                '_DEBUG_out': now.isoformat(),
                '_DEBUG_delta': -1*hours,
            }
            res = await db.store_new_historical(ctx.guild.id, doc)
            if not res:
                print(f"Clearout failure\n {doc}", flush=True)
            await view.message.edit(content=f"Ooooh, yes! :urn: :tada: {hours} hours well spent!")
            return
        else:
            # User Aborted
            return
    
    # return last # commands
    @commands.slash_command(name='getcommands', description='Ephemeral - Get a list of historical commands submitted to the bot by a user')
    @is_member()
    async def _get_commands(self, ctx, 
                            _id: discord.Option(str, name="user_id", required=False, default=0),
                            startat: discord.Option(int, name="start_at", required=False, default=0), 
                            count: discord.Option(int, name="count", required=False, default=10)):
        if _id == 0:
            _id = ctx.author.id
        try:
            _id = int(id)
        except ValueError as err:
            ctx.send_response(content=f'id must be a valid integer {err}', ephemeral=True)
            return
        res = await db.get_user_commands_history(ctx.guild.id, _id, start_at=int(startat), count=int(count))
        content = f"<@{_id}>'s last {len(res)} commands"
        if startat:
            content += f", starting at user's {startat}'th most recent command"
        if res:
            content += '```'
        for item in res:
            del item['server']
            del item['user']
            del item['user_name']
            if item['options'] == 'None':
                del item['options']
            content += f"\n{str(item)}"
        content = content[:1990]
        if res:
            content += '```'
        await ctx.send_response(content=content, ephemeral=True)
        pass
    
    # Gets last 20 commands by user, returned as an ephemeral message or maybe all commands as an attached doc?
    @commands.user_command(name="Get User Commands")
    @is_member()
    async def _get_user_commands(self, ctx, member: discord.Member):
        res = await db.get_user_commands_history(ctx.guild.id, member.id)
        content = f"<@{member.id}>'s last {len(res)} commands"
        if res:
            content += '```'
        for item in res:
            del item['server']
            del item['user']
            del item['user_name']
            if item['options'] == 'None':
                del item['options']
            content += f"\n{str(item)}"
        
        content = content[:1990]
        if res:
            content += '```'
        await ctx.send_response(content=content, ephemeral=True)
        pass
    
    # Gets last 20 commands by user, returned as an ephemeral message or maybe all commands as an attached doc?
    @commands.user_command(name="Get User Time")
    @is_member()
    async def _get_user_time(self, ctx, member: discord.Member):
        tot = await db.get_user_hours(ctx.guild.id, member.id)
        await ctx.send_response(content=f'{member.display_name} has accrued {tot:.2f} hours', ephemeral=True)
    
    @commands.slash_command(name="getusersessions", description='Ephemeral - Get list of user\'s historical sessions')
    @is_member()
    async def _cmd_get_user_sessions(self, ctx, 
                                    _id: discord.Option(str, name="user_id", required=False),
                                    _timetype: discord.Option(str, name="timetype", choices=["Hours", "Seconds"], required=False, default='Hours'),
                                    _public: discord.Option(bool, name="public", required=False, default=False)):
        if _id == 0:
            _id = ctx.author.id
        try:
            _id = int(id)
        except ValueError as err:
            ctx.send_response(content=f'id must be a valid integer {err}', ephemeral=True)
            return
        res = await db.get_historical_user(ctx.guild.id, _id)
        if len(res) == 0:
            await ctx.send_response(content=f"{member.display_name} has no recorded sessions", ephemeral=True)
            return
        chunks = []
        title = f"_ _\n<@{_id}> Sessions:\n"
        content = ""
        for item in res:
            _in = datetime.datetime.fromtimestamp(item['in_timestamp'], tz)
            _out = datetime.datetime.fromtimestamp(item['out_timestamp'], tz)
            ses_hours = "Null"
            if _timetype == 'Hours':
                ses_hours = get_hours_from_secs(item['out_timestamp'] - item['in_timestamp'])
            elif _timetype == 'Seconds':
                ses_hours = item['out_timestamp'] - item['in_timestamp']
            catagory = "  "
            if "_PCT_BONUS_" in item['character']:
                catagory = " +"
            elif item['character'].startswith("URN_ZERO_OUT_EVENT"):
                catagory = "⚱️"
            elif item['character'] == "SOLO_HOLD_BONUS":
                catagory = " S"
            elif item['character'] == "QUAKE_DS_BONUS":
                catagory = " Q"
            content += f"\n{item['rowid']:5} {_in.date().isoformat()} - {item['session'][:50]:50}  {catagory} from {_in.time().isoformat('seconds')} {tz} to {_out.time().isoformat('seconds')} {tz} for {ses_hours} {_timetype.lower()}"
            # Max message length is 2000, give 100 leway for title/user hours ending
            if len(content) >= 1850:
                clip_idx = content.rfind('\n', 0, 1850)
                if len(chunks) == 0:
                    chunks.append(content[:clip_idx])
                else:
                    chunks.append(content[:clip_idx])
                content = content[clip_idx:]
        
        tot = await db.get_user_hours(ctx.guild.id, _id)
        tail = f"\n<@{_id}> has accrued {tot} hours"        
        if res:
            chunks.append(content)
        
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                content = title+"```"+chunk+"```"
                if len(chunks) == 1:
                    content += tail
                await ctx.send_response(content=content, ephemeral=not _public, allowed_mentions=discord.AllowedMentions(users=False))
            elif len(chunks) == idx+1:
                await ctx.send_followup(content="```"+chunk+"```"+tail, ephemeral=not _public, allowed_mentions=discord.AllowedMentions(users=False))
            else:
                await ctx.send_followup(content="```"+chunk+"```", ephemeral=not _public, allowed_mentions=discord.AllowedMentions(users=False))
    
    
    
    #TODO condense this with slash command of same name
    @commands.user_command(name="Get User Sessions")
    @is_member()
    async def _get_user_sessions(self, ctx, member: discord.Member):
        await self._cmd_get_user_sessions(ctx, member.id, "Hours", False)
        return
                
    @commands.slash_command(name="getuserseconds", description='Get total number of seconds that a user has accrued')
    @is_member()
    async def _get_user_seconds(self, ctx,  id: discord.Option(str, name="user_id", required=False)):
        if _id == 0:
            _id = ctx.author.id
        try:
            _id = int(id)
        except ValueError as err:
            ctx.send_response(content=f'id must be a valid integer {err}', ephemeral=True)
            return
        res = await db.get_user_commands_history(ctx.guild.id, _id, start_at=int(startat), count=int(count))
        secs = await db.get_user_seconds(ctx.guild.id, id)
        await ctx.send_response(content=f'{id} has {secs}')
    
    # ==============================================================================
    # Admin functions
    # ==============================================================================   
    @commands.slash_command(name="admincommand", description='Command to confirm the user is an admin')
    @is_admin()
    async def _admincommand(self, ctx):
        await ctx.send_response(content=f'You\'re an admin!')
        
    @commands.slash_command(name='admindirecturn', description='Admin command to directly urn a user')
    @is_admin()
    @is_member()
    @is_member_visible()
    async def _directurn(self, ctx, 
                        sessionname: discord.Option(str, name="sessionname", required=True),
                        userid: discord.Option(str, name="userid", required=True),
                        username: discord.Option(str, name="username", required=True),
                        date: discord.Option(str, name="killdate", description="Form YYYY-MM-DD", required=True),
                        time: discord.Option(str, name="killtime", description="Form HH:MM in EST", required=True)):
        if userid == 0:
            userid = ctx.author.id
        try:
            userid = int(id)
        except ValueError as err:
            ctx.send_response(content=f'id must be a valid integer {err}', ephemeral=True)
            return
        secs = await db.get_user_seconds(ctx.guild.id, userid)
        hours = get_hours_from_secs(secs)
        datetime_kill = datetime.datetime.fromisoformat(date+"T"+time+":00-05:00")
        rev_timestamp = datetime_kill.timestamp() - secs
        rev_datetime = datetime.datetime.fromtimestamp(rev_timestamp, tz)
        doc = {
                'user': int(userid),
                'character': f"URN_ZERO_OUT_EVENT -{hours}",
                'session': sessionname,
                'in_timestamp': int(datetime_kill.timestamp()),
                'out_timestamp': int(rev_timestamp),
                '_DEBUG_user_name': username,
                '_DEBUG_in': datetime_kill.isoformat(),
                '_DEBUG_out': rev_datetime.isoformat(),
                '_DEBUG_delta': -1*hours,
            }
        try:
            res = await db.store_new_historical(ctx.guild.id, doc)
        except OperationalError as err:
            await ctx.send_response(content=f'Failed, database error - {err}, please try again or contact an administator')
            return
        if not res:
            await ctx.send_response(content=f'Something went wrong, return index 0 please contact an administator')
            return
        tot = await db.get_user_hours(ctx.guild.id, int(userid))
        await ctx.send_response(content=f'{username} - <@{int(userid)}> Successfuly URNed and stored record #{res} for {doc["_DEBUG_delta"]} hours. Total is at {tot}')
        
    @commands.slash_command(name='adminchangehistory', description='Admin command to change a historical record of a user')
    @is_admin()
    @is_member()
    @is_member_visible()
    async def _adminchangehistory(self, ctx,
                                  row: discord.Option(str, name="recordnumber", required=True),
                                  _type: discord.Option(str, name="type", choices=['Clock in time', 'Clock out time'], required=True),
                                  _date: discord.Option(str, name="date", description="Form YYYY-MM-DD", required=True),
                                  time: discord.Option(str, name="time", description="24 hour clock, 12pm midnight is 00:00", required=True)):
        if _id == 0:
            _id = ctx.author.id
        try:
            _id = int(id)
        except ValueError as err:
            ctx.send_response(content=f'id must be a valid integer {err}', ephemeral=True)
            return
            
        rec = await db.get_historical_record(ctx.guild.id, row)
        
        if len(rec) == 0 or len(rec) > 1:
            await ctx.send_response(content=f'Could not find record #{row} for guild {ctx.guild.id}')
            return
        rec = rec[0]
        
        was = {}
        if len(time) == 4:
            time = "0" + time
        time += "-05:00"
        arg_date = datetime.date.fromisoformat(_date)
        _datetime = datetime.datetime.combine(arg_date, datetime.time.fromisoformat(time))
        if _type == 'Clock in time':
            was['timestamp'] = rec['in_timestamp']
            was['_DEBUG'] = rec['_DEBUG_in']
            rec['in_timestamp'] = _datetime.timestamp()
            rec['_DEBUG_in'] = _datetime.isoformat()
            
        elif _type == 'Clock out time':
            was['timestamp'] = rec['out_timestamp']
            was['_DEBUG'] = rec['_DEBUG_out']
            rec['out_timestamp'] = _datetime.timestamp()
            rec['_DEBUG_out'] = _datetime.isoformat()
        else:
            await ctx.send_response(content=f'Invalid option {_type}')
            return
            
        rec['_DEBUG_delta'] = get_hours_from_secs(rec['out_timestamp']-rec['in_timestamp'])    
        res = await db.delete_historical_record(ctx.guild.id, row)
        res = await db.store_new_historical(ctx.guild.id, rec)
        await ctx.send_response(content=f'Updated record #{row}, {_type} from {was["_DEBUG"]} to {_datetime.isoformat()} for user <@{rec["user"]}>', allowed_mentions=discord.AllowedMentions(users=False))
        
    
    @commands.slash_command(name='admindirectrecord', description='Admin command to add a historical record of a user')
    @is_admin()
    @is_member()
    @is_member_visible()
    async def _directrecord(self, ctx,  
                            sessionname: discord.Option(str, name="sessionname", required=True),
                            userid: discord.Option(str, name="userid", required=True),
                            username: discord.Option(str, name="username", required=True),
                            date: discord.Option(str, name="startdate", description="Form YYYY-MM-DD", required=True),
                            intime: discord.Option(str, name="intime", description="Form HH:MM in EST", required=True),
                            outtime: discord.Option(str, name="outtime", description="Form HH:MM in EST", required=True),
                            character: discord.Option(str, name="character", default=''),
                            dayafter: discord.Option(str, name="dayafter", choices=['True', 'False'], description="Did clockout occur the day after in?", default='False')):
        if _id == 0:
            _id = ctx.author.id
        try:
            _id = int(id)
        except ValueError as err:
            ctx.send_response(content=f'id must be a valid integer {err}', ephemeral=True)
            return
        if len(intime) == 4:
            intime = "0" + intime
        if len(outtime) == 4:
            outtime = "0" + outtime
        intime += "-05:00"
        outtime += "-05:00"
        arg_date = datetime.date.fromisoformat(date)
        in_datetime = datetime.datetime.combine(arg_date, datetime.time.fromisoformat(intime))
        if dayafter == "True":
            out_datetime = datetime.datetime.combine(arg_date+datetime.timedelta(days=1), datetime.time.fromisoformat(outtime))
        else:
            out_datetime = datetime.datetime.combine(arg_date, datetime.time.fromisoformat(outtime))
        in_timestamp = int(in_datetime.timestamp())
        out_timestamp = int(out_datetime.timestamp())
        doc = {
                'user': int(userid),
                'character': character,
                'session': sessionname,
                'in_timestamp': in_timestamp,
                'out_timestamp': out_timestamp,
                '_DEBUG_user_name': username,
                '_DEBUG_in': in_datetime.isoformat(),
                '_DEBUG_out': out_datetime.isoformat(),
                '_DEBUG_delta': get_hours_from_secs(out_timestamp-in_timestamp),
            }
        try:
            res = await db.store_new_historical(ctx.guild.id, doc)
        except OperationalError as err:
            await ctx.send_response(content=f'Failed, database error - {err}, please try again or contact an administator')
            return
        if not res:
            await ctx.send_response(content=f'Something went wrong, return index 0 please contact an administator')
            return
        tot = await db.get_user_hours(ctx.guild.id, int(userid))
        await ctx.send_response(content=f'{username} - <@{int(userid)}> Successfuly clocked out and stored record #{res} for {doc["_DEBUG_delta"]} hours. Total is at {tot}')
    
    # ==============================================================================
    # Data functions
    # ==============================================================================
    
    @commands.slash_command(name='getdata', description='Command to retrive all data of a table')
    @is_member()
    async def _getdata(self, ctx, data_type=discord.Option(name='datatype', choices=['actives','historical','session', 'historicalsession', 'commands', 'errors'], default='historical')):
        res = await db.flush_wal()
        if not res:
            await ctx.send_response(content='Couldn\'t flush journal, possible multiple connections active, contact administrator')
            return
        if data_type == 'historical':
            data = await db.get_historical(ctx.guild.id)
        elif data_type == 'actives':
            data = await db.get_all_actives(ctx.guild.id)
        elif data_type == 'session':
            data = [await db.get_session(ctx.guild.id)]
        elif data_type == 'commands':
            data = await db.get_commands_history(ctx.guild.id)
        else:
            await ctx.send_response(content='Option not available yet')
            return
        out_file = Path('/temp/data.json')
        out_file.parent.mkdir(exist_ok=True, parents=True)
        json.dump(data, open('temp/data.json', 'w', encoding='utf-8'), indent=1)
        await ctx.send_response(content='Here\'s the data!', file=discord.File('temp/data.json', filename='data.json'))
        return
    
    def get_config(self, guild_id):
        return json.load(open('data/config.json', 'r', encoding='utf-8')).get(str(guild_id))
    



def setup(bot):
    cog = Clocks(bot)
    
    bot.add_cog(Clocks(bot))