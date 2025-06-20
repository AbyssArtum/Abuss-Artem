import discord
from discord import app_commands, ui
from discord.ext import commands
import datetime

class MuteDurationView(ui.View):
    def __init__(self, target: discord.Member, reason: str, cog):
        super().__init__()
        self.target = target
        self.reason = reason
        self.cog = cog
        self.add_item(MuteDurationSelect())

class MuteDurationSelect(ui.Select):
    def __init__(self):
        durations = [
            ("1 минута", "1m"), ("5 минут", "5m"), ("10 минут", "10m"),
            ("30 минут", "30m"), ("1 час", "1h"), ("2 часа", "2h"),
            ("5 часов", "5h"), ("12 часов", "12h"), ("1 день", "1d"),
            ("2 дня", "2d"), ("7 дней", "7d"), ("14 дней", "14d"), 
            ("1 месяц", "30d")
        ]
        options = [discord.SelectOption(label=label, value=value) for label, value in durations]
        super().__init__(placeholder="Выберите длительность мута...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("ModerationMute")
        if not cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        await cog.mute_user(
            interaction,
            interaction.view.target,
            self.values[0],
            interaction.view.reason,
            interaction.message
        )

class ModerationMute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def mute_user(self, interaction, member, duration, reason, report_message=None):
        base_cog = self.bot.get_cog("ModerationBase")
        if not base_cog:
            return await interaction.response.send_message(
                "Ошибка: система модерации не загружена.",
                ephemeral=True
            )
            
        seconds = self.parse_duration(duration)
        if not seconds:
            return await interaction.response.send_message(
                "Неверный формат времени! Примеры: 1h, 30m, 7d",
                ephemeral=True
            )
            
        try:
            await member.timeout(discord.utils.utcnow() + datetime.timedelta(seconds=seconds), reason=reason)
            
            embed = discord.Embed(
                title="✅ Участник заглушен",
                description=f"{member.mention} был заглушен на {duration}.",
                color=discord.Color.red()
            )
            embed.add_field(name="Причина", value=reason)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Отправка уведомления
            await self.send_mute_notification(member, interaction.user, reason, duration)
            
            # Обновление сообщения жалобы
            if report_message and hasattr(self.bot.get_cog("ModerationReports"), 'log_report_action'):
                await self.bot.get_cog("ModerationReports").log_report_action(report_message, f"мут на {duration}")

        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

    async def send_mute_notification(self, member, moderator, reason, duration):
        embed = discord.Embed(
            title="Вы получили мут",
            description=f"На сервере {moderator.guild.name} вам выдали мут.",
            color=discord.Color.red()
        )
        embed.add_field(name="Модератор", value=moderator.mention)
        embed.add_field(name="Причина", value=reason)
        embed.add_field(name="Длительность", value=duration)
        
        try:
            await member.send(embed=embed)
        except:
            pass

    @app_commands.command(name="мут", description="Заглушить участника на время")
    @app_commands.describe(участник="Участник для мута", длительность="Длительность (1m, 1h, 1d)", причина="Причина")
    @commands.has_permissions(manage_roles=True)
    async def mute(self, interaction: discord.Interaction, участник: discord.Member, длительность: str, причина: str = None):
        await interaction.response.send_message(
            "Выберите длительность мута:",
            view=MuteDurationView(участник, причина or "Не указана", self),
            ephemeral=True
        )

    @app_commands.command(name="размут", description="Снять мут с участника")
    @app_commands.describe(участник="Участник для размута", причина="Причина")
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, interaction: discord.Interaction, участник: discord.Member, причина: str = None):
        try:
            await участник.timeout(None, reason=причина)
            
            embed = discord.Embed(
                title="✅ Мут снят",
                description=f"С участника {участник.mention} снят мут.",
                color=discord.Color.green()
            )
            embed.add_field(name="Причина", value=причина or "Не указана")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Отправка уведомления
            embed = discord.Embed(
                title="С вас снят мут",
                description=f"На сервере {interaction.guild.name} с вас снят мут.",
                color=discord.Color.green()
            )
            embed.add_field(name="Модератор", value=interaction.user.mention)
            try:
                await участник.send(embed=embed)
            except:
                pass
            
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

    @staticmethod
    def parse_duration(duration: str) -> int:
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        num = int(duration[:-1])
        unit = duration[-1].lower()
        return num * units.get(unit, 0)

async def setup(bot):
    await bot.add_cog(ModerationMute(bot))