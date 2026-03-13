"""Main entry point for the D&D 5e Discord bot with Claude as DM."""

import os
import sys
import logging
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot.dm_engine import DMEngine
from bot.balance_tracker import BalanceTracker
from bot.version import __version__
from bot.update_checker import UpdateChecker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("dnd-bot")

# Validate required env vars
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN environment variable is required. See .env.example")
    sys.exit(1)
if not ANTHROPIC_API_KEY:
    logger.error("ANTHROPIC_API_KEY environment variable is required. See .env.example")
    sys.exit(1)

# Exit codes for wrapper script
EXIT_RESTART = 42
EXIT_UPDATE = 43

# Bot setup
PREFIX = os.environ.get("COMMAND_PREFIX", "!")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Initialize update checker
update_checker = UpdateChecker(bot)

# Cog extensions to load
EXTENSIONS = [
    "bot.cogs.campaign",
    "bot.cogs.character",
    "bot.cogs.wod_character",
    "bot.cogs.gameplay",
    "bot.cogs.combat",
    "bot.cogs.progression",
    "bot.cogs.spells",
    "bot.cogs.utility",
    "bot.cogs.info",
    "bot.cogs.balance",
]


async def shutdown(exit_code=0):
    """Gracefully shutdown the bot with specified exit code."""
    print(f"\n[SHUTDOWN] Shutting down with exit code {exit_code}...")

    print("[SHUTDOWN] Closing bot connection...")
    await bot.close()

    print("[SHUTDOWN] Shutdown complete.")
    sys.exit(exit_code)


@bot.event
async def on_ready():
    print(f'{"=" * 42}')
    print(f'  TTRPGBot v{__version__}')
    print(f'{"=" * 42}')
    print(f'  Logged in as: {bot.user.name}')
    print(f'  Bot ID: {bot.user.id}')
    print(f'  Servers: {len(bot.guilds)}')
    print(f'{"=" * 42}')

    # Initialize balance tracker and DM engine
    try:
        bot.balance_tracker = BalanceTracker()
        bot.dm_engine = DMEngine(balance_tracker=bot.balance_tracker)
        logger.info(f"Claude DM engine initialized (model: {bot.dm_engine.model})")
        logger.info(f"Balance tracker initialized (balance: ${bot.balance_tracker.current_balance:.2f})")
    except ValueError as e:
        logger.error(f"Failed to initialize DM engine: {e}")
        sys.exit(1)

    # Load cog extensions
    for ext in EXTENSIONS:
        try:
            await bot.load_extension(ext)
            logger.info(f"Loaded extension: {ext}")
        except Exception as e:
            logger.error(f"Failed to load extension {ext}: {e}")

    # Set bot status to show version
    await bot.change_presence(
        activity=discord.Game(name=f"D&D 5e | !commands | v{__version__}")
    )

    # Start update checker
    update_checker.start()

    print(f'  Bot is ready!')
    print(f'  Update checker: Running')
    print(f'{"=" * 42}\n')


@bot.event
async def on_command_error(ctx, error):
    """Global error handler — sends full error details to Discord."""
    import traceback

    # Ignore command not found
    if isinstance(error, commands.CommandNotFound):
        return

    # Ignore check failures (permissions etc) — send friendly message
    if isinstance(error, commands.CheckFailure):
        await ctx.send(f"❌ You don't have permission to use that command.")
        return

    # Missing required argument
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
        return

    # Get the original exception if wrapped
    original = getattr(error, 'original', error)

    # Format full traceback
    tb = "".join(traceback.format_exception(type(original), original, original.__traceback__))

    # Log it
    logger.error(f"Command error in {ctx.command}: {error}")

    # Send to Discord (truncate if too long for Discord's 2000 char limit)
    error_msg = (
        f"❌ **Error in `!{ctx.command}`**\n"
        f"```\n{tb[-1800:] if len(tb) > 1800 else tb}\n```"
    )

    try:
        await ctx.send(error_msg)
    except discord.Forbidden:
        # Can't send in channel — try DM to command author
        try:
            await ctx.author.send(error_msg)
        except Exception:
            pass


def main():
    """Run the bot."""
    logger.info(f"Starting TTRPGBot v{__version__}...")
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
