import discord
from discord.ext import commands
import json
import datetime
import asyncio
import aiosqlite
from pathlib import Path
from pytz import timezone
tz = timezone('EST')

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

SECS_IN_MINUTE = 60
MINUTE_IN_HOUR = 60
SECS_IN_HOUR = MINUTE_IN_HOUR * SECS_IN_MINUTE



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
    async def on_ready(ctx):
        #print('clocks on_ready')
        pass
        
    
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
        await self.store_command(guild_id, command)
        return
    
    # ==============================================================================
    # Error Handlers
    # ==============================================================================
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        now = datetime.datetime.now(tz)
        now = now.replace(microsecond = 0)
        guild_id = None
        channel_name = None
        if not ctx.guild:
            guild_id = 'DM'
            channel_name = 'DM'
        else:
            guild_id = ctx.guild.id
            channel_name = ctx.channel.name
        print(f'{now.isoformat()} [{guild_id}] - Error in command {ctx.command.qualified_name} by {ctx.author.name} - {ctx.author.id}', flush=True)
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
    # DEBUG FUNCTIONS NEEDS TO BE DELETED
    # ==============================================================================
    @commands.slash_command(name="admincommand", description='Command to confirm the user is an admin')
    @is_admin()
    async def _admincommand(self, ctx):
        await ctx.send_response(content='You\'re an admin!')
    
    # ==============================================================================
    # Init/Reconnection events
    # ==============================================================================
    @commands.Cog.listener()
    async def on_guild_join(guild):
        print(f'Joined {guild} guild', flush=True)
    
    @commands.Cog.listener()
    async def on_connect(self):
        print(f'clocks connected to discord',flush=True)
        async with aiosqlite.connect('data/urnby.db') as db:
            query = f"PRAGMA journal_mode=WAL"
            res = await db.execute(query)
            print(f"Database mode set to: {await res.fetchall()}",flush=True)
            await db.commit() 
        
    # ==============================================================================
    # All User Commands
    # ============================================================================== 

    @commands.slash_command(name='getconfig', description='Ephemeral optional - Get bot configuration')
    async def _get_config(self, ctx, public: discord.Option(name='public', input_type=bool, default=False)):
        if ctx.guild is None:
            await ctx.send_response(content='This command can not be used in Direct Messages')
            return
        config = self.get_config(ctx.guild.id)
        await ctx.send_response(content=config, ephemeral=not public)
    
    # ==============================================================================
    # Activity Commands
    # ==============================================================================
    @commands.slash_command(name='getactive', description='Ephemeral optional - Get list of active users in the session')
    @is_member()
    async def _get_active(self, ctx, public: discord.Option(name='public', input_type=bool, default=False)):
        actives = await self.get_all_actives(ctx.guild.id)
        now = int(datetime.datetime.now().timestamp())
        if len(actives) == 0:
            await ctx.send_response(content=f"There are no active users at this time", ephemeral=not public)
            return
        content = "_ _\nActive Users:\n```"
        for active in actives:
            user = await ctx.guild.fetch_member(active['user'])
            delta = get_hours_from_secs(now - active['in_timestamp'])
            content += f"\n{user.display_name:20}{delta:.2f} hours active"
        content += "```"
        await ctx.send_response(content=content, ephemeral=not public)
    
    
    @commands.slash_command(name='clockin', description='Clock into the active session')
    @is_member()
    @is_member_visible()
    @is_command_channel()
    async def _clockin(self, ctx, character: discord.Option(name='character', input_type=str, required=False, default='')):
        # Session Check
        session = await self.get_session(ctx.guild.id)
        if not session:
            await ctx.send_response(content=f'Sorry, there is no current session to clock into')
            return
        # Already active check
        actives = await self.get_all_actives(ctx.guild.id)
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
        
        await self.store_active_record(ctx.guild.id, doc)
        
        await ctx.send_response(content=f'{ctx.author.display_name} Successfuly clocked in at <t:{doc["in_timestamp"]}:f>')
        return
    
    @commands.slash_command(name='clockout', description='Clock out of the active session')
    @is_member()
    @is_member_visible()
    @is_command_channel()
    async def _clockout(self, ctx):
        res = await self._inner_clockout(ctx, ctx.author.id)
        await ctx.send_response(content=res['content'])
    
    async def _inner_clockout(self, ctx, user_id):
        # Session Check
        session = await self.get_session(ctx.guild.id)
        if not session:
            return {'status': False, 'record': None, 'content': f'Sorry, there is no current session to clock out of'}
        
        # Ensure user was unique in active
        actives = await self.get_all_actives(ctx.guild.id)
        found = [_ for _ in actives if _['user'] == user_id]
        if not found:
            return {'status': False, 'record': None, 'content': f'Did not find you in active records, did you forget to clock in?'}
        if len(found) > 1:
            #error somehow they are clocked in more then once
            raise ValueError(f'Error - user was clocked in more then once guild: {ctx.guild.id} - user: {user_id}')
            return {'status': False, 'record': found, 'content': f'Error - user was clocked in more then once guild: {ctx.guild.id} - user: {user_id}'}
        record = found[0]
        
        res = await self.remove_active_record(ctx.guild.id, record)
        
        
        _out = datetime.datetime.now(tz)
        record['_DEBUG_out'] = _out.isoformat()
        record['out_timestamp'] = int(_out.timestamp())
        record['_DEBUG_delta'] = get_hours_from_secs(record['out_timestamp']-record['in_timestamp'])
        
        res = await self.store_new_historical(ctx.guild.id, record)
        
        if not res:
            return {'status': False, 'record': record, 'content': f'Failed to store record to historical, contact admin\n{found}'}
        tot = await self.get_user_hours(ctx.guild.id, user_id)
        user = await ctx.guild.fetch_member(user_id)
        return {'status': True,'record': record, 'content': f'{user.display_name} Successfuly clocked out at <t:{record["out_timestamp"]}>, stored record for {record["_DEBUG_delta"]} hours. Your total is at {round(tot, 2)}'}
    

    # ==============================================================================
    # Session Commands
    # ==============================================================================
    @commands.slash_command(name='getsession', description='Ephemeral - Get information about the active session')
    @is_member()
    async def _getsession(self, ctx):
        session = await self.get_session(ctx.guild.id)
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
    async def _sessionstart(self, ctx, sessionname: discord.Option(name="session_name", input_type=str, required=True)):
        content = f"I'm busy updating, please try again later"
        await self.state_lock.acquire()
        try:
            session = await self.get_session(ctx.guild.id)
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
                row = await self.set_session(ctx.guild.id, session)
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
            session = await self.get_session(ctx.guild.id)
            if session:
                now = datetime.datetime.now(tz)
                session['ended_by'] = ctx.author.id
                session['end_timestamp'] = int(now.timestamp())
                session['_DEBUG_end'] = now.isoformat()
                session['_DEBUG_ended_by'] = ctx.author.name
                session['_DEBUG_delta'] = get_hours_from_secs(session['end_timestamp'] - 
                                                              session['start_timestamp'])
                
                actives = await self.get_all_actives(ctx.guild.id)
                close_outs = []
                fails = []
                
                for active in actives:
                    res = await self._inner_clockout(ctx, active["user"])
                    close_outs.append((res['record']['_DEBUG_user_name'], res['record']['_DEBUG_delta']))
                    if not res['status']:
                        fails.append(active)
                        
                content = f'Session, {session["session"]} ended and lasted {session["_DEBUG_delta"]} hours'
                if close_outs:       
                    content += f'\nAutomagically closed out {close_outs}'
                if fails:
                    content += f'\nFailed to close out record {fails}, contact administrator'
                
                await self.store_historical_session(ctx.guild.id, session)
                await self.delete_session(ctx.guild.id)
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
    async def _list(self, ctx, public: discord.Option(name='public', input_type=bool, default=False)):
        # List all users in ranked order
        # get unique users
        users = await self.get_unique_users(ctx.guild.id)
        
        res = await self.get_users_hours(ctx.guild.id, users)
        
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
        view = ClearOutView()
        await ctx.respond("Did you really get an URN!?! Are you ready to clear out your dkp/time to 0?", view=view)
        await view.wait()
        if view.result == None:
            # Time out
            return
        elif view.result == True:
            tot = await self.get_user_seconds(ctx.guild.id, ctx.author.id)
            session = await self.get_session(ctx.guild.id)
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
            res = await self.store_new_historical(ctx.guild.id, doc)
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
                            _id: discord.Option(name="user_id", input_type=int, required=True),
                            startat: discord.Option(name="start_at", input_type=int, required=False, default=0), 
                            count: discord.Option(name="count", input_type=int, required=False, default=10)):
        res = await self.get_user_commands_history(ctx.guild.id, _id, start_at=int(startat), count=int(count))
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
        res = await self.get_user_commands_history(ctx.guild.id, member.id)
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
        tot = await self.get_user_hours(ctx.guild.id, member.id)
        await ctx.send_response(content=f'{member.display_name} has accrued {tot:.2f} hours', ephemeral=True)
    
    @commands.slash_command(name="getusersessions", description='Ephemeral - Get list of user\'s historical sessions')
    @is_member()
    async def _cmd_get_user_sessions(self, ctx, _id: discord.Option(name="user_id", input_type=int, required=True)):
        try:
            int(_id)
        except ValueError:
            content = f"The ID must be numerical, you can get this by right clicking a user and copy id"
            await ctx.send_response(content=content, ephemeral=True)
            return
        res = await self.get_historical_user(ctx.guild.id, _id)
        if len(res) == 0:
            await ctx.send_response(content=f"{member.display_name} has no recorded sessions", ephemeral=True)
            return
        chunks = []
        title = f"_ _\n<@{_id}> Sessions:\n"
        content = ""
        for item in res:
            _in = datetime.datetime.fromtimestamp(item['in_timestamp'], tz)
            _out = datetime.datetime.fromtimestamp(item['out_timestamp'], tz)
            ses_hours = get_hours_from_secs(item['out_timestamp'] - item['in_timestamp'])
            content += f"\n{item['rowid']:5} {_in.date().isoformat()} - {item['session'][:55]:55} from {_in.time().isoformat('seconds')} {tz} to {_out.time().isoformat('seconds')} {tz} for {ses_hours} hours"
            # Max message length is 2000, give 100 leway for title/user hours ending
            if len(content) >= 1850:
                clip_idx = content.rfind('\n', 0, 1850)
                if len(chunks) == 0:
                    chunks.append(content[:clip_idx])
                else:
                    chunks.append(content[:clip_idx])
                content = content[clip_idx:]
        
        tot = await self.get_user_hours(ctx.guild.id, _id)
        tail = f"\n<@{_id}> has accrued {tot} hours"        
        if res:
            chunks.append(content)
        
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                content = title+"```"+chunk+"```"
                if len(chunks) == 1:
                    content += tail
                await ctx.send_response(content=content, ephemeral=True)
            elif len(chunks) == idx+1:
                await ctx.send_followup(content="```"+chunk+"```"+tail, ephemeral=True)
            else:
                await ctx.send_followup(content="```"+chunk+"```", ephemeral=True)
    
    @commands.slash_command(name="getuserseconds", description='Get total number of seconds that a user has accrued')
    @is_member()
    async def _get_user_seconds(self, ctx,  id: discord.Option(name="user_id", input_type=int, required=True)):
        secs = await self.get_user_seconds(ctx.guild.id, id)
        await ctx.send_response(content=f'{id} has {secs}')
    
    #TODO condense this with slash command of same name
    @commands.user_command(name="Get User Sessions")
    @is_member()
    async def _get_user_sessions(self, ctx, member: discord.Member):
        res = await self.get_historical_user(ctx.guild.id, member.id)
        if len(res) == 0:
            await ctx.send_response(content=f"{member.display_name} has no recorded sessions", ephemeral=True)
            return
        chunks = []
        title = f"_ _\n<@{member.id}> Sessions:\n"
        content = ""
        for item in res:
            _in_date = datetime.datetime.fromtimestamp(item['in_timestamp'], tz).date().isoformat()
            _in = datetime.datetime.fromtimestamp(item['in_timestamp'], tz)
            _out = datetime.datetime.fromtimestamp(item['out_timestamp'], tz)
            ses_hours = get_hours_from_secs(item['out_timestamp']-item['in_timestamp'])
            content += f"\n{item['rowid']:5} {_in_date} - {item['session'][:55]:55} from {_in.time().isoformat('seconds')} {tz} to {_out.time().isoformat('seconds')} {tz} for {ses_hours:.2f} hours"
            # Max message length is 2000, give 100 leway for title/user hours ending
            if len(content) >= 1850:
                clip_idx = content.rfind('\n', 0, 1850)
                if len(chunks) == 0:
                    chunks.append(content[:clip_idx])
                else:
                    chunks.append(content[:clip_idx])
                content = content[clip_idx:]
        tot = await self.get_user_hours(ctx.guild.id, member.id)
        tail = f"\n<@{member.id}> has accrued {tot} hours"      
        if res:
            chunks.append(content)
        
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                content = title+"```"+chunk+"```"
                if len(chunks) == 1:
                    content += tail
                await ctx.send_response(content=content, ephemeral=True)
            elif len(chunks) == idx+1:
                await ctx.send_followup(content="```"+chunk+"```"+tail, ephemeral=True)
            else:
                await ctx.send_followup(content="```"+chunk+"```", ephemeral=True)
    
    
    # ==============================================================================
    # Admin functions
    # ==============================================================================    
    @commands.slash_command(name='admindirecturn', description='Admin command to directly urn a user')
    @is_admin()
    @is_member()
    @is_member_visible()
    async def _directurn(self, ctx, 
                        sessionname: discord.Option(name="sessionname", input_type=str, required=True),
                        userid: discord.Option(name="userid", input_type=int, required=True),
                        username: discord.Option(name="username", input_type=str, required=True),
                        date: discord.Option(name="killdate", description="Form YYYY-MM-DD", input_type=str, required=True),
                        time: discord.Option(name="killtime", description="Form HH:MM in EST", input_type=str, required=True)):
        secs = await self.get_user_seconds(ctx.guild.id, userid)
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
            res = await self.store_new_historical(ctx.guild.id, doc)
        except aiosqlite.OperationalError as err:
            await ctx.send_response(content=f'Failed, database error - {err}, please try again or contact an administator')
            return
        if not res:
            await ctx.send_response(content=f'Something went wrong, return index 0 please contact an administator')
            return
        tot = await self.get_user_hours(ctx.guild.id, int(userid))
        await ctx.send_response(content=f'{username} - <@{int(userid)}> Successfuly URNed and stored record #{res} for {doc["_DEBUG_delta"]} hours. Total is at {tot}')
        
    @commands.slash_command(name='adminchangehistory', description='Admin command to change a historical record of a user')
    @is_admin()
    @is_member()
    @is_member_visible()
    async def _adminchangehistory(self, ctx,
                                  row: discord.Option(name="recordnumber", input_type=int, required=True),
                                  
                                  _type: discord.Option(name="type", choices=['Clock in time', 'Clock out time'], input_type=str, required=True),
                                  _date: discord.Option(name="date", description="Form YYYY-MM-DD", required=True),
                                  time: discord.Option(name="time", description="24 hour clock, 12pm midnight is 00:00", input_type=str, required=True)):
        rec = await self.get_historical_record(ctx.guild.id, row)
        
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
        res = await self.delete_historical_record(ctx.guild.id, row)
        res = await self.store_new_historical(ctx.guild.id, rec)
        await ctx.send_response(content=f'Updated record #{row}, {_type} from {was["_DEBUG"]} to {_datetime.isoformat()} for user <@{rec["user"]}>', allowed_mentions=discord.AllowedMentions(users=False))
        
    
    @commands.slash_command(name='admindirectrecord', description='Admin command to add a historical record of a user')
    @is_admin()
    @is_member()
    @is_member_visible()
    async def _directrecord(self, ctx,  
                            sessionname: discord.Option(name="sessionname", input_type=str, required=True),
                            userid: discord.Option(name="userid", input_type=int, required=True),
                            username: discord.Option(name="username", input_type=str, required=True),
                            date: discord.Option(name="startdate", description="Form YYYY-MM-DD", input_type=str, required=True),
                            intime: discord.Option(name="intime", description="Form HH:MM in EST", input_type=str, required=True),
                            outtime: discord.Option(name="outtime", description="Form HH:MM in EST", input_type=str, required=True),
                            character: discord.Option(name="character", input_type=str, default=''),
                            dayafter: discord.Option(name="dayafter", choices=['True', 'False'], description="Did clockout occur the day after in?", input_type=str, default='False')):
        
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
            res = await self.store_new_historical(ctx.guild.id, doc)
        except aiosqlite.OperationalError as err:
            await ctx.send_response(content=f'Failed, database error - {err}, please try again or contact an administator')
            return
        if not res:
            await ctx.send_response(content=f'Something went wrong, return index 0 please contact an administator')
            return
        tot = await self.get_user_hours(ctx.guild.id, int(userid))
        await ctx.send_response(content=f'{username} - <@{int(userid)}> Successfuly clocked out and stored record #{res} for {doc["_DEBUG_delta"]} hours. Total is at {tot}')
    
    # ==============================================================================
    # Database functions
    # ==============================================================================
    
    async def flush_wal(self):
        async with aiosqlite.connect('data/urnby.db') as db:
            try:
                query = f"""PRAGMA journal_mode = DELETE"""
                res = await db.execute(query)
                await db.commit()
                print(f"Database mode set to: {await res.fetchall()}", flush=True)
                query = f"""PRAGMA journal_mode = WAL"""
                res = await db.execute(query)
                await db.commit()
                print(f"Database mode set to: {await res.fetchall()}", flush=True)
            except aiosqlite.OperationalError as err:
                print(f"Failed flushing WAL, are there multiple connections to the database?", flush=True)
                return False
        return True
        
    @commands.slash_command(name='getdata', description='Command to retrive all data of a table')
    @is_member()
    async def _getdata(self, ctx, data_type=discord.Option(name='datatype', choices=['actives','historical','session', 'historicalsession', 'commands', 'errors'], default='historical')):
        res = await self.flush_wal()
        if not res:
            await ctx.send_response(content='Couldn\'t flush journal, possible multiple connections active, contact administrator')
            return
        if data_type == 'historical':
            data = await self.get_historical(ctx.guild.id)
        elif data_type == 'actives':
            data = await self.get_all_actives(ctx.guild.id)
        elif data_type == 'session':
            data = [await self.get_session(ctx.guild.id)]
        elif data_type == 'commands':
            data = await self.get_commands_history(ctx.guild.id)
        else:
            await ctx.send_response(content='Option not available yet')
            return
        json.dump(data, open('temp/data.json', 'w', encoding='utf-8'), indent=1)
        await ctx.send_response(content='Here\'s the data!', file=discord.File('temp/data.json', filename='data.json'))
        return
    
    def get_config(self, guild_id):
        return json.load(open('data/config.json', 'r', encoding='utf-8')).get(str(guild_id))
    
    async def get_session(self, guild_id):
        res = {}
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"""SELECT rowid, * FROM session WHERE server = {guild_id}"""
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                if len(rows) < 1:
                    return None
                elif len(rows) > 1:
                    raise ValueError(f'Error, server {guild_id} has more then one active session {len(rows)}')
                res = dict(rows[0])
        return res
        
    async def set_session(self, guild_id, session):
        lastrow = 0
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            # Only one session allowed per server
            query = f"""SELECT count(*) FROM session WHERE server = {guild_id}"""
            async with db.execute(query) as cursor:
                res = await cursor.fetchall()
                if dict(res[0])['count(*)'] != 0:
                    return None
            # Session name must be unique
            query = f"""SELECT count(*) FROM session_history WHERE server = {guild_id} AND session = '{session['session']}'"""
            async with db.execute(query) as cursor:
                res = await cursor.fetchall()
                if dict(res[0])['count(*)'] != 0:
                    return None
                
            query = f"""INSERT INTO session(server,      session,  created_by,  _DEBUG_started_by,  _DEBUG_start,  start_timestamp,  ended_by,  _DEBUG_ended_by,  _DEBUG_end,  end_timestamp,  _DEBUG_delta)
                                     VALUES({guild_id}, :session, :created_by, :_DEBUG_started_by, :_DEBUG_start, :start_timestamp, :ended_by, :_DEBUG_ended_by, :_DEBUG_end, :end_timestamp, :_DEBUG_delta)"""
            async with db.execute(query, session) as cursor:
                lastrow = cursor.lastrowid
            await db.commit()
        return lastrow
    
    async def delete_session(self, guild_id):
        lastrow = 0
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"""SELECT count(*) FROM session WHERE server = {guild_id}"""
            async with db.execute(query) as cursor:
                res = await cursor.fetchall()
                if dict(res[0])['count(*)'] != 1:
                    return None
            query = f"""DELETE FROM session WHERE server = {guild_id}"""
            async with db.execute(query) as cursor:
                lastrow = cursor.lastrowid
            await db.commit()
        return lastrow
    
    
    async def store_historical_session(self, guild_id, session):
        lastrow = 0
        async with aiosqlite.connect('data/urnby.db') as db:
            query = f"""INSERT INTO session_history(server,      session,  created_by,  _DEBUG_started_by,  _DEBUG_start,  start_timestamp,  ended_by,  _DEBUG_ended_by,  _DEBUG_end,  end_timestamp,  _DEBUG_delta)
                                             VALUES({guild_id}, :session, :created_by, :_DEBUG_started_by, :_DEBUG_start, :start_timestamp, :ended_by, :_DEBUG_ended_by, :_DEBUG_end, :end_timestamp, :_DEBUG_delta)"""
            async with db.execute(query, session) as cursor:
                lastrow = cursor.lastrowid
            await db.commit()
        return lastrow
    
    async def get_last_rows_historical_session(self, guild_id, count):
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"""SELECT rowid, * FROM session_history WHERE server = {guild_id} ORDER BY rowid DESC LIMIT {count}"""
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
        return res
    
    async def get_all_actives(self, guild_id) -> list:
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"SELECT rowid, * FROM active WHERE server == {guild_id}"
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
        return res
    
    # Returns None on user not in active
    async def remove_active_record(self, guild_id, record):
        lastrow = 0
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"""SELECT count(*) FROM active WHERE server = {guild_id} AND user = {record['user']}"""
            async with db.execute(query) as cursor:
                res = await cursor.fetchall()
                if dict(res[0])['count(*)'] == 0:
                    return None
            query = f"""DELETE FROM active WHERE server = {guild_id} AND user = {record['user']}"""
            async with db.execute(query) as cursor:
                lastrow = cursor.lastrowid
            await db.commit()
        return lastrow
    
    # Returns None on user was already in active
    async def store_active_record(self, guild_id, record):
        guild_actives = await self.get_all_actives(str(guild_id))
        for item in guild_actives:
            if item['user'] == record['user']:
                return None
                
        lastrow = 0
        async with aiosqlite.connect('data/urnby.db') as db:
            query = f"""INSERT INTO active(server,      user,  character,  session,  in_timestamp,  out_timestamp,  _DEBUG_user_name,  _DEBUG_in,  _DEBUG_out,  _DEBUG_delta)
                                    VALUES({guild_id}, :user, :character, :session, :in_timestamp, :out_timestamp, :_DEBUG_user_name, :_DEBUG_in, :_DEBUG_out, :_DEBUG_delta)"""
            async with db.execute(query, record) as cursor:
                lastrow = cursor.lastrowid
            await db.commit()
        return lastrow
    
    async def get_historical(self, guild_id):
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"SELECT rowid, * FROM historical WHERE server == {guild_id}"
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
        return res
        
    async def get_last_rows_historical(self, guild_id, count):
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"""SELECT rowid, * FROM historical WHERE server = {guild_id} ORDER BY rowid DESC LIMIT {count}"""
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
        return res
    
    async def get_historical_user(self, guild_id, user_id):
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"SELECT rowid, * FROM historical WHERE server == {guild_id} AND user == {user_id}"
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
        return res
    
    async def store_new_historical(self, guild_id, record):
        lastrow = 0
        async with aiosqlite.connect('data/urnby.db') as db:
            query = f"""INSERT INTO historical(server,      user,  character,  session,  in_timestamp,  out_timestamp,  _DEBUG_user_name,  _DEBUG_in,  _DEBUG_out,  _DEBUG_delta)
                                        VALUES({guild_id}, :user, :character, :session, :in_timestamp, :out_timestamp, :_DEBUG_user_name, :_DEBUG_in, :_DEBUG_out, :_DEBUG_delta)"""
            async with db.execute(query, record) as cursor:
                lastrow = cursor.lastrowid
            await db.commit()
        return lastrow
    
    async def get_historical_record(self, guild_id, rowid):
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"SELECT rowid, * FROM historical WHERE server == {guild_id} AND rowid == {rowid}"
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
            await db.commit()
        return res
        
    async def delete_historical_record(self, guild_id, rowid):
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            query = f"DELETE FROM historical WHERE server == {guild_id} AND rowid == {rowid}"
            async with db.execute(query) as cursor:
                res = await cursor.fetchall()
            await db.commit()
        return res
        
    # Returns list of int of unique users stored in historical for a given guild
    async def get_unique_users(self, guild_id) -> list[int]:
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"SELECT DISTINCT user FROM historical WHERE server == {guild_id}"
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [row['user'] for row in rows]
        return res
    
    async def get_user_seconds(self, guild_id, user, guild_historical=None):
        
        if not guild_historical:
            guild_historical = await self.get_historical(guild_id)
        
        if not guild_historical:
            return None
            
        found = [_ for _ in guild_historical if _['user'] == int(user)]
        
        if len(found) == 0:
            return 0
        
        in_tot = 0
        out_tot = 0
        for item in found:
            in_tot += item['in_timestamp']
            out_tot += item['out_timestamp']
        return out_tot - in_tot
    
    async def get_user_hours(self, guild_id, user, guild_historical=None) -> float:
        secs = await self.get_user_seconds(guild_id, user, guild_historical)
        return get_hours_from_secs(secs)
    
    # Wraps get_users_hours but only needs one grab from historical json
    async def get_users_hours(self, guild_id, users) -> list[dict]:
        guild_historical = await self.get_historical(guild_id)
        res = []
        if not guild_historical:
            return res
        
        for user in users:
        
            tot = await self.get_user_hours(guild_id, user, guild_historical)
              
            res.append({'user': user, 'total':tot})
        return res
    
    async def store_command(self, guild_id, command):
        lastrow = 0
        async with aiosqlite.connect('data/urnby.db') as db:
            query = f"""INSERT INTO commands(server,      command_name,  options,  datetime,  user,  user_name,  channel_name)
                                      VALUES({guild_id}, :command_name, :options, :datetime, :user, :user_name, :channel_name)"""
            async with db.execute(query, command) as cursor:
                lastrow = cursor.lastrowid
            await db.commit()
        return lastrow
        
    async def get_commands_history(self, guild_id):
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"""SELECT rowid, * FROM commands WHERE server = {guild_id}"""
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
        return res
    
    async def get_last_rows_commands_history(self, guild_id, count) -> list[dict]:
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            query = f"""SELECT rowid, * FROM commands WHERE server = {guild_id} ORDER BY rowid DESC LIMIT {count}"""
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
        return res
    
    async def get_user_commands_history(self, guild_id, user_id, start_at=None, count=10) -> list[dict]:
        res = []
        async with aiosqlite.connect('data/urnby.db') as db:
            db.row_factory = aiosqlite.Row
            if start_at:
                count += start_at
            query = f"""SELECT rowid, * FROM commands WHERE server = {guild_id} and user = {user_id} ORDER BY rowid DESC LIMIT {count}"""
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                res = [dict(row) for row in rows]
            if start_at:
                res = res[start_at:]
        return res
    

def get_hours_from_secs(timestamp_delta: int) -> float:
    return round(timestamp_delta/SECS_IN_HOUR, 2)

def setup(bot):
    cog = Clocks(bot)
    
    bot.add_cog(Clocks(bot))