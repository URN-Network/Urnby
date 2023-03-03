import datetime
import json
import discord
from discord.ext import commands
from pytz import timezone
tz = timezone('EST')


from checks.IsAdmin import is_admin, NotAdmin
from checks.IsCommandChannel import is_command_channel, NotCommandChannel
from checks.IsMemberVisible import is_member_visible, NotMemberVisible
from checks.IsMember import is_member, NotMember
from checks.IsInDev import is_in_dev, InDevelopment

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
    
    @commands.slash_command(name='configadd')
    @is_admin()
    async def _add_config(self, ctx, 
                          _key: discord.Option(name="key", choices=["member_roles", "admin_roles", "command_channels", "max_active"], required=True),
                          _value: discord.Option(int, name="value", required=True)):
        guild_config = get_guild_config(str(ctx.guild.id))
        if _key == "max_active":
            guild_config[_key] = _value
        else:
            guild_config[_key].append(_value)
        save_guild_config(str(ctx.guild.id), guild_config)
        await ctx.send_response(content=f"Config item set - {_key} = {guild_config[_key]}")
            
    @commands.slash_command(name='configaddbonushours')
    @is_admin()
    async def _add_config_bonus_hours(self, ctx, 
                          _start: discord.Option(str, name="start", required=True),
                          _end: discord.Option(str, name="end", required=True),
                          _pct: discord.Option(int, name="pct", required=True)):
        guild_config = get_guild_config(str(ctx.guild.id))
        if not guild_config.get('bonus_hours'):
            guild_config['bonus_hours'] = []
        try:
            _start = '0'+_start if len(_start) == 4 else _start
            _end = '0'+end if len(_end) == 4 else _end
            datetime.time.fromisoformat(_start)
            datetime.time.fromisoformat(_end)
            int(_pct)
        except ValueError as err:
            await ctx.send_response(content=f"Invalid input for value: {err}")
            return
        guild_config['bonus_hours'].append({"start":_start, "end":_end, "pct": _pct})
        save_guild_config(str(ctx.guild.id), guild_config)
        await ctx.send_response(content=f"Config item set - bonus_hours = {guild_config['bonus_hours']}")
    
    @commands.slash_command(name='configclearitem')
    @is_admin()
    async def _config_clear_item(self, ctx, _key: discord.Option(name="key", choices=["member_roles", "admin_roles", "command_channels", "bonus_hours"], required=True)):
        guild_config = get_guild_config(str(ctx.guild.id))
        guild_config[_key] = []
        save_guild_config(str(ctx.guild.id), guild_config)
        await ctx.send_response(content=f"Config item cleared - {_key} = {guild_config[_key]}")
        
    @commands.slash_command(name='echo')
    @is_admin()
    async def _echo(self, ctx, content: discord.Option(str, name='content', required=True)):
        await ctx.channel.send(content=content)
        await ctx.send_response(content="Your word is my command", ephemeral=True)

def get_guild_config(guild_id):
    config = json.load(open('data/config.json', 'r', encoding='utf-8'))
    guild_config = config.get(str(guild_id))
    if not guild_config:
        guild_config = {}
    return guild_config

def save_guild_config(guild_id, new_guild_config):
    config = get_guild_config(guild_id)
    config[guild_id] = new_guild_config
    json.dump(config, open('data/config.json', 'w', encoding='utf-8'), indent=1)
    return True
    
def setup(bot):
    bot.add_cog(Misc(bot))

