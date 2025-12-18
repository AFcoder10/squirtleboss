import discord
from discord.ext import commands
import os
import sys

OWNER_ID = 688983124868202496

class Reload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.send("You do not have permission to use this command.")
            return False
        return True

    @commands.command(name='reload')
    async def reload(self, ctx, target: str):
        """
        Reloads a specific extension, all extensions, or restarts the bot.
        Usage: 
        !reload all - Reloads all cogs and utils.
        !reload bot - Restarts the bot process.
        !reload utils - Reloads utility modules only.
        !reload <filename> - Reloads a specific cog.
        """
        target = target.lower()

        if target == 'bot':
            await ctx.send("Restarting bot...")
            # Restart the current process
            os.execv(sys.executable, ['python'] + sys.argv)
            return

        # Deep reload utils
        if target == 'utils':
            try:
                # Import here to ensure we get the latest if we reload THIS file too? 
                # Actually standard import is fine if we reload 'utils' prefix which includes utils.reloader
                from utils.reloader import reload_modules
                reloaded = reload_modules()
                await ctx.send(f"Reloaded {len(reloaded)} utility modules: {', '.join(reloaded)}")
            except Exception as e:
                await ctx.send(f"Failed to reload utils: {e}")
            return

        if target == 'all':
            msg = await ctx.send("Reloading all extensions and utils...")
            try:
                # 1. Reload Utils first
                from utils.reloader import reload_modules
                reloaded_utils = reload_modules()
                
                # 2. Reload Cogs
                count = 0
                if os.path.exists('./commands'):
                    for filename in os.listdir('./commands'):
                        if filename.endswith('.py'):
                            ext_name = f'commands.{filename[:-3]}'
                            try:
                                await self.bot.reload_extension(ext_name)
                                count += 1
                            except commands.ExtensionNotLoaded:
                                try:
                                    await self.bot.load_extension(ext_name)
                                    count += 1
                                except Exception as e:
                                    await ctx.send(f"Failed to load {ext_name}: {e}")
                            except Exception as e:
                                await ctx.send(f"Failed to reload {ext_name}: {e}")
                
                await msg.edit(content=f"Reloaded **{len(reloaded_utils)} utils** and **{count} extensions**.")
            except Exception as e:
                await msg.edit(content=f"Error reloading all: {e}")
            return

        # Reload specific file
        # Handle cases like "ping.py", "ping", "commands.ping"
        if target.endswith('.py'):
            target = target[:-3]
        
        if not target.startswith('commands.'):
            ext_name = f'commands.{target}'
        else:
            ext_name = target

        try:
            await self.bot.reload_extension(ext_name)
            await ctx.send(f"Successfully reloaded `{ext_name}`.")
        except commands.ExtensionNotLoaded:
            try:
                # Try loading if not loaded
                await self.bot.load_extension(ext_name)
                await ctx.send(f"Successfully loaded `{ext_name}`.")
            except commands.ExtensionNotFound:
                await ctx.send(f"Extension `{ext_name}` not found.")
            except Exception as e:
                await ctx.send(f"Failed to load `{ext_name}`: {e}")
        except commands.ExtensionNotFound:
            await ctx.send(f"Extension `{ext_name}` not found.")
        except Exception as e:
            await ctx.send(f"Failed to reload `{ext_name}`: {e}")

async def setup(bot):
    await bot.add_cog(Reload(bot))
