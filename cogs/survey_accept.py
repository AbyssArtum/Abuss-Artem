import discord
from discord.ext import commands
from discord import app_commands
import re
import json

from utils.db import save_survey, get_survey_by_user  # <-- исправлено здесь

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
        await interaction.response.send_message("✅ Анкета одобрена и опубликована.", ephemeral=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.author.send(
                "❌ Ваша анкета была отклонена модератором. Вы можете отредактировать её и отправить заново с помощью команды `/анкета редактировать`."
            )
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ Не удалось отправить пользователю ЛС.", ephemeral=True)
            return

        await interaction.response.send_message("❌ Анкета отклонена. Уведомление отправлено пользователю.", ephemeral=True)


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

            embed = discord.Embed(
                title=f"📝 Анкета пользователя {user.display_name}",
                color=discord.Color.green()
            )
            embed.add_field(name="Имя / Псевдоним", value=data["name"], inline=False)
            embed.add_field(name="Возраст", value=data["age"], inline=False)
            embed.add_field(name="Вид деятельности", value=data["creative_fields"], inline=False)
            embed.add_field(name="О себе", value=data["about"], inline=False)
            embed.add_field(name="Соцсети", value=data["socials"] if data["socials"] else "—", inline=False)
            embed.set_footer(text=f"Пользователь: {user.display_name}")

            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(SurveyCog(bot))
