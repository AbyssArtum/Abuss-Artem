import discord
from discord.ext import commands
from discord import app_commands
import json
import os
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

    @app_commands.command(name="анкета", description="Управление анкетами")
    @app_commands.describe(
        действие="Выберите действие: редактировать, посмотреть, настроить",
        участник="Участник для просмотра анкеты (требуется, если действие 'посмотреть')",
        цель="Что настраиваем (модерация или публикация, требуется при 'настроить')",
        канал="Канал для настройки (требуется при 'настроить')"
    )
    @app_commands.choices(
        действие=[
            app_commands.Choice(name="редактировать", value="редактировать"),
            app_commands.Choice(name="посмотреть", value="посмотреть"),
            app_commands.Choice(name="настроить", value="настроить"),
        ],
        цель=[
            app_commands.Choice(name="модерация", value="модерация"),
            app_commands.Choice(name="публикация", value="публикация"),
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
            if действие.value == "редактировать":
                # Правильный способ отправки модального окна
                await interaction.response.send_modal(SurveyModal())
                return

            # Для остальных команд используем defer
            await interaction.response.defer(ephemeral=True)

            if действие.value == "посмотреть":
                if not участник:
                    await interaction.followup.send(
                        "Для действия 'посмотреть' нужно указать участника.", 
                        ephemeral=True
                    )
                    return
                
                from data.users import get_survey_embed
                embed = get_survey_embed(участник.id)
                
                if embed:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send("Анкета не найдена.", ephemeral=True)

            elif действие.value == "настроить":
                if not цель or not канал:
                    await interaction.followup.send(
                        "Для действия 'настроить' нужно указать цель и канал.",
                        ephemeral=True
                    )
                    return
                
                config = load_config()
                config[цель.value] = str(канал.id)
                save_config(config)
                
                await interaction.followup.send(
                    f"Канал для **{цель.name}** установлен: {канал.mention}",
                    ephemeral=True
                )
                
        except Exception as e:
            error_msg = f"Произошла ошибка: {str(e)}"
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SurveyCommands(bot))