from discord.ext import commands
import discord 
import json

class NotMemberVisible(commands.CheckFailure):
    pass

@staticmethod
def get_config():
    return json.load(open('data/config.json', 'r', encoding='utf-8'))

def is_member_visible():
    async def predicate(ctx):
        # Can not be DMs
        if ctx.guild is None:
            raise NotMemberVisible
        
        member_roles = get_config()[str(ctx.guild.id)]['member_roles']
        for role in member_roles:
            _role = ctx.guild.get_role(role)
            channel_perms = ctx.channel.permissions_for(_role)
            
            req_perms = discord.Permissions.none()
            req_perms.update(read_messages = True) 
            req_perms.update(read_message_history = True)
            if not channel_perms.is_superset(req_perms):
                raise NotMemberVisible
            
        return True
    return commands.check(predicate)
   