import discord
from discord.ext import commands, tasks
import datetime
from pytz import timezone
tz = timezone('EST')
utc_tz = timezone('UTC')
import json

import data.databaseapi as db
from static.common import get_hours_from_secs


class Dashboard(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.printer.start()
        
        print('Initilization on dashboard complete')
    
    @commands.slash_command(name="timeleft")
    async def _timeleft(self, ctx):
        now = datetime.datetime.now(utc_tz)
        delta = self.printer.next_iteration - now
        await ctx.send_response(content=f'{delta}')
    
    @tasks.loop(minutes = 1)
    async def printer(self):
        for guild in self.bot.guilds:
           
            config = self.get_config(guild.id)
            if not config or not config.get('dashboard_channel'):
                continue
            print(f'config get on {guild}')
            users = await db.get_unique_users(guild.id)
            
            res = await db.get_users_hours(guild.id, users)
            
            sorted_res = list(sorted(res, key= lambda user: user['total'], reverse=True))[:10]
            for item in sorted_res:
                member = await guild.get_member(int(item['user']))
                if not member:
                    item['display_name'] = 'placeholder'
                    continue
                item['display_name'] = member.display_name
            
            for idx in range(len(sorted_res), 10):
                sorted_res.append({'display_name': '', 'total': 0})
            
            actives = await db.get_all_actives(guild.id)
            now = datetime.datetime.now()
            for item in actives:
                member = await guild.get_member(int(item['user']))
                if not member:
                    item['display_name'] = 'placeholder'
                    item['delta'] = get_hours_from_secs(now.timestamp() - item['in_timestamp'])
                    continue
                item['display_name'] = guild.get_member(item['user']).display_name
                item['delta'] = get_hours_from_secs(now.timestamp() - item['in_timestamp'])
            for idx in range(len(actives), 5):
                actives.append({'display_name': '', 'delta': 0})
                
            session = await db.get_session(guild.id)
            if not session:
                session = {'session': "None"}
                timestr = ''
            else:
                timestr = datetime.datetime.fromtimestamp(session['start_timestamp'], tz).strftime("%b%d %I:%M%p")
            content= f"""
```    
 Active Session                                  | Top 10 Hours
---------------------------------------------------------------------------------------------------
 {session['session'][:27]:27} @ {timestr:13} EST | {sorted_res[0]['display_name'][:43]:43} {sorted_res[0]['total']:.2f}
-------------------------------------------------| {sorted_res[1]['display_name'][:43]:43} {sorted_res[1]['total']:.2f}
 Active Users                                    | {sorted_res[2]['display_name'][:43]:43} {sorted_res[2]['total']:.2f}
-------------------------------------------------| {sorted_res[3]['display_name'][:43]:43} {sorted_res[3]['total']:.2f}
 {actives[0]['display_name'][:29]:30} {actives[0]['delta']:16.2f} | {sorted_res[4]['display_name'][:43]:43} {sorted_res[4]['total']:.2f}
 {actives[1]['display_name'][:29]:30} {actives[1]['delta']:16.2f} | {sorted_res[5]['display_name'][:43]:43} {sorted_res[5]['total']:.2f}
 {actives[2]['display_name'][:29]:30} {actives[2]['delta']:16.2f} | {sorted_res[6]['display_name'][:43]:43} {sorted_res[6]['total']:.2f}
 {actives[3]['display_name'][:29]:30} {actives[3]['delta']:16.2f} | {sorted_res[7]['display_name'][:43]:43} {sorted_res[7]['total']:.2f}
 {actives[4]['display_name'][:29]:30} {actives[4]['delta']:16.2f} | {sorted_res[8]['display_name'][:43]:43} {sorted_res[8]['total']:.2f}
                                                 | {sorted_res[9]['display_name'][:43]:43} {sorted_res[9]['total']:.2f}
```
"""
            await guild.get_channel(config['dashboard_channel']).send(content=content)
    
            
    def get_config(self, guild_id):
        print(guild_id)
        return json.load(open('data/config.json', 'r', encoding='utf-8')).get(str(guild_id))
        
        
def setup(bot):
    bot.add_cog(Dashboard(bot))
