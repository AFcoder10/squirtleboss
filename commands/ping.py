import discord
from discord.ext import commands

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        
        # Color coding
        if latency < 100:
            color = discord.Color.green()
            status = "Excellent"
        elif latency < 200:
            color = discord.Color.gold()
            status = "Good"
        else:
            color = discord.Color.red()
            status = "Bad"
            
        embed = discord.Embed(title="🏓 Pong!", color=color)
        embed.add_field(name="Latency", value=f"**{latency}ms**", inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Ping(bot))
