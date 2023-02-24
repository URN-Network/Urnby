import discord
from discord.ext import commands
import datetime
from pytz import timezone
tz = timezone('EST')


class Peeper(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.peeped_last = None
        print('Initilization on peeper complete')

    @commands.Cog.listener()
    async def on_connect(self):
        print(f'peeper connected to discord')
        
    @commands.slash_command(name='ipeeped')
    async def _ipeeped(self, ctx):
        peep_timestamp = int(datetime.datetime.now(tz).timestamp())
        self.peeped_last = {'user': ctx.author.id, 'time': peep_timestamp}
        await ctx.send_response(content=f'Got it, you\'re the last peeper at <t:{peep_timestamp}:f> local time', ephemeral=True)
        return
        
    @commands.slash_command(name='whopeeped')
    async def _whopeeped(self, ctx):
        if self.peeped_last == None:
            await ctx.send_response(content=f'Sorry I cant remember who peeped last', ephemeral=True)
        else:
            now = datetime.datetime.now(tz)
            peeptime = datetime.datetime.fromtimestamp(self.peeped_last["time"], tz=tz)
            mins = await time_delta_to_minutes(now-peeptime)
            
            await ctx.send_response(content=f'<@{self.peeped_last["user"]}> last peeped at <t:{self.peeped_last["time"]}:f> local, that was {mins:.2f} mins ago', ephemeral=True, allowed_mentions=discord.AllowedMentions(users=False))
        return

async def time_delta_to_minutes(delta:datetime.timedelta) -> float:
    secs = delta.total_seconds()
    sec_to_min = 60
    mins = secs/sec_to_min
    return mins

def setup(bot):
    bot.add_cog(Peeper(bot))