from discord.ext import commands

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Command not found.", delete_after=5)
        # You can add more error handling here if needed

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
