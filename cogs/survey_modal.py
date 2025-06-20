import discord
from discord import ui
from discord.ui import Modal, TextInput
import json
from pathlib import Path
from utils.user_data import get_user_data, save_user_data

CONFIG_FILE = "data/survey_config.json"

class SurveyModal(Modal, title="📝 Заполнение анкеты"):
    name = TextInput(
        label="Имя / Псевдоним",
        placeholder="Как к вам обращаться?",
        required=True,
        max_length=100
    )
    age = TextInput(
        label="Возраст",
        placeholder="Укажите ваш возраст",
        required=True,
        max_length=20
    )
    creativity = TextInput(
        label="Творческая деятельность",
        placeholder="Чем вы занимаетесь?",
        required=True,
        max_length=250
    )
    about = TextInput(
        label="О себе",
        style=discord.TextStyle.paragraph,
        placeholder="Расскажите о себе (минимум 100 символов)",
        required=True,
        min_length=100,
        max_length=2000
    )
    socials = TextInput(
        label="Социальные сети",
        placeholder="Ссылки на ваши соцсети (не обязательно)",
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Получаем или создаем данные пользователя
            user_data = get_user_data(interaction.user.id)
            
            # Сохраняем анкету
            survey_data = {
                "name": self.name.value,
                "age": self.age.value,
                "creativity": self.creativity.value,
                "about": self.about.value,
                "socials": self.socials.value if self.socials.value else "Не указано",
                "status": "pending",
                "timestamp": interaction.created_at.isoformat()
            }

            if "surveys" not in user_data:
                user_data["surveys"] = {"current": None, "history": []}
            
            user_data["surveys"]["current"] = survey_data
            user_data["surveys"]["history"].append(survey_data)
            save_user_data(interaction.user.id, user_data)

            # Отправляем на модерацию
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            mod_channel = interaction.client.get_channel(int(config["модерация"]))
            if mod_channel:
                embed = discord.Embed(
                    title="📥 Новая анкета на модерации",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Имя", value=self.name.value, inline=False)
                embed.add_field(name="Возраст", value=self.age.value, inline=False)
                embed.add_field(name="Творчество", value=self.creativity.value, inline=False)
                embed.add_field(name="О себе", value=self.about.value[:500] + "..." if len(self.about.value) > 500 else self.about.value, inline=False)
                embed.add_field(name="Соцсети", value=self.socials.value if self.socials.value else "—", inline=False)
                embed.set_footer(text=f"Отправил: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

                view = SurveyModerationView(interaction.user.id)
                await mod_channel.send(embed=embed, view=view)
                await interaction.response.send_message("✅ Анкета отправлена на модерацию!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Ошибка: канал модерации не найден", ephemeral=True)

        except Exception as e:
            print(f"Ошибка при отправке анкеты: {e}")
            await interaction.response.send_message("❌ Произошла ошибка при отправке анкеты", ephemeral=True)

class SurveyModerationView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="✅ Одобрить", style=discord.ButtonStyle.success, custom_id="approve_survey")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Логика одобрения
        user_data = get_user_data(self.user_id)
        if not user_data or "surveys" not in user_data:
            return await interaction.response.send_message("❌ Анкета не найдена", ephemeral=True)

        user_data["surveys"]["current"]["status"] = "approved"
        save_user_data(self.user_id, user_data)

        # Отправка в канал публикации
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        pub_channel = interaction.client.get_channel(int(config["публикация"]))
        if pub_channel:
            embed = discord.Embed(
                title="📝 Новая анкета участника",
                color=discord.Color.green()
            )
            survey = user_data["surveys"]["current"]
            embed.add_field(name="Имя", value=survey["name"], inline=False)
            embed.add_field(name="Возраст", value=survey["age"], inline=False)
            embed.add_field(name="Творчество", value=survey["creativity"], inline=False)
            embed.add_field(name="О себе", value=survey["about"][:500] + "..." if len(survey["about"]) > 500 else survey["about"], inline=False)
            embed.add_field(name="Соцсети", value=survey["socials"], inline=False)
            
            msg = await pub_channel.send(embed=embed)
            await msg.add_reaction("❤️")
            await interaction.response.send_message("✅ Анкета одобрена и опубликована!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ошибка: канал публикации не найден", ephemeral=True)

    @discord.ui.button(label="❌ Отклонить", style=discord.ButtonStyle.danger, custom_id="reject_survey")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectionReasonModal(self.user_id))

class RejectionReasonModal(Modal, title="Укажите причину отклонения"):
    reason = TextInput(
        label="Причина отклонения",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        user_data = get_user_data(self.user_id)
        if not user_data or "surveys" not in user_data:
            return await interaction.response.send_message("❌ Анкета не найдена", ephemeral=True)

        user_data["surveys"]["current"]["status"] = "rejected"
        user_data["surveys"]["current"]["rejection_reason"] = self.reason.value
        save_user_data(self.user_id, user_data)

        # Отправка уведомления пользователю
        user = await interaction.client.fetch_user(self.user_id)
        if user:
            try:
                embed = discord.Embed(
                    title="❌ Ваша анкета была отклонена",
                    color=discord.Color.red()
                )
                survey = user_data["surveys"]["current"]
                embed.add_field(name="Причина", value=self.reason.value, inline=False)
                embed.add_field(name="Имя", value=survey["name"], inline=False)
                embed.add_field(name="Возраст", value=survey["age"], inline=False)
                embed.add_field(name="Творчество", value=survey["creativity"], inline=False)
                embed.add_field(name="О себе", value=survey["about"], inline=False)
                embed.add_field(name="Соцсети", value=survey["socials"], inline=False)
                
                await user.send(embed=embed)
                await interaction.response.send_message("✅ Пользователь уведомлен об отклонении", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("⚠️ Не удалось отправить ЛС пользователю", ephemeral=True)