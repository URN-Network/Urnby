# Builtin
import datetime
from enum import Enum

# External
import discord
from discord.ext import commands

# Internal
import data.databaseapi as db
import static.common as com
from checks.IsAdmin import is_admin, NotAdmin
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember
from checks.IsInDev import is_in_dev, InDevelopment

class MemberQueryResult(Enum):
    FOUND = 1
    ID_NOT_FOUND = 2
    NOT_UNIQUE = 3
    UNKNOWN_PARAMETER = 4
    QUERY_FAILED = 5

class CampQueue(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        print('Initilization on campqueue complete')

    @commands.Cog.listener()
    async def on_connect(self):
        print(f'campqueue connected to discord')

    @commands.Cog.listener()
    async def on_ready(self):
        missing_tables = await db.check_tables(['reps'])
        if missing_tables:
            print(f"Warning, missing the following tables in db: {missing_tables}")
    
    async def cog_before_invoke(self, ctx):
        guild_id = 0
        if ctx.guild:
            guild_id = ctx.guild.id
        now_iso = com.get_current_iso()
        print(f'{now_iso} [{guild_id}] - Command {ctx.command.qualified_name} by {ctx.author.name} - {ctx.author.id} - {ctx.selected_options}', flush=True)
        command = {'command_name': ctx.command.qualified_name, 'options': str(ctx.selected_options), 'datetime': now_iso, 'user': ctx.author.id, 'user_name': ctx.author.name, 'channel_name': ctx.channel.name}
        await db.store_command(guild_id, command)
        return

    # ========================
    #  Abstract away direct data access
    # ========================
    async def remove_rep(self, ctx, user_id):
        return await db.remove_replacement(ctx.guild.id, user_id)

    async def remove_reps(self, ctx, user_ids):
        # TODO: Could do this in 1 sql command
        # DELETE FROM reps WHERE user IN ({user_ids})
        for user in user_ids:
            self.remove_rep(ctx, user)

    async def add_rep(self, ctx, rep):
        return await db.add_replacement(ctx.guild.id, rep)

    async def clear_reps(self, ctx):
        return await db.clear_replacement_queue(ctx.guild.id)

    async def get_older_reps_than_user(self, ctx, user_id) -> list:
        reps = await db.get_replacements_before_user(ctx.guild.id, user_id)
        return reps

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

    @commands.slash_command(name='getreps', description='Display current list of replacements')
    @is_member()
    async def _getreps(self, ctx, public: discord.Option(bool, name='public', default=False)):
        if ctx.guild is None:
            await ctx.send_response(content='This command can not be used in Direct Messages')
            return

        reps = await db.get_replacement_queue(ctx.guild.id)
        
        content = '\nCurrent replacements: '
        for rep in reps:
            content += f'\n<@{rep["user"]}> @ {com.datetime_from_timestamp(rep["in_timestamp"]).isoformat()}'
        
        if not reps:
            content = 'There are no replacements available'
        await ctx.send_response(content=content, ephemeral=not public, allowed_mentions=discord.AllowedMentions(users=False))

    @commands.slash_command(name='repadd', description='Add yourself to the replacement list (FIFO)')
    @is_member()
    @is_command_channel()
    async def _repadd(self, ctx, userid: discord.Option(str, name="userid", default = None, required=False)):
        if userid is None:
            userid = ctx.author.id
        userid, display_name = await get_userid_and_name(ctx, userid)
        if not userid:
            return
        rep = {
            'user': userid,
            'name': display_name,
            'in_timestamp': com.get_current_timestamp(),
        }

        if await db.is_user_active(ctx.guild.id, userid):
            await ctx.send_response(content=f'{display_name} is already clocked in')
            return
        
        added = await self.add_rep(ctx, rep)
        if not added:
            await ctx.send_response(content=f'{display_name} is already in queue')
            return
        await ctx.send_response(content=f'{display_name} Successfully added to replacement queue')
        
    
    @commands.slash_command(name='repremove', description='Remove yourself from the replacement list')
    @is_member()
    @is_command_channel()
    async def _repremove(self, ctx, userid: discord.Option(str, name="userid", default = None, required=False)):
        if userid is None:
            userid = ctx.author.id
        userid, display_name = await get_userid_and_name(ctx, userid)
        if not userid:
            return
        removed = await self.remove_rep(ctx, userid)
        if removed is None:
            await ctx.send_response(content=f'User is not in queue')
            return
        await ctx.send_response(content=f'{display_name} Successfully removed from replacement queue')    
    
    '''
    @commands.slash_command(name='admin_repremove')
    @is_admin()
    @is_command_channel()
    async def _adminrepremove(self, ctx,
                _userid: discord.Option(str, name="userid", required=True)):
        userid, display_name = await get_userid_and_name(ctx, userid)
        if not userid:
            return
        removed = await self.remove_rep(ctx, userid)
        if removed is None:
            await ctx.send_response(content=f'User is not in queue')
            return
        await ctx.send_response(content=f'{display_name} Successfully removed from replacement queue')   
    
    @commands.user_command(name="Admin - Dequeue")
    @is_admin()
    @is_command_channel()
    async def _adminuserrepremove(self, ctx, member: discord.Member):
        userid, display_name = await get_userid_and_name(ctx, member.id)
        if not userid:
            return
        removed = await self.remove_rep(ctx, userid)
        if removed is None:
            await ctx.send_response(content=f'User is not in queue')
            return
        await ctx.send_response(content=f'{display_name} Successfully removed from replacement queue')   
    '''
    
    @commands.slash_command(name='admin_repclear')
    @is_admin()
    @is_command_channel()
    async def _adminrepclear(self, ctx):
        res = await self.clear_reps()
        if not res:
            await ctx.send_response(content=f'Problem occured while clearing camp queue.')
            return
        await ctx.send_response(content=f'Camp Queue cleared.')
'''
async def get_userid_and_name(ctx, userid):
    if not userid:
        userid = ctx.author.id
        display_name = ctx.author.display_name
    else:
        try:
            userid = int(userid)
            user = await ctx.guild.fetch_member(userid)
            display_name = user.display_name
        except (discord.errors.NotFound, ValueError):
            await ctx.send_response(content=f'Invalid User ID')
            return None, None
            
    return userid, display_name
'''
async def get_userid_and_name(ctx, param) -> int:
    # Try userid for int interpretation
    ret = {'result': None, 'type': MemberQueryResult.QUERY_FAILED}
    try:
        int(param)
        res = await ctx.guild.fetch_member(int(param))
        ret = {'result': res, 'type': MemberQueryResult.FOUND}
    except (ValueError, TypeError) as err:
        # Failed int parsing
        pass 
    except discord.errors.NotFound:
        ret = {'result': None, 'type': MemberQueryResult.ID_NOT_FOUND}
    if not ret['result']:
        # try querying string for member
        try:
            res = await ctx.guild.query_members(query=param, limit=2)
            if len(res) == 0:
                ret = {'result': None, 'type': MemberQueryResult.ID_NOT_FOUND}
            elif len(res) == 1:
                ret = {'result': res[0], 'type': MemberQueryResult.FOUND}
            else:
                ret = {'result': None, 'type': MemberQueryResult.NOT_UNIQUE}
        except Exception as err:
            pass
    if ret['result'] is None:
        await ctx.send_response(content=f"userid '{param}' couldnt be found, returned {ret['type']}", ephemeral=True)
        return None, None
    return ret['result'].id, ret['result'].display_name

def setup(bot):
    bot.add_cog(CampQueue(bot))