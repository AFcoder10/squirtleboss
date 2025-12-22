import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define intents
intents = discord.Intents.default()
intents.message_content = True

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

# Initialize bot with prefix
bot = commands.Bot(command_prefix='?', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    
    # Check Database Connection
    import db
    conn = db.get_connection()
    if conn:
        print("✅ Database connected successfully!")
        conn.close()
    else:
        print("❌ Failed to connect to Database!")

async def main():
    async with bot:
        # Load extensions from commands
        if os.path.exists('./commands'):
            for filename in os.listdir('./commands'):
                if filename.endswith('.py'):
                    await bot.load_extension(f'commands.{filename[:-3]}')
                    print(f'Loaded extension: commands.{filename}')

        # Load extensions from admincommands
        if os.path.exists('./admincommands'):
            for filename in os.listdir('./admincommands'):
                if filename.endswith('.py'):
                    await bot.load_extension(f'admincommands.{filename[:-3]}')
                    print(f'Loaded extension: admincommands.{filename}')
        
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN or TOKEN == "your_token_here":
        print("Error: DISCORD_TOKEN not found in .env or is still default.")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            pass
