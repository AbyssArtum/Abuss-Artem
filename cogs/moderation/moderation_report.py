import discord
from discord import app_commands, ui
from discord.ext import commands
from .moderation_warns import WarnModal
from .moderation_mute import MuteDurationView
from .moderation_del import ConfirmActionModal

class ReportActionView(ui.View):
    def __init__(self, target: discord.Member, reporter: discord.Member, reason: str):
        super().__init__(timeout=None)
        self.target = target
        self.reporter = reporter
        self.reason = reason

    @ui.button(label="Наказать", style=discord.ButtonStyle.red, emoji="🔨")
    async def punish(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        view.add_item(PunishmentSelect(self.target, self.reason))
        await interaction.response.send_message(
            "Выберите тип наказания:",
            view=view,
            ephemeral=True
        )

    @ui.button(label="Игнорировать", style=discord.ButtonStyle.gray, emoji="❌")
    async def ignore(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "Жалоба проигнорирована.",
            ephemeral=True
        )
        await interaction.message.delete()

class PunishmentSelect(ui.Select):
    def __init__(self, target: discord.Member, reason: str):
        options = [
            discord.SelectOption(label="Предупреждение", value="warn", emoji="⚠️"),
            discord.SelectOption(label="Мут", value="mute", emoji="🔇"),
            discord.SelectOption(label="Кик", value="kick", emoji="👢"),
            discord.SelectOption(label="Бан", value="ban", emoji="🔨")
        ]
        super().__init__(placeholder="Выберите тип наказания...", options=options)
        self.target = target
        self.reason = reason

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("ModerationReports")
        if self.values[0] == "warn":
            await interaction.response.send_modal(WarnModal(self.target, self.reason, cog))
        elif self.values[0] == "mute":
            await interaction.response.send_message(
                "Выберите длительность мута:",
                view=MuteDurationView(self.target, self.reason, cog),
                ephemeral=True
            )
        else:
            action = "кик" if self.values[0] == "kick" else "бан"
            await interaction.response.send_modal(
                ConfirmActionModal(self.target, self.reason, action, cog)
            )

class ModerationReports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_report_action(self, message: discord.Message, action: str):
        embed = discord.Embed(
            title=f"Жалоба обработана: {action}",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Модератор", value=self.bot.user.mention)
        await message.edit(embed=embed, view=None)

    @app_commands.command(name="жалоба", description="Отправить жалобу на участника")
    @app_commands.describe(участник="Участник для жалобы", причина="Причина жалобы")
    async def report(self, interaction: discord.Interaction, участник: discord.Member, причина: str):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog or not base_cog.log_channel:
            return await interaction.response.send_message(
                "Система жалоб не настроена администратором.",
                ephemeral=True
            )
            
        channel = self.bot.get_channel(base_cog.log_channel)
        if not channel:
            return await interaction.response.send_message(
                "Ошибка: канал для логов не найден.",
                ephemeral=True
            )
            
        embed = discord.Embed(
            title=f"Жалоба на {участник.display_name} ({участник.mention})",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="От", value=interaction.user.mention)
        embed.add_field(name="Причина", value=причина)
        embed.add_field(name="ID", value=участник.id)
        embed.set_footer(text=f"Сегодня, в {discord.utils.format_dt(discord.utils.utcnow(), 't')}")
        
        await channel.send(
            embed=embed,
            view=ReportActionView(участник, interaction.user, причина)
        )
        await interaction.response.send_message(
            "✅ Ваша жалоба отправлена модераторам.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(ModerationReports(bot))