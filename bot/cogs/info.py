"""
Bot information and control commands
"""

import discord
from discord.ext import commands
import platform
import psutil
import os
import asyncio
from datetime import datetime

from bot.version import __version__, get_version_info, RELEASE_NOTES
from bot.update_checker import UpdateChecker
from bot.storage import list_campaigns


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Pong! Shows bot latency and version."""
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="Pong!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Latency",
            value=f"`{latency}ms`",
            inline=True
        )

        embed.add_field(
            name="Version",
            value=f"`v{__version__}`",
            inline=True
        )

        embed.add_field(
            name="Status",
            value="Online",
            inline=True
        )

        await ctx.send(embed=embed)

    @commands.command(name='version', aliases=['v', 'ver'])
    async def version(self, ctx):
        """Show detailed version information and release notes."""
        version_info = get_version_info()

        embed = discord.Embed(
            title=f"TTRPGBot v{version_info['version']}",
            description="D&D 5e Discord Bot with Claude AI Dungeon Master",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Version",
            value=f"`{version_info['version']}`",
            inline=True
        )

        embed.add_field(
            name="Python",
            value=f"`{platform.python_version()}`",
            inline=True
        )

        embed.add_field(
            name="Discord.py",
            value=f"`{discord.__version__}`",
            inline=True
        )

        embed.add_field(
            name="Release Notes",
            value=RELEASE_NOTES[:1024],
            inline=False
        )

        embed.set_footer(text="https://github.com/Rantark/TTRPGBot")

        await ctx.send(embed=embed)

    @commands.command(name='botinfo', aliases=['about', 'info'])
    async def show_bot_info(self, ctx):
        """Show detailed bot information and statistics."""
        uptime = datetime.utcnow() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024

        campaign_count = len(list_campaigns())

        embed = discord.Embed(
            title="TTRPGBot Information",
            description="D&D 5e with Claude AI as your Dungeon Master",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="Version",
            value=f"`v{__version__}`",
            inline=True
        )

        embed.add_field(
            name="Servers",
            value=f"`{len(self.bot.guilds)}`",
            inline=True
        )

        embed.add_field(
            name="Saved Campaigns",
            value=f"`{campaign_count}`",
            inline=True
        )

        embed.add_field(
            name="Uptime",
            value=f"`{days}d {hours}h {minutes}m`",
            inline=True
        )

        embed.add_field(
            name="Memory Usage",
            value=f"`{memory_usage:.2f} MB`",
            inline=True
        )

        embed.add_field(
            name="Latency",
            value=f"`{round(self.bot.latency * 1000)}ms`",
            inline=True
        )

        embed.add_field(
            name="Useful Commands",
            value=(
                "`!commands` - Show all commands\n"
                "`!newcampaign` - Start a campaign\n"
                "`!createchar` - Create a character\n"
                "`!version` - Version info\n"
                "`!ping` - Check bot status"
            ),
            inline=False
        )

        embed.set_footer(
            text="Created by Rantark | Powered by Claude AI",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )

        await ctx.send(embed=embed)

    @commands.command(name='checkupdate', aliases=['updatecheck'])
    @commands.has_permissions(administrator=True)
    async def check_update(self, ctx):
        """(Admin only) Manually check for updates."""
        await ctx.send("Checking for updates...")

        checker = UpdateChecker(self.bot)
        update_info = await checker.check_for_updates()

        if not update_info:
            return await ctx.send("Failed to check for updates.")

        if update_info['update_available']:
            embed = discord.Embed(
                title="Update Available!",
                description=f"Version `{update_info['latest_version']}` is now available.",
                color=discord.Color.gold()
            )

            embed.add_field(
                name="Current Version",
                value=f"`{update_info['current_version']}`",
                inline=True
            )

            embed.add_field(
                name="Latest Version",
                value=f"`{update_info['latest_version']}`",
                inline=True
            )

            embed.add_field(
                name="How to Update",
                value=(
                    "**From Discord:** `!update`\n"
                    "**Windows:** Run `update.bat`\n"
                    "**Linux/Mac:** Run `./update.sh`\n"
                    "**Manual:** `git pull origin claude/dnd-discord-bot-e1Rh5`"
                ),
                inline=False
            )

            await ctx.send(embed=embed)
        else:
            await ctx.send(f"You're running the latest version (`{update_info['current_version']}`)!")

    @commands.command(name='restart')
    @commands.has_permissions(administrator=True)
    async def restart_bot(self, ctx):
        """(Admin only) Restart the bot."""
        if not os.path.exists('.wrapper_active'):
            embed = discord.Embed(
                title="Cannot Restart",
                description="The bot is not running with the start script.",
                color=discord.Color.red()
            )

            embed.add_field(
                name="How to Enable Restarts",
                value=(
                    "**Windows:** Stop the bot and run `start.bat`\n"
                    "**Linux/Mac:** Stop the bot and run `./start.sh`\n\n"
                    "Then `!restart` will work."
                ),
                inline=False
            )

            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="Restarting Bot",
            description="The bot will restart in a moment...",
            color=discord.Color.blue()
        )

        await ctx.send(embed=embed)

        print(f"\n[RESTART] Restart requested by {ctx.author} ({ctx.author.id})")

        from bot.main import shutdown, EXIT_RESTART
        asyncio.create_task(shutdown(EXIT_RESTART))

    @commands.command(name='update')
    @commands.has_permissions(administrator=True)
    async def update_bot(self, ctx):
        """(Admin only) Update the bot from GitHub and restart."""
        if not os.path.exists('.wrapper_active'):
            embed = discord.Embed(
                title="Cannot Update",
                description="The bot is not running with the start script.",
                color=discord.Color.red()
            )

            embed.add_field(
                name="How to Enable Updates",
                value=(
                    "**Windows:** Stop the bot and run `start.bat`\n"
                    "**Linux/Mac:** Stop the bot and run `./start.sh`\n\n"
                    "Then `!update` will work."
                ),
                inline=False
            )

            return await ctx.send(embed=embed)

        await ctx.send("Checking for updates...")

        checker = UpdateChecker(self.bot)
        update_info = await checker.check_for_updates()

        if not update_info:
            return await ctx.send("Failed to check for updates. Try again later.")

        if not update_info['update_available']:
            embed = discord.Embed(
                title="Already Up to Date",
                description=f"The bot is already running the latest version (`{update_info['current_version']}`).",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Force Restart?",
                value="Use `!restart` to restart without updating.",
                inline=False
            )

            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="Updating Bot",
            description=f"Updating from `{update_info['current_version']}` to `{update_info['latest_version']}`",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Steps",
            value=(
                "1. Pulling latest code from GitHub\n"
                "2. Installing dependencies\n"
                "3. Restarting bot\n\n"
                "*This will take 10-30 seconds*"
            ),
            inline=False
        )

        await ctx.send(embed=embed)

        print(f"\n[UPDATE] Update requested by {ctx.author} ({ctx.author.id})")
        print(f"[UPDATE] Current: {update_info['current_version']} -> Latest: {update_info['latest_version']}")

        from bot.main import shutdown, EXIT_UPDATE
        asyncio.create_task(shutdown(EXIT_UPDATE))

    @commands.command(name='shutdown', aliases=['stop'])
    @commands.has_permissions(administrator=True)
    async def shutdown_bot(self, ctx):
        """(Admin only) Shut down the bot completely."""
        embed = discord.Embed(
            title="Shutting Down",
            description="The bot is shutting down. Goodbye!",
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)

        print(f"\n[SHUTDOWN] Shutdown requested by {ctx.author} ({ctx.author.id})")

        from bot.main import shutdown
        asyncio.create_task(shutdown(0))


async def setup(bot):
    await bot.add_cog(Info(bot))
