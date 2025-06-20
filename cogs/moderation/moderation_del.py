import discord
from discord import app_commands, ui
from discord.ext import commands

class ConfirmActionModal(ui.Modal, title="Подтверждение действия"):
    def __init__(self, target: discord.Member, reason: str, action: str, cog):
        super().__init__()
        self.target = target
        self.original_reason = reason
        self.action = action
        self.cog = cog
        
        self.reason = ui.TextInput(
            label="Причина",
            style=discord.TextStyle.long,
            placeholder=reason,
            default=reason,
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        if self.action.lower() == "кик":
            await self.cog.kick_user(interaction, self.target, self.reason.value, self.cog.message)
        elif self.action.lower() == "бан":
            await self.cog.ban_user(interaction, self.target, self.reason.value, self.cog.message)

class ModerationDel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def kick_user(self, interaction, member, reason, report_message=None):
        try:
            await member.kick(reason=reason)
            
            embed = discord.Embed(
                title="✅ Участник кикнут",
                description=f"{member.mention} был кикнут с сервера.",
                color=discord.Color.red()
            )
            embed.add_field(name="Причина", value=reason)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Отправка уведомления
            await self.send_kick_notification(member, interaction.user, reason)
            
            # Обновление сообщения жалобы
            if report_message and hasattr(self.bot.get_cog("ModerationReports"), 'log_report_action'):
                await self.bot.get_cog("ModerationReports").log_report_action(report_message, "кик")

        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

    async def send_kick_notification(self, member, moderator, reason):
        embed = discord.Embed(
            title="Вы были кикнуты",
            description=f"С сервера {moderator.guild.name} вас кикнули.",
            color=discord.Color.red()
        )
        embed.add_field(name="Модератор", value=moderator.mention)
        embed.add_field(name="Причина", value=reason)
        
        try:
            await member.send(embed=embed)
        except:
            pass

    async def ban_user(self, interaction, member, reason, report_message=None):
        try:
            await member.ban(reason=reason, delete_message_days=0)
            
            embed = discord.Embed(
                title="✅ Участник забанен",
                description=f"{member.mention} был забанен на сервере.",
                color=discord.Color.red()
            )
            embed.add_field(name="Причина", value=reason)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Отправка уведомления
            await self.send_ban_notification(member, interaction.user, reason)
            
            # Обновление сообщения жалобы
            if report_message and hasattr(self.bot.get_cog("ModerationReports"), 'log_report_action'):
                await self.bot.get_cog("ModerationReports").log_report_action(report_message, "бан")

        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

    async def send_ban_notification(self, member, moderator, reason):
        embed = discord.Embed(
            title="Вы были забанены",
            description=f"На сервере {moderator.guild.name} вас забанили.",
            color=discord.Color.red()
        )
        embed.add_field(name="Модератор", value=moderator.mention)
        embed.add_field(name="Причина", value=reason)
        
        try:
            await member.send(embed=embed)
        except:
            pass

    @app_commands.command(name="кик", description="Кикнуть участника с сервера")
    @app_commands.describe(участник="Участник для кика", причина="Причина")
    @commands.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, участник: discord.Member, причина: str = None):
        modal = ConfirmActionModal(участник, причина or "Не указана", "кик", self)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="бан", description="Забанить участника на сервере")
    @app_commands.describe(участник="Участник для бана", причина="Причина")
    @commands.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, участник: discord.Member, причина: str = None):
        modal = ConfirmActionModal(участник, причина or "Не указана", "бан", self)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="разбан", description="Разбанить участника")
    @app_commands.describe(user_id="ID пользователя для разбана", причина="Причина")
    @commands.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, причина: str = None):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=причина)
            
            embed = discord.Embed(
                title="✅ Участник разбанен",
                description=f"{user.mention} был разбанен на сервере.",
                color=discord.Color.green()
            )
            embed.add_field(name="Причина", value=причина or "Не указана")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Отправка уведомления
            embed = discord.Embed(
                title="Вы были разбанены",
                description=f"На сервере {interaction.guild.name} вас разбанили.",
                color=discord.Color.green()
            )
            embed.add_field(name="Модератор", value=interaction.user.mention)
            try:
                await user.send(embed=embed)
            except:
                pass
            
        except Exception as e:
            await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationDel(bot))