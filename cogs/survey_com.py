import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from cogs.survey_modal import SurveyModal

CONFIG_FILE = "data/survey_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

class SurveyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_survey_embed(self, user_id: int):
        """Создает embed для просмотра анкеты"""
        try:
            # Используем существующую функцию из utils/db.py
            from utils.db import get_survey_by_user
            
            data = get_survey_by_user(user_id)
            if not data:
                return None

            # Получаем объект пользователя
            user = await self.bot.fetch_user(user_id)
            status = data.get("status", "на модерации")
            
            # Создаем embed
            embed = discord.Embed(
                title=f"Анкета пользователя {user.display_name}",
                color=discord.Color.blue()
            )
            
            # Добавляем поля анкеты
            embed.add_field(name="Имя/Псевдоним", value=data.get("name", "Не указано"), inline=False)
            embed.add_field(name="Возраст", value=data.get("age", "Не указано"), inline=False)
            embed.add_field(name="Деятельность", value=data.get("creative_fields", "Не указано"), inline=False)
            
            # Обрабатываем поле "О себе" (ограничение длины)
            about = data.get("about", "Не указано")
            if len(about) > 1000:
                about = about[:1000] + "..."
            embed.add_field(name="О себе", value=about, inline=False)
            
            # Обработка статуса анкеты
            if status == "rejected":
                embed.color = discord.Color.red()
                embed.add_field(name="Причина отклонения", 
                              value=data.get("reject_reason", "Не указана"), 
                              inline=False)
            elif status == "approved":
                embed.color = discord.Color.green()
            
            # Устанавливаем footer с статусом
            status_text = {
                "approved": "одобрена",
                "rejected": "отклонена",
            }.get(status, "на модерации")
            
            embed.set_footer(text=f"Статус: {status_text}")
            
            return embed

        except Exception as e:
            print(f"Ошибка при создании embed: {e}")
            return None

    @app_commands.command(name="анкета", description="Управление анкетами")
    @app_commands.describe(
        действие="Выберите действие: редактировать, посмотреть, настроить",
        участник="Участник для просмотра анкеты (требуется, если действие 'посмотреть')",
        цель="Что настраиваем (модерация или публикация, требуется при 'настроить')",
        канал="Канал для настройки (требуется при 'настроить')"
    )
    @app_commands.choices(
        действие=[
            app_commands.Choice(name="редактировать", value="edit"),
            app_commands.Choice(name="посмотреть", value="view"),
            app_commands.Choice(name="настроить", value="config"),
        ],
        цель=[
            app_commands.Choice(name="модерация", value="moderation"),
            app_commands.Choice(name="публикация", value="publication"),
        ]
    )
    async def анкета(
        self,
        interaction: discord.Interaction,
        действие: app_commands.Choice[str],
        участник: discord.Member = None,
        цель: app_commands.Choice[str] = None,
        канал: discord.TextChannel = None
    ):
        try:
            if действие.value == "edit":
                await interaction.response.send_modal(SurveyModal())
                return

            await interaction.response.defer(ephemeral=True)

            if действие.value == "view":
                if not участник:
                    await interaction.followup.send(
                        "❌ Для просмотра анкеты укажите участника.", 
                        ephemeral=True
                    )
                    return
                
                embed = await self.get_survey_embed(участник.id)
                
                if embed:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(
                        "❌ Анкета не найдена в системе.", 
                        ephemeral=True
                    )

            elif действие.value == "config":
                if not цель or not канал:
                    await interaction.followup.send(
                        "❌ Для настройки укажите цель и канал.",
                        ephemeral=True
                    )
                    return
                
                config = load_config()
                config[цель.value] = str(канал.id)
                save_config(config)
                
                await interaction.followup.send(
                    f"✅ Канал для **{цель.name}** установлен: {канал.mention}",
                    ephemeral=True
                )
                
        except Exception as e:
            error_msg = f"⚠️ Произошла ошибка: {str(e)}"
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SurveyCommands(bot))