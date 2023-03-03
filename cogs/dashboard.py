import discord
from discord.ext import commands, tasks
import datetime
from pytz import timezone
tz = timezone('EST')
utc_tz = timezone('UTC')
import json

import data.databaseapi as db
from static.common import get_hours_from_secs, SECS_IN_MINUTE


class Dashboard(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.printer.start()
        self.lastmsg = {}
        print('Initilization on dashboard complete')
        
    @commands.Cog.listener()
    async def cog_unload(ctx):
        for key, value in self.lastmsg:
            msg = await self.bot.fetch_guild(key).fetch_channel(value['channel']).fetch_message(value['msgid'])
            jump = msg.juml_url
            await msg.delete()
            print(f"Deleted dashboard message {jump}")
        
    @commands.slash_command(name="timeleft")
    async def _timeleft(self, ctx):
        now = datetime.datetime.now(utc_tz)
        delta = self.printer.next_iteration - now
        await ctx.send_response(content=f'{delta}')
    
    @commands.slash_command(name="dashboardhalt")
    @commands.is_owner()
    async def _halt(self, ctx):
        print("Halting Dashboard cycle")
        await ctx.send_response("Stopping Dashboard Cycle")
        self.printer.stop()
    
    @tasks.loop(minutes = 1)
    async def printer(self):
        for guild in self.bot.guilds:
           
            config = self.get_config(guild.id)
            if not config or not config.get('dashboard_channel'):
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
                    continue
                item['display_name'] = member.display_name
            
            actives = await db.get_all_actives(guild.id)
            
            for item in actives:
                try:
                    member = await guild.fetch_member(int(item['user']))
                except discord.errors.NotFound:
                    item['display_name'] = 'placeholder'
                    item['delta'] = get_hours_from_secs(now.timestamp() - item['in_timestamp'])
                    continue
                item['display_name'] = guild.get_member(item['user']).display_name
                item['delta'] = get_hours_from_secs(now.timestamp() - item['in_timestamp'])
            
                
            session = await db.get_session(guild.id)
            if not session:
                session = {'session': "None"}
                timestr = ''
            else:
                timestr = datetime.datetime.fromtimestamp(session['start_timestamp'], tz).strftime("%b%d %I:%M%p")
            
            tod_dict = db.get_tod(guild.id, mob_name="Drusella Sathir")
            tod_datetime = datetime.datetime.fromtimestamp(tod_dict['tod_timestamp'], tz) + datetime.timedelta(days=1)
            mins_till_ds = int((tod_datetime - now).total_seconds()/SECS_IN_MINUTE)}
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
            contentlines.append(f" {'Active Users':35}Hours at camp|") 
            contentlines.append(f"{'-'*49}|")
            for item in actives:
                contentlines.append(f" {item['display_name'][:29]:30} {item['delta']:17.2f}|")
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
                
            lastmsg = await guild.get_channel(config['dashboard_channel']).send(content=content, delete_after=59.5, silent=True)
            self.lastmsg[str(ctx.guild.id)] = {'channel': ctx.channel_id, 'msgid':lastmsg.id}
    
            
    def get_config(self, guild_id):
        return json.load(open('data/config.json', 'r', encoding='utf-8')).get(str(guild_id))
        
        
def setup(bot):
    bot.add_cog(Dashboard(bot))
