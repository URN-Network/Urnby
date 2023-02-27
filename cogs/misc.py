import datetime
import discord
from discord.ext import commands
from pytz import timezone
tz = timezone('EST')

from checks.IsAdmin import is_admin, NotAdmin
from checks.IsMember import is_member, NotMember

class Misc(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        print('Initilization on misc complete')

    @commands.Cog.listener()
    async def on_connect(self):
        pass
    
    async def cog_before_invoke(self, ctx):
        now = datetime.datetime.now(tz)
        now = now.replace(microsecond = 0)
        guild_id = None
        if not ctx.guild:
            guild_id = 'DM'
        else:
            guild_id = ctx.guild.id
        print(f'{now.isoformat()} [{guild_id}] - Command {ctx.command.qualified_name} by {ctx.author.name} - {ctx.author.id} - {ctx.selected_options[0]["value"]}', flush=True)
        #command = {'command_name': ctx.command.qualified_name, 'options': str(ctx.selected_options), 'datetime': now.isoformat(), 'user': ctx.author.id, 'user_name': ctx.author.name, 'channel_name': ctx.channel.name}
        #await self.store_command(guild_id, command)
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
        
    @commands.slash_command(name='echo')
    @is_member()
    async def _echo(self, ctx, content: discord.Option(name='content', input_type=str, required=True)):
        await ctx.channel.send(content=content)
        await ctx.send_response(content="Your word is my command", ephemeral=True)


def setup(bot):
    bot.add_cog(Misc(bot))

