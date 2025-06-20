import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.user_data import get_user_data, save_user_data

class LevelingAdminCommands(commands.Cog):  # Изменили название класса
    def __init__(self, bot):
        self.bot = bot
        self.VOICE_XP_PER_MIN = 20
        
    @app_commands.command(name="опыт", description="Управление опытом участников")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        действие="Начислить или снять опыт",
        тип="Тип опыта: общий или голосовой",
        количество="Количество (число для общего, минуты для голосового)",
        участник="Участник, которому начисляем/снимаем"
    )
    @app_commands.choices(
        действие=[
            app_commands.Choice(name="начислить", value="add"),
            app_commands.Choice(name="снять", value="remove")
        ],
        тип=[
            app_commands.Choice(name="общий", value="general"),
            app_commands.Choice(name="голосовой", value="voice")
        ]
    )
    async def manage_xp(self, interaction: discord.Interaction, действие: app_commands.Choice[str],
                       тип: app_commands.Choice[str], количество: int, участник: discord.Member):
        try:
            if количество <= 0:
                return await interaction.response.send_message(
                    "❌ Количество должно быть положительным числом!",
                    ephemeral=True
                )
            
            await interaction.response.defer(ephemeral=True)
            user_data = get_user_data(участник.id)
            
            # Инициализация структуры
            if "leveling" not in user_data:
                user_data["leveling"] = {
                    "text_xp": 0,
                    "voice_xp": 0,
                    "total_xp": 0,
                    "level": 1,
                    "voice_time": 0  # Добавляем отсутствующее поле
                }
            
            # Добавляем voice_time, если его нет
            if "voice_time" not in user_data["leveling"]:
                user_data["leveling"]["voice_time"] = 0
            
            if тип.value == "voice":
                old_time = user_data["leveling"]["voice_time"]
                change = количество if действие.value == "add" else -количество
                new_time = max(0, old_time + change)
                
                if действие.value == "remove" and количество > old_time:
                    return await interaction.followup.send(
                        f"❌ У участника только {old_time} минут, нельзя снять {количество}!",
                        ephemeral=True
                    )
                
                user_data["leveling"]["voice_time"] = new_time
                user_data["leveling"]["voice_xp"] = new_time * self.VOICE_XP_PER_MIN
                user_data["leveling"]["total_xp"] = user_data["leveling"]["text_xp"] + user_data["leveling"]["voice_xp"]
                
                action_word = "начислено" if действие.value == "add" else "снято"
                await interaction.followup.send(
                    f"✅ {участник.mention}: {action_word} {количество} мин. голосовой активности. Теперь: {new_time} мин.",
                    ephemeral=True
                )
            
            save_user_data(участник.id, user_data)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Ошибка: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingAdminCommands(bot))  # Используем новое название класса