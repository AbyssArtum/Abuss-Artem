import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from typing import Dict, Optional

class ModerationBase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "data/moderation.json"
        self.load_data()
        
    def load_data(self):
        if not os.path.exists(self.data_file):
            self.data = {
                "log_channels": {
                    "punishments": None,
                    "reports": None
                },
                "warns": {}
            }
            return
            
        with open(self.data_file, "r", encoding="utf-8") as f:
            self.data = json.load(f)
            
    def save_data(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    @app_commands.command(name="лог_канал", description="Установить канал для логов модерации")
    @app_commands.describe(
        функция="Тип логов",
        канал="Канал для логов"
    )
    @app_commands.choices(функция=[
        app_commands.Choice(name="наказания", value="punishments"),
        app_commands.Choice(name="жалобы", value="reports")
    ])
    @commands.has_permissions(administrator=True)
    async def set_log_channel(
        self,
        interaction: discord.Interaction,
        функция: app_commands.Choice[str],
        канал: discord.TextChannel
    ):
        self.data["log_channels"][функция.value] = канал.id
        self.save_data()
        
        embed = discord.Embed(
            title="✅ Канал для логов установлен",
            description=f"Канал {канал.mention} теперь получает логи типа: {функция.name}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationBase(bot))