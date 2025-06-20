import discord
from discord.ext import commands
from discord import Member
from datetime import datetime

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.booster_role_id = 1384488323652915220  # 🔁 Заменить на ID роли бустера
        self.channel_id = 1284472130754449453      # 🔁 ID канала для сообщений

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        channel = member.guild.get_channel(self.channel_id)
        if channel:
            embed = discord.Embed(
                title="👋 Новый участник!",
                description=f"**{member.display_name}** присоединился к серверу.",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        channel = member.guild.get_channel(self.channel_id)
        if channel:
            embed = discord.Embed(
                title="😢 Участник покинул сервер",
                description=f"**{member.display_name}** больше с нами нет.",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        booster_role = after.guild.get_role(self.booster_role_id)
        if booster_role is None:
            return

        if booster_role not in before.roles and booster_role in after.roles:
            channel = after.guild.get_channel(self.channel_id)
            if channel:
                embed = discord.Embed(
                    title="💜 Сервер забущен!",
                    description=f"**{after.display_name}** только что **забустил сервер**. Благодарим за поддержку!",
                    color=discord.Color.purple(),
                    timestamp=datetime.utcnow()
                )
                embed.set_thumbnail(url=after.avatar.url if after.avatar else after.default_avatar.url)
                await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
