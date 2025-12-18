import discord
from discord.ext import commands

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Ignore errors if command has its own error handler
        if hasattr(ctx.command, 'on_error'):
            return

        # Ignore errors handled by local cog error handler
        if ctx.cog:
            if ctx.cog._get_overridden_method(ctx.cog.cog_command_error) is not None:
                return

        # Ignore command not found
        if isinstance(error, commands.CommandNotFound):
            return

        # 1. Permission Error
        if isinstance(error, commands.MissingPermissions):
            missing = [perm.replace('_', ' ').replace('guild', '').title() for perm in error.missing_permissions]
            embed = discord.Embed(
                title="❌ Permission Denied",
                description=f"You need the following permissions to use this command:\n`{', '.join(missing)}`",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        # 2. Missing Argument
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="⚠️ Missing Argument",
                description=f"You missed a required argument: `{error.param.name}`.\nUsage: `{ctx.prefix}{ctx.command.signature}`",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        # 3. Bad Argument
        if isinstance(error, commands.BadArgument):
             embed = discord.Embed(
                title="⚠️ Invalid Argument",
                description=f"Invalid argument passed. Please check the command usage.",
                color=discord.Color.orange()
            )
             await ctx.send(embed=embed, delete_after=10)
             return
            
        # 4. Cooldown
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏳ Slow Down",
                description=f"This command is on cooldown. Try again in `{error.retry_after:.2f}s`.",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed, delete_after=5)
            return

        # Default: Print and show generic error
        print(f"Error in command {ctx.command}: {error}")
        embed = discord.Embed(title="Error", description=f"An unexpected error occurred: `{error}`", color=discord.Color.dark_red())
        await ctx.send(embed=embed, delete_after=10)

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
