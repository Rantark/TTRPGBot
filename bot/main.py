"""Main entry point for the D&D 5e Discord bot with Claude as DM."""

import os
import sys
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from bot.dm_engine import DMEngine

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

# Bot setup
PREFIX = os.environ.get("COMMAND_PREFIX", "!")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Cog extensions to load
EXTENSIONS = [
    "bot.cogs.campaign",
    "bot.cogs.character",
    "bot.cogs.gameplay",
    "bot.cogs.combat",
    "bot.cogs.progression",
    "bot.cogs.spells",
    "bot.cogs.utility",
]


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    logger.info(f"Command prefix: {PREFIX}")

    # Initialize the DM engine
    try:
        bot.dm_engine = DMEngine()
        logger.info(f"Claude DM engine initialized (model: {bot.dm_engine.model})")
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

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.playing, name="D&D 5e | !commands")
    )
    logger.info("Bot is ready!")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    """Global error handler for commands."""
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown commands
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`. Check `!commands` for usage.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid argument. Check `!commands` for usage.")
        return
    if isinstance(error, commands.CommandInvokeError):
        logger.exception(f"Command error in {ctx.command}: {error.original}")
        await ctx.send(f"Something went wrong: {type(error.original).__name__}: {error.original}")
        return

    logger.exception(f"Unhandled command error: {error}")
    await ctx.send("An unexpected error occurred. Please try again.")


def main():
    """Run the bot."""
    logger.info("Starting D&D 5e Discord Bot...")
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
