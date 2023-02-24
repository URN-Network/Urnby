from discord.ext import commands

class InDevelopment(commands.CheckFailure):
    pass

def is_in_dev():
    async def predicate(ctx):
        member = ctx.guild.get_member(ctx.author.id)
        roles = member.roles
        for role in roles:
            if role.permissions.administrator:
                return True
        raise InDevelopment()
    return commands.check(predicate)