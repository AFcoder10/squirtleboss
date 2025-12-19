import discord
from discord.ext import commands
import typing

class Purge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='purge', hidden=True)
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, arg1: typing.Optional[str] = None, arg2: typing.Optional[int] = None):
        """
        Purge messages from the channel.
        Usage:
        ?purge <amount> - Delete the last <amount> messages.
        ?purge all - Delete all messages in the channel.
        ?purge @user <amount> - Delete up to <amount> messages from @user.
        """
        if arg1 is None:
            await ctx.send("Usage: ?purge <amount> | ?purge all | ?purge @user [amount]", delete_after=3)
            return

        limit = None
        check = None

        # Logic to determine mode
        # Case 1: !purge all
        if arg1.lower() == 'all':
            limit = None # All messages
        
        # Case 2: !purge <amount> (e.g. !purge 5)
        elif arg1.isdigit():
            limit = int(arg1) + 1 # Include command message

        # Case 3: !purge @user <amount>
        # We need to manually convert the user string
        else:
            try:
                converter = commands.MemberConverter()
                member = await converter.convert(ctx, arg1)
                
                # Check for amount in arg2
                if arg2 is None:
                    # Default scan limit if not provided
                    scan_limit = 100 
                else:
                    scan_limit = arg2
                
                limit = scan_limit
                check = lambda m: m.author.id == member.id
            except commands.BadArgument:
                await ctx.send(f"Invalid argument: {arg1}. Expected 'all', a number, or a user.", delete_after=3)
                return

        # Perform the purge
        kwargs = {}
        if limit is not None:
            kwargs['limit'] = limit
        if check is not None:
            kwargs['check'] = check
            
        try:
            deleted = await ctx.channel.purge(**kwargs)
            await ctx.send(f"Purged {len(deleted) - 1 if check is None and limit else len(deleted)} messages.", delete_after=3)
        except Exception as e:
            await ctx.send(f"Failed to purge: {e}", delete_after=5)
            print(f"Purge error: {e}")

async def setup(bot):
    await bot.add_cog(Purge(bot))
