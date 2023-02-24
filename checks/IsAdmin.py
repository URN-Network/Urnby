from discord.ext import commands

class NotAdmin(commands.CheckFailure):
    pass

def is_admin():
    async def predicate(ctx):
        member = ctx.guild.get_member(ctx.author.id)
        roles = member.roles
        for role in roles:
            if role.permissions.administrator:
                return True
        raise NotAdmin()
    return commands.check(predicate)