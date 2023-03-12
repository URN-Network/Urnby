# Builtin
import datetime

# External
import discord
from discord.ext import commands
from pytz import timezone
tz = timezone('EST')

# Internal
import data.databaseapi as db
from checks.IsAdmin import is_admin, NotAdmin
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember
from checks.IsInDev import is_in_dev, InDevelopment


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

    @commands.slash_command(name='getreps', description='Display current list of replacements')
    @is_member()
    async def _getreps(self, ctx, public: discord.Option(bool, name='public', default=False)):
        if ctx.guild is None:
            await ctx.send_response(content='This command can not be used in Direct Messages')
            return

        reps = await db.get_replacement_queue(ctx.guild.id)
        content = '\nCurrent replacements: '
        for rep in reps:
            content += f'<@{rep["user"]}> --> '
        content += f'<END>'
        await ctx.send_response(content=content, ephemeral=not public, allowed_mentions=discord.AllowedMentions(users=False))


    @commands.slash_command(name='rep', description='Add yourself to the replacement list (FIFO)')
    @is_member()
    @is_command_channel()
    async def _rep(self, ctx, userid: discord.Option(str, name="userid", required=False)):
        now = datetime.datetime.now(tz)

        if userid:
            userid = int(userid)
            try:
                user = await ctx.guild.fetch_member(userid)
            except discord.errors.NotFound:
                await ctx.send_response(content=f'Invalid User ID')
                return
            else:
                display_name = user.display_name
        else:
            display_name = ctx.author.display_name
            
        rep = {
            'user': userid if userid else ctx.author.id,
            'name': display_name,
            'in_timestamp': int(now.timestamp())
        }

        added = await db.add_replacement(ctx.guild.id, rep)
        if added is not None:
            await ctx.send_response(content=f'{display_name} Successfully added to replacement queue')
        else:
            await ctx.send_response(content=f'User is already in queue')
    
    @commands.slash_command(name='unrep', description='Remove yourself from the replacement list')
    @is_member()
    @is_command_channel()
    async def _unrep(self, ctx, userid: discord.Option(str, name="userid", required=False)):

        if userid:
            userid = int(userid)
            try:
                user = await ctx.guild.fetch_member(userid)
            except discord.errors.NotFound:
                await ctx.send_response(content=f'Invalid User ID')
                return
            else:
                display_name = user.display_name
        else:
            display_name = ctx.author.display_name

        removed = await db.remove_replacement(ctx.guild.id, userid if userid else ctx.author.id)
        if removed is not None:
            await ctx.send_response(content=f'{display_name} Successfully removed from replacement queue')
        else:
            await ctx.send_response(content=f'User is not in queue')

    @commands.slash_command(name='admin_rep')
    @is_admin()
    async def _adminrep(self, ctx,
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
        
    @commands.slash_command(name='admin_unrep')
    @is_admin()
    async def _adminunrep(self, ctx,
                _userid: discord.Option(str, name="userid", required=True)):
        await db.remove_replacement(ctx.guild.id, _userid)
        await ctx.send_response(content=f'Removed.')

    @commands.slash_command(name='admin_clearreps')
    @is_admin()
    async def _adminclearreps(self, ctx):
        await db.clear_replacement_queue(ctx.guild.id)
        await ctx.send_response(content=f'Queue cleared.')


def setup(bot):
    bot.add_cog(CampQueue(bot))