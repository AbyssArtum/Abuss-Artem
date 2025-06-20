import sqlite3
import discord
from discord.ext import commands

class GuildConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="установить_guild_id")
    @commands.has_permissions(administrator=True)
    async def set_guild_id(self, ctx):
        """Автоматически обновляет guild_id в базе данных"""
        try:
            conn = sqlite3.connect('data/main.db')
            cursor = conn.cursor()
            
            # Обновляем все таблицы, где есть guild_id
            cursor.execute("UPDATE surveys SET guild_id = ?", (str(ctx.guild.id),))
            cursor.execute("UPDATE levels SET guild_id = ? WHERE guild_id = 'ВАШ_GUILD_ID'", (str(ctx.guild.id),))
            conn.commit()
            
            await ctx.send(f"✅ Все guild_id обновлены на `{ctx.guild.id}`")
        except Exception as e:
            await ctx.send(f"❌ Ошибка: {str(e)}")
        finally:
            conn.close()

async def setup(bot):
    await bot.add_cog(GuildConfig(bot))