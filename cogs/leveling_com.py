import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from typing import Optional

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
    async def manage_xp(
        self,
        interaction: discord.Interaction,
        действие: app_commands.Choice[str],
        тип: app_commands.Choice[str],
        количество: int,
        участник: discord.Member
    ):
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
            
            if тип.value == "general":
                # Получаем текущие данные
                current_xp, current_level = leveling_cog.get_user_stats(участник.id, interaction.guild_id)
                
                # Обновляем опыт
                new_level = await leveling_cog.update_level(
                    участник.id,
                    interaction.guild_id,
                    amount
                )
                
                # Формируем сообщение
                action_word = "начислен" if действие.value == "add" else "снят"
                message = f"✅ Участнику {участник.mention} {action_word} {количество} общего опыта"
                
                if new_level:
                    message += f" и он {'достиг' if действие.value == 'add' else 'понизился до'} {new_level} уровня!"
                
                await interaction.followup.send(message, ephemeral=True)
                    
            elif тип.value == "voice":
                conn = None
                try:
                    conn = sqlite3.connect('data/levels.db')
                    cursor = conn.cursor()
                    
                    cursor.execute(
                        '''SELECT voice_time FROM levels 
                        WHERE user_id=? AND guild_id=?''',
                        (участник.id, interaction.guild_id)
                    )
                    result = cursor.fetchone()
                    
                    if not result:
                        if действие.value == "add":
                            cursor.execute(
                                '''INSERT INTO levels 
                                (user_id, guild_id, voice_time, voice_xp) 
                                VALUES (?, ?, ?, ?)''',
                                (участник.id, interaction.guild_id, max(0, amount), 0)
                            )
                            conn.commit()
                        else:
                            await interaction.followup.send(
                                "❌ У участника нет голосовой активности для снятия!",
                                ephemeral=True
                            )
                            return
                    else:
                        current_time = result[0]
                        new_time = max(0, current_time + amount)
                        
                        if действие.value == "remove" and количество > current_time:
                            await interaction.followup.send(
                                "❌ Нельзя снять больше минут, чем есть у участника!",
                                ephemeral=True
                            )
                            return
                        
                        cursor.execute(
                            '''UPDATE levels SET 
                            voice_time=?
                            WHERE user_id=? AND guild_id=?''',
                            (new_time, участник.id, interaction.guild_id)
                        )
                        conn.commit()
                    
                    action_word = "начислено" if действие.value == "add" else "снято"
                    await interaction.followup.send(
                        f"✅ Участнику {участник.mention} {action_word} {количество} минут голосовой активности",
                        ephemeral=True
                    )
                    
                except Exception as e:
                    await interaction.followup.send(
                        f"❌ Ошибка работы с базой данных: {str(e)}",
                        ephemeral=True
                    )
                finally:
                    if conn:
                        conn.close()
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ Произошла ошибка: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(LevelingCommands(bot))