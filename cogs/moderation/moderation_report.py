import discord
from discord import app_commands, ui
from discord.ext import commands
from datetime import datetime
from typing import Optional
from utils.user_data import get_user_data, save_user_data
import json
from pathlib import Path

class ReportSystem:
    def __init__(self):
        self.reports_file = Path("data/reports.json")
        self._init_storage()

    def _init_storage(self):
        if not self.reports_file.exists():
            with open(self.reports_file, "w", encoding="utf-8") as f:
                json.dump({"reports": {}, "last_id": 0}, f)

    def _load_data(self):
        with open(self.reports_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_data(self, data):
        with open(self.reports_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def add_report(self, guild_id: int, target_id: int, reporter_id: int, reason: str) -> int:
        data = self._load_data()
        report_id = data["last_id"] + 1
        
        report = {
            "id": report_id,
            "guild_id": guild_id,
            "target_id": target_id,
            "reporter_id": reporter_id,
            "reason": reason,
            "status": "pending",
            "moderator_id": None,
            "action_taken": None,
            "created_at": datetime.now().isoformat()
        }
        
        data["reports"][str(report_id)] = report
        data["last_id"] = report_id
        self._save_data(data)
        
        return report_id

    def update_report(self, report_id: int, status: str, moderator_id: int, action_taken: str):
        data = self._load_data()
        if str(report_id) in data["reports"]:
            report = data["reports"][str(report_id)]
            report["status"] = status
            report["moderator_id"] = moderator_id
            report["action_taken"] = action_taken
            self._save_data(data)
            return True
        return False

class ReportActionView(ui.View):
    def __init__(self, target: discord.Member, reporter: discord.Member, reason: str, report_id: int):
        super().__init__(timeout=None)
        self.target = target
        self.reporter = reporter
        self.reason = reason
        self.report_id = report_id

    @ui.button(label="Наказать", style=discord.ButtonStyle.red, emoji="🔨")
    async def punish(self, interaction: discord.Interaction, button: ui.Button):
        view = PunishmentSelectView(self.target, self.reason, self.report_id)
        await interaction.response.send_message(
            "Выберите тип наказания:",
            view=view,
            ephemeral=True
        )

    @ui.button(label="Игнорировать", style=discord.ButtonStyle.gray, emoji="❌")
    async def ignore(self, interaction: discord.Interaction, button: ui.Button):
        report_cog = interaction.client.get_cog("ModerationReports")
        if report_cog:
            report_cog.report_system.update_report(
                self.report_id,
                status="rejected",
                moderator_id=interaction.user.id,
                action_taken="ignored"
            )
        
        # Добавляем запись в профиль пользователя
        target_data = get_user_data(self.target.id)
        if "moderation" not in target_data:
            target_data["moderation"] = {"reports": []}
        
        target_data["moderation"]["reports"].append({
            "report_id": self.report_id,
            "status": "rejected",
            "moderator_id": interaction.user.id,
            "action": "ignored",
            "timestamp": datetime.now().isoformat()
        })
        save_user_data(self.target.id, target_data)
        
        await interaction.message.edit(view=None)
        await interaction.response.send_message("Жалоба проигнорирована.", ephemeral=True)

class PunishmentSelectView(ui.View):
    def __init__(self, target: discord.Member, reason: str, report_id: int):
        super().__init__()
        self.target = target
        self.reason = reason
        self.report_id = report_id

    @ui.select(
        placeholder="Выберите наказание",
        options=[
            discord.SelectOption(label="Предупреждение", value="warn"),
            discord.SelectOption(label="Мут", value="mute"),
            discord.SelectOption(label="Кик", value="kick"),
            discord.SelectOption(label="Бан", value="ban")
        ]
    )
    async def select_punishment(self, interaction: discord.Interaction, select: ui.Select):
        report_cog = interaction.client.get_cog("ModerationReports")
        if not report_cog:
            return await interaction.response.send_message("Ошибка системы!", ephemeral=True)

        action = select.values[0]
        report_cog.report_system.update_report(
            self.report_id,
            status="approved",
            moderator_id=interaction.user.id,
            action_taken=action
        )
        
        # Добавляем запись в профиль пользователя
        target_data = get_user_data(self.target.id)
        if "moderation" not in target_data:
            target_data["moderation"] = {"reports": []}
        
        target_data["moderation"]["reports"].append({
            "report_id": self.report_id,
            "status": "approved",
            "moderator_id": interaction.user.id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        save_user_data(self.target.id, target_data)
        
        # Применяем наказание
        if action == "warn":
            warn_cog = interaction.client.get_cog("ModerationWarns")
            if warn_cog:
                await warn_cog.warn(interaction, self.target, self.reason)
        # Здесь можно добавить обработку других действий (мут, кик, бан)
        
        await interaction.message.edit(view=None)
        await interaction.response.send_message(
            f"Наказание '{action}' применено к {self.target.mention}",
            ephemeral=True
        )

class ModerationReports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.report_system = ReportSystem()
        self.reports_log_channel = None  # Будет установлено при загрузке

    async def setup_log_channel(self, guild_id: int):
        # Здесь можно реализовать логику получения канала логов
        # Например, из конфига или базы данных
        return None

    @commands.Cog.listener()
    async def on_ready(self):
        # При загрузке кога ищем канал для логов
        for guild in self.bot.guilds:
            self.reports_log_channel = await self.setup_log_channel(guild.id)

    @app_commands.command(name="жалоба", description="Отправить жалобу на участника")
    @app_commands.describe(участник="Участник для жалобы", причина="Причина жалобы")
    async def report_command(self, interaction: discord.Interaction, 
                           участник: discord.Member, 
                           причина: str):
        if участник.bot:
            return await interaction.response.send_message(
                "Нельзя пожаловаться на бота!", 
                ephemeral=True
            )

        if участник.id == interaction.user.id:
            return await interaction.response.send_message(
                "Нельзя пожаловаться на самого себя!",
                ephemeral=True
            )

        if not self.reports_log_channel:
            self.reports_log_channel = await self.setup_log_channel(interaction.guild.id)
            if not self.reports_log_channel:
                return await interaction.response.send_message(
                    "❌ Система жалоб не настроена администратором.",
                    ephemeral=True
                )

        try:
            report_id = self.report_system.add_report(
                guild_id=interaction.guild.id,
                target_id=участник.id,
                reporter_id=interaction.user.id,
                reason=причина
            )

            embed = discord.Embed(
                title=f"Жалоба #{report_id} на {участник.display_name}",
                color=discord.Color.red(),
                description=f"**Причина:** {причина}"
            )
            embed.add_field(name="Отправитель", value=interaction.user.mention)
            embed.add_field(name="Участник", value=участник.mention)
            embed.set_footer(text=f"ID: {участник.id}")

            await self.reports_log_channel.send(
                embed=embed,
                view=ReportActionView(участник, interaction.user, причина, report_id)
            )

            await interaction.response.send_message(
                "✅ Ваша жалоба отправлена модераторам.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Произошла ошибка: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="жалобы", description="Посмотреть жалобы на участника")
    @app_commands.describe(участник="Участник для проверки")
    async def view_reports(self, interaction: discord.Interaction, участник: discord.Member):
        user_data = get_user_data(участник.id)
        
        if "moderation" not in user_data or not user_data["moderation"].get("reports"):
            return await interaction.response.send_message(
                f"На {участник.mention} нет жалоб.",
                ephemeral=True
            )
            
        reports = user_data["moderation"]["reports"]
        approved = sum(1 for r in reports if r["status"] == "approved")
        rejected = sum(1 for r in reports if r["status"] == "rejected")
        pending = sum(1 for r in reports if r["status"] == "pending")
        
        embed = discord.Embed(
            title=f"Жалобы на {участник.display_name}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Всего жалоб", value=len(reports), inline=False)
        embed.add_field(name="Одобрено", value=approved, inline=True)
        embed.add_field(name="Отклонено", value=rejected, inline=True)
        embed.add_field(name="На рассмотрении", value=pending, inline=True)
        
        # Показываем последние 5 жалоб
        recent_reports = sorted(reports, key=lambda x: x["timestamp"], reverse=True)[:5]
        for i, report in enumerate(recent_reports, 1):
            moderator = await self.bot.fetch_user(report["moderator_id"]) if report["moderator_id"] else "Не назначен"
            embed.add_field(
                name=f"Жалоба #{report.get('report_id', '?')}",
                value=f"**Статус:** {report['status']}\n"
                      f"**Действие:** {report.get('action', 'нет')}\n"
                      f"**Модератор:** {moderator.mention if isinstance(moderator, discord.User) else moderator}",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationReports(bot))