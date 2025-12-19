import discord
from discord.ext import commands
import datetime

class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='avatar', aliases=['av'])
    async def avatar(self, ctx, member: discord.Member = None):
        """
        Displays the avatar of a user.
        Usage: !avatar [user]
        """
        member = member or ctx.author
        embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.blue())
        embed.set_image(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='userinfo', aliases=['uf', 'whois'])
    async def userinfo(self, ctx, member: discord.Member = None):
        """
        Displays information about a user.
        Usage: !userinfo [user]
        """
        member = member or ctx.author
        roles = [role.mention for role in member.roles if role != ctx.guild.default_role]
        roles.reverse()
        
        embed = discord.Embed(title=f"User Info: {member}", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.nick if member.nick else "None", inline=True)
        embed.add_field(name="Created Account", value=discord.utils.format_dt(member.created_at, style='F'), inline=False)
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, style='F'), inline=False)
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "None", inline=False)
        embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
        embed.add_field(name="Bot?", value="Yes" if member.bot else "No", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name='serverinfo', aliases=['sf', 'server'])
    async def serverinfo(self, ctx):
        """
        Displays information about the server.
        Usage: !serverinfo
        """
        guild = ctx.guild
        embed = discord.Embed(title=f"{guild.name} Info", color=discord.Color.gold())
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Created At", value=discord.utils.format_dt(guild.created_at, style='F'), inline=False)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Channels", value=len(guild.channels), inline=True)
        # Count text/voice separately if needed, but total is fine for now
        
        if guild.description:
            embed.add_field(name="Description", value=guild.description, inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Info(bot))
