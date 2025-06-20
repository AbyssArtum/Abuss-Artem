import discord
from discord.ext import commands
from discord import app_commands
import re
import json
from datetime import datetime

from utils.db import save_survey, get_survey_by_user, update_survey_status  # Добавлен новый импорт

CONFIG_PATH = "config.json"
REACTION_EMOJI = "❤️"


def get_config_value(key):
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("анкетирование", {}).get(key)
    except FileNotFoundError:
        return None


class SurveyModal(discord.ui.Modal, title="📔 Отправка анкеты"):
    name = discord.ui.TextInput(label="Имя / Псевдоним", required=True, max_length=100)
    age = discord.ui.TextInput(label="Возраст", required=True, max_length=50)
    creative_fields = discord.ui.TextInput(label="Вид деятельности", required=True, max_length=200)
    about = discord.ui.TextInput(
        label="О себе",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=100
    )
    socials = discord.ui.TextInput(label="Ссылки на соцсети", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        if re.search(r"[A-Za-zА-Яа-яЁё]", self.age.value.strip()):
            return await interaction.response.send_message(
                "⚠️ В поле возраст нельзя вводить буквы. Пожалуйста, используйте только цифры и символы.",
                ephemeral=True
            )

        save_survey(
            user_id=interaction.user.id,
            name=self.name.value,
            age=self.age.value,
            creative_fields=self.creative_fields.value,
            about=self.about.value,
            socials=self.socials.value if self.socials.value else None
        )

        moderation_channel_id = get_config_value("канал_модерации")
        if not moderation_channel_id:
            return await interaction.response.send_message("❌ Канал модерации не настроен.", ephemeral=True)

        channel = interaction.client.get_channel(int(moderation_channel_id))
        if channel is None:
            return await interaction.response.send_message("❌ Не удалось найти канал модерации.", ephemeral=True)

        embed = discord.Embed(title="📥 Новая анкета на модерации", color=discord.Color.orange())
        embed.add_field(name="Имя / Псевдоним", value=self.name.value, inline=False)
        embed.add_field(name="Возраст", value=self.age.value, inline=False)
        embed.add_field(name="Вид деятельности", value=self.creative_fields.value, inline=False)
        embed.add_field(name="О себе", value=self.about.value, inline=False)
        embed.add_field(name="Соцсети", value=self.socials.value if self.socials.value else "—", inline=False)
        embed.set_footer(text=f"Отправлено: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        view = ModerationButtons(interaction.user)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Анкета отправлена на модерацию!", ephemeral=True)


class ModerationButtons(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=None)
        self.author = author

    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        publication_channel_id = get_config_value("канал_публикации")
        if not publication_channel_id:
            return await interaction.response.send_message("❌ Канал публикации не настроен.", ephemeral=True)

        data = get_survey_by_user(self.author.id)
        if not data:
            return await interaction.response.send_message("❌ Анкета не найдена.", ephemeral=True)

        channel = interaction.client.get_channel(int(publication_channel_id))
        if channel is None:
            return await interaction.response.send_message("❌ Не удалось найти канал публикации.", ephemeral=True)

        embed = discord.Embed(title="📝 Новая анкета", color=discord.Color.purple())
        embed.add_field(name="Имя / Псевдоним", value=data["name"], inline=False)
        embed.add_field(name="Возраст", value=data["age"], inline=False)
        embed.add_field(name="Вид деятельности", value=data["creative_fields"], inline=False)
        embed.add_field(name="О себе", value=data["about"], inline=False)
        embed.add_field(name="Соцсети", value=data["socials"] if data["socials"] else "—", inline=False)
        embed.set_footer(text=f"Отправлено пользователем: {self.author.display_name}")

        msg = await channel.send(embed=embed)
        await msg.add_reaction(REACTION_EMOJI)
        
        # Обновляем статус анкеты
        update_survey_status(self.author.id, "approved")
        await interaction.response.send_message("✅ Анкета одобрена и опубликована.", ephemeral=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Получаем данные анкеты
        data = get_survey_by_user(self.author.id)
        if not data:
            return await interaction.response.send_message("❌ Анкета не найдена.", ephemeral=True)

        # Запрашиваем причину отклонения
        modal = RejectReasonModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.reason:
            return

        # Формируем полное сообщение с анкетой
        message = (
            "**Ваша анкета была отклонена.**\n"
            f"Причина: {modal.reason}\n\n"
            "## Полный текст вашей анкеты:\n"
            f"### Имя / Псевдоним\n{data.get('name', 'Не указано')}\n\n"
            f"### Возраст\n{data.get('age', 'Не указано')}\n\n"
            f"### Вид деятельности\n{data.get('creative_fields', 'Не указано')}\n\n"
            f"### О себе\n{data.get('about', 'Не указано')}\n\n"
            f"### Соцсети\n{data.get('socials', 'Не указаны')}\n\n"
            "Вы можете отредактировать анкету и отправить её заново с помощью команды `/анкета редактировать`"
        )

        try:
            await self.author.send(message)
        except discord.Forbidden:
            await interaction.followup.send("⚠️ Не удалось отправить пользователю ЛС.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Анкета отклонена. Уведомление отправлено пользователю.", ephemeral=True)
        
        # Обновляем статус анкеты
        update_survey_status(self.author.id, "rejected", modal.reason)


class RejectReasonModal(discord.ui.Modal, title="Укажите причину отклонения"):
    reason = discord.ui.TextInput(
        label="Причина отклонения",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    def __init__(self):
        super().__init__()
        self.reason = None

    async def on_submit(self, interaction: discord.Interaction):
        self.reason = self.reason.value
        await interaction.response.defer()


class SurveyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="анкета", description="Редактировать или посмотреть анкету")
    @app_commands.describe(
        действие="Что сделать: редактировать или посмотреть",
        участник="Пользователь, чью анкету нужно посмотреть"
    )
    @app_commands.choices(
        действие=[
            app_commands.Choice(name="редактировать", value="редактировать"),
            app_commands.Choice(name="посмотреть", value="посмотреть")
        ]
    )
    async def анкета(
        self,
        interaction: discord.Interaction,
        действие: app_commands.Choice[str],
        участник: discord.User = None
    ):
        if действие.value == "редактировать":
            await interaction.response.send_modal(SurveyModal())
        elif действие.value == "посмотреть":
            user = участник or interaction.user
            data = get_survey_by_user(user.id)

            if not data:
                return await interaction.response.send_message("❌ Анкета не найдена.", ephemeral=True)

            status = data.get("status", "на модерации")
            status_emoji = "✅" if status == "approved" else "❌" if status == "rejected" else "🕒"
            
            embed = discord.Embed(
                title=f"{status_emoji} Анкета пользователя {user.display_name}",
                color=discord.Color.green() if status == "approved" else discord.Color.red() if status == "rejected" else discord.Color.orange()
            )
            embed.add_field(name="Имя / Псевдоним", value=data["name"], inline=False)
            embed.add_field(name="Возраст", value=data["age"], inline=False)
            embed.add_field(name="Вид деятельности", value=data["creative_fields"], inline=False)
            embed.add_field(name="О себе", value=data["about"], inline=False)
            embed.add_field(name="Соцсети", value=data["socials"] if data["socials"] else "—", inline=False)
            
            if status == "rejected" and data.get("reject_reason"):
                embed.add_field(name="Причина отклонения", value=data["reject_reason"], inline=False)
                
            embed.set_footer(text=f"Статус: {'одобрена' if status == 'approved' else 'отклонена' if status == 'rejected' else 'на модерации'}")

            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(SurveyCog(bot))