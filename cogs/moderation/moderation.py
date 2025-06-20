import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class ModerationBase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "data/moderation.json"
        self.load_data()
        
    def load_data(self):
        if not os.path.exists(self.data_file):
            self.warns = {}
            self.log_channel = None
            return
            
        with open(self.data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.warns = data.get("warns", {})
            self.log_channel = data.get("log_channel")
            
    def save_data(self):
        data = {
            "warns": self.warns,
            "log_channel": self.log_channel
        }
        
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


    @app_commands.command(name="установить_лог_канал", description="Установить канал для логов модерации")
    @app_commands.describe(канал="Канал для логов модерации")
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, канал: discord.TextChannel):
        self.log_channel = канал.id
        self.save_data()
        await interaction.response.send_message(
            f"✅ Канал для логов установлен: {канал.mention}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(ModerationBase(bot))