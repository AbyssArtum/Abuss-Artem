import discord
from cogs.survey_modal import SurveyModal  # NEW

class SurveyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 Заполнить анкету",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_survey_button"  # NEW: Уникальный ID
    )
    async def button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SurveyModal())  # NEW: Открываем модальное окно

def get_template():
    embed = discord.Embed(
        title="📝 Правила заполнения анкеты",
        description=(
            "1. Заполняйте все поля честно.\n"
            "2. Не используйте оскорбления.\n"
            "3. Минимум 100 символов в разделе 'О себе'.\n\n"
            "После проверки модератором анкета будет опубликована."
        ),
        color=discord.Color.blue()
    )
    view = SurveyButton()
    return embed, view