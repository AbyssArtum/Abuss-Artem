import discord
from discord import app_commands
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Текстовая команда !ping
    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong!")

    # Слэш-команда /ping
    @app_commands.command(name="ping", description="Отвечает Pong!")
    async def slash_ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")

async def setup(bot):
    await bot.add_cog(General(bot))
