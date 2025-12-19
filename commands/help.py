import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Remove default help command if it exists
        self._original_help_command = bot.help_command
        bot.help_command = None

    def cog_unload(self):
        # Restore default help command on unload
        self.bot.help_command = self._original_help_command

    @commands.command(name='help')
    async def help(self, ctx, *, command_name: str = None):
        """
        Shows this help message.
        Usage: 
        ?help - List all commands.
        ?help <command> - Show details for a specific command.
        """
        
        if command_name:
            # Show specific command help
            cmd = self.bot.get_command(command_name)
            if not cmd or cmd.hidden:
                await ctx.send("Command not found.")
                return
            
            embed = discord.Embed(title=f"Help: ?{cmd.name}", description=cmd.help or "No description provided.", color=discord.Color.blue())
            
            # Aliases
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(cmd.aliases), inline=False)
            
            # Syntax (Simple approximation)
            params = []
            for name, param in cmd.clean_params.items():
                if param.default == param.empty:
                    params.append(f"<{name}>")
                else:
                    params.append(f"[{name}]")
            
            syntax = f"?{cmd.name} {' '.join(params)}"
            embed.add_field(name="Usage", value=f"`{syntax}`", inline=False)
            
            await ctx.send(embed=embed)
            
        else:
            # Show all commands
            embed = discord.Embed(title="🤖 Bot Commands", description="Type `?help <command>` for more info.", color=discord.Color.blurple())
            
            cogs = self.bot.cogs
            for cog_name, cog in cogs.items():
                # Filter hidden commands
                cmds = [c for c in cog.get_commands() if not c.hidden]
                if cmds:
                    # Create clickable or just list
                    cmd_list = ", ".join([f"`{c.name}`" for c in cmds])
                    embed.add_field(name=cog_name, value=cmd_list, inline=False)
            
            # Handle commands without cogs (if any)
            uncategorized = [c for c in self.bot.commands if c.cog is None and not c.hidden]
            if uncategorized:
                cmd_list = ", ".join([f"`{c.name}`" for c in uncategorized])
                embed.add_field(name="Uncategorized", value=cmd_list, inline=False)
                
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
