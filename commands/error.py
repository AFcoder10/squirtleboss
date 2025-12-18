from discord.ext import commands

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Command not found.", delete_after=5)
            return
        
        # Print other errors to console
        print(f"Error in command {ctx.command}: {error}")
        await ctx.send(f"An error occurred: {error}", delete_after=5)

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
