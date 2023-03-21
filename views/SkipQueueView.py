import discord

class SkipQueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=10)
        self.result = None
        
    async def on_timeout(self):
        already_disabled = False
        for child in self.children:
            if child.disabled:
                already_disabled = True
            child.disabled = True
        if not already_disabled:
            await self.message.edit(content="You took too long to respond, Clockin command reset.", view=self)
        else:
            return
        
    @discord.ui.button(label='Yes', style=discord.ButtonStyle.primary)
    async def accept_button_callback(self, button, interaction):
        #TODO check and ensure these are the same and other users cant click the button
        print(interaction.user.id)
        print(self.message.interaction.user.id) 
        if interaction.user.id == self.message.interaction.user.id:
            for child in self.children:
                child.disabled = True
            self.result = True
            await interaction.response.edit_message(content="Confirmed, skipping queue members", view=self)
            self.stop()
            return interaction.message.id
        else:
            return
            
    @discord.ui.button(label='No', style=discord.ButtonStyle.red)
    async def abort_button_callback(self, button, interaction):
        if interaction.user.id == self.message.interaction.user.id:
            for child in self.children:
                child.disabled = True
            self.result = False
            await interaction.response.edit_message(content="Clockin Canceled", view=self)
            self.stop()
        else:
            return