from discord.ext import commands
import json

class NotCommandChannel(commands.CheckFailure):
    pass

@staticmethod
def get_config():
    return json.load(open('data/config.json', 'r', encoding='utf-8'))

def is_command_channel():
    async def predicate(ctx):
        if ctx.guild is None:
            return NotCommandChannel()
        config = get_config()
        if ctx.channel_id in config[str(ctx.guild.id)]['command_channels']:
            return True
        raise NotCommandChannel()
    return commands.check(predicate)
   