import discord
from discord.ext import commands
import typing
import asyncio

class Recreate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='re')
    @commands.has_permissions(manage_channels=True)
    async def re(self, ctx, targets: commands.Greedy[typing.Union[discord.CategoryChannel, discord.TextChannel, discord.VoiceChannel]] = None):
        """
        Deletes and recreates channels or categories.
        Usage: !re [channel/category] ...
        If a category is provided, all channels in it are recreated (requires confirmation).
        Max 10 channels at once unless confirmed.
        """
        if not targets:
            targets = [ctx.channel]
        
        channels_to_recreate = []
        is_category_involved = False

        # Expand inputs
        for target in targets:
            if isinstance(target, discord.CategoryChannel):
                is_category_involved = True
                channels_to_recreate.extend(target.channels)
            else:
                if target not in channels_to_recreate:
                    channels_to_recreate.append(target)
        
        # Remove duplicates
        seen = set()
        channels_to_recreate = [x for x in channels_to_recreate if not (x.id in seen or seen.add(x.id))]

        # Check limits & Confirmation
        limit = 10
        requires_confirmation = is_category_involved or len(channels_to_recreate) > limit

        if requires_confirmation:
            msg = await ctx.send(f"⚠️ You are about to recreate **{len(channels_to_recreate)}** channels. "
                                 f"{'This involves categories.' if is_category_involved else ''}\n"
                                 "This will PERMANENTLY DELETE history. Reply `yes` to confirm.")
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == 'yes'

            try:
                await self.bot.wait_for('message', check=check, timeout=30.0)
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out. Operation cancelled.")
                return
        
        elif len(channels_to_recreate) > limit:
             # Should not happen as logic above catches > limit in requires_confirmation, 
             # but keeping safeguards normally. 
             # Actually, if not category and > limit, we force confirm, so this block is redundant but safe.
             pass

        await ctx.send(f"Recreating {len(channels_to_recreate)} channels...", delete_after=5)

        recreated_count = 0
        
        for target_channel in channels_to_recreate:
            # Save position to restore it
            position = target_channel.position
            new_channel = None

            try:
                # Clone the channel (copies permissions, category, topic, etc.)
                # We explicitly pass the category (even if None) to ensure it's preserved exactly
                new_channel = await target_channel.clone(
                    reason="Channel recreation command",
                    category=target_channel.category
                )
                
                # Delete the old channel
                await target_channel.delete(reason="Channel recreation command")
                
                # Ensure the new channel is at the correct position
                await new_channel.edit(position=position)
                
                # Notify
                if isinstance(new_channel, discord.TextChannel):
                    await new_channel.send("Channel recreated successfully!", delete_after=10)
                
                print(f"Recreated channel: {target_channel.name}")
                recreated_count += 1
                
                # Wait a bit before next one to be slow/safe
                if len(channels_to_recreate) > 1:
                    await asyncio.sleep(2)
                
            except Exception as e:
                # Error handling
                if new_channel and isinstance(new_channel, discord.TextChannel):
                     await new_channel.send(f"Channel recreated but error occurred: {e}", delete_after=10)
                elif not getattr(target_channel, 'deleted', False,):
                     # Try to send to context if original target is still valid 
                     # (and distinct logic if needed, but simple catch-all here)
                     try:
                        if target_channel != ctx.channel:
                             await ctx.send(f"Failed to recreate {target_channel.name}: {e}", delete_after=10)
                     except:
                        pass
                print(f"Recreate error for {target_channel.name}: {e}")

        if recreated_count > 0:
             try:
                 await ctx.send(f"Completed recreation of {recreated_count} channels.", delete_after=10)
             except:
                 pass

async def setup(bot):
    await bot.add_cog(Recreate(bot))
