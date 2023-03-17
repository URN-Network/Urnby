from discord.ext import commands
import discord 
import json

class NotMember(commands.CheckFailure):
    pass

@staticmethod
def get_config():
    return json.load(open('data/config.json', 'r', encoding='utf-8'))

def is_member():
    async def predicate(ctx):
        if ctx.guild is None:
            return False
        allowed_member_roles = get_config()[str(ctx.guild.id)]['member_roles']
        
        author_member = await ctx.guild.fetch_member(ctx.author.id)
        author_roles = author_member.roles
        for role in author_roles:
            if role.id in allowed_member_roles:
                return True
            
        raise NotMember
    return commands.check(predicate)
   