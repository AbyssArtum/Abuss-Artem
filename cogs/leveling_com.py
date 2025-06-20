import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.user_data import get_user_data, save_user_data

class LevelingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
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
        """Управление опытом участников"""
        if количество <= 0:
            return await interaction.response.send_message(
                "❌ Количество должно быть положительным числом!",
                ephemeral=True
            )
        
        leveling_cog = self.bot.get_cog("LevelingSystem")
        if not leveling_cog:
            return await interaction.response.send_message(
                "❌ Система уровней не загружена!",
                ephemeral=True
            )
        
        try:
            await interaction.response.defer(ephemeral=True)
            
            multiplier = 1 if действие.value == "add" else -1
            amount = количество * multiplier
            
            user_data = get_user_data(участник.id)
            
            if "leveling" not in user_data:
                user_data["leveling"] = {
                    "text_xp": 0,
                    "voice_xp": 0,
                    "total_xp": 0,
                    "level": 1,
                    "voice_time": 0
                }
            
            if тип.value == "general":
                # Обновляем общий опыт
                xp_earned = amount
                user_data["leveling"]["text_xp"] = max(0, user_data["leveling"]["text_xp"] + xp_earned)
                user_data["leveling"]["total_xp"] = max(0, user_data["leveling"]["total_xp"] + xp_earned)
                
                # Проверяем уровень
                old_level = user_data["leveling"]["level"]
                new_level = leveling_cog.get_level_from_xp(user_data["leveling"]["total_xp"])
                user_data["leveling"]["level"] = new_level
                
                save_user_data(участник.id, user_data)
                
                action_word = "начислен" if действие.value == "add" else "снят"
                message = f"✅ Участнику {участник.mention} {action_word} {количество} общего опыта"
                
                if new_level != old_level:
                    message += f" и он {'достиг' if действие.value == 'add' else 'понизился до'} {new_level} уровня!"
                
                await interaction.followup.send(message, ephemeral=True)
                    
            elif тип.value == "voice":
                # Обновляем голосовую активность
                minutes_earned = amount
                user_data["leveling"]["voice_time"] = max(0, user_data["leveling"]["voice_time"] + minutes_earned)
                
                # Пересчитываем голосовой опыт
                voice_xp = int(minutes_earned * leveling_cog.LEVEL_SETTINGS['voice_xp_per_min'])
                user_data["leveling"]["voice_xp"] = max(0, user_data["leveling"]["voice_xp"] + voice_xp)
                user_data["leveling"]["total_xp"] = max(0, user_data["leveling"]["total_xp"] + voice_xp)
                
                # Проверяем уровень
                old_level = user_data["leveling"]["level"]
                new_level = leveling_cog.get_level_from_xp(user_data["leveling"]["total_xp"])
                user_data["leveling"]["level"] = new_level
                
                save_user_data(участник.id, user_data)
                
                action_word = "начислено" if действие.value == "add" else "снято"
                message = f"✅ Участнику {участник.mention} {action_word} {количество} минут голосовой активности"
                
                if new_level != old_level:
                    message += f" и он {'достиг' if действие.value == 'add' else 'понизился до'} {new_level} уровня!"
                
                await interaction.followup.send(message, ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ Произошла ошибка: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingCommands(bot))