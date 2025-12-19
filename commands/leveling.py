import discord
from discord.ext import commands
import random
from utils.leveling_handler import update_user_xp, get_user_data, get_rank, get_leaderboard, calculate_xp_for_level, set_levelup_channel, get_levelup_channel

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if not message.guild:
            return

        # Award random XP between 15 and 25
        xp_amount = random.randint(15, 25)
        new_level, leveled_up = update_user_xp(message.guild.id, message.author.id, xp_amount)
        
        if leveled_up:
            channel_id = get_levelup_channel(message.guild.id)
            if channel_id:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(f"Congratulations {message.author.mention}! You have leveled up to level {new_level}!")
            else:
                 # Optional: Send in the same channel if no log channel set, or just don't send anything.
                 # User request says: "send mssg when someone level ups". 
                 # Usually if log channel is not set, we might send in current channel or do nothing.
                 # Given the explicit command to set log channel, maybe default to nothing or current?
                 # Let's stick to only sending if configured, to avoid spam, or maybe send in current channel if not configured?
                 # The user request: "add a admin command ?set_levelup_log (channel) to send mssg when someone level ups"
                 # faster implication: only send if set. But typical bots send in current channel by default.
                 # I'll stick to: only send if channel is set, to avoid annoyance.
                 pass

    @commands.command(aliases=['lvl', 'level'])
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_data = get_user_data(ctx.guild.id, member.id)
        
        if not user_data:
            await ctx.send(f"{member.display_name} has not earned any XP yet.")
            return
            
        rank = get_rank(ctx.guild.id, member.id)
        level = user_data['level']
        xp = user_data['xp']
        next_level_xp = calculate_xp_for_level(level)
        
        # Calculate progress
        # XP for current level start (approximate, to show progress bar correctly)
        # Ideally we'd know the XP required for the PREVIOUS level to show a bar from 0% to 100% of the current level.
        # But our formula is cumulative?
        # create_xp_for_level(level) returns limit for THAT level.
        # So previous level limit is calculate_xp_for_level(level - 1).
        
        prev_level_xp = calculate_xp_for_level(level - 1) if level > 1 else 0
        xp_towards_next = xp - prev_level_xp
        xp_needed_for_next = next_level_xp - prev_level_xp
        
        # Progress bar
        boxes = 10
        ratio = xp_towards_next / xp_needed_for_next if xp_needed_for_next > 0 else 0
        filled = int(ratio * boxes)
        bar = '🟦' * filled + '⬜' * (boxes - filled)
        
        embed = discord.Embed(title=f"Rank - {member.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="XP", value=f"{xp} / {next_level_xp}", inline=False)
        embed.add_field(name="Progress", value=bar, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(aliases=['lb'])
    async def leaderboard(self, ctx):
        leaderboard_data = get_leaderboard(ctx.guild.id)
        
        if not leaderboard_data:
            await ctx.send("No distinct rankings on the leaderboard yet.")
            return
            
        embed = discord.Embed(title=f"Leaderboard - {ctx.guild.name}", color=discord.Color.gold())
        
        description = ""
        for idx, entry in enumerate(leaderboard_data):
            username = f"<@{entry['user_id']}>"
            description += f"**{idx + 1}.** {username} - Level {entry['level']} ({entry['xp']} XP)\n"
            
        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def set_levelup_log(self, ctx, channel: discord.TextChannel):
        set_levelup_channel(ctx.guild.id, channel.id)
        await ctx.send(f"Level-up notifications will now be sent to {channel.mention}")

    @set_levelup_log.error
    async def set_levelup_log_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have permission to use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Please specify a channel. Usage: `?set_levelup_log #channel`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid channel specified.")

async def setup(bot):
    await bot.add_cog(Leveling(bot))
