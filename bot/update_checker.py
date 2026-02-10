"""
Checks GitHub for new versions and notifies the bot owner
"""

import aiohttp
import asyncio
import discord
from packaging import version
import os

from bot.version import __version__

class UpdateChecker:
    def __init__(self, bot):
        self.bot = bot
        self.github_repo = "Rantark/TTRPGBot"
        self.github_branch = "claude/dnd-discord-bot-e1Rh5"
        self.check_interval = 86400  # 24 hours in seconds
        self.task = None
        self.owner_id = None

    def start(self):
        """Start the update checker task"""
        self.owner_id = os.getenv('BOT_OWNER_ID')

        if not self.owner_id:
            print("[UPDATE CHECKER] No BOT_OWNER_ID set, update notifications disabled")
            return

        self.task = self.bot.loop.create_task(self._check_loop())
        print("[UPDATE CHECKER] Started (checking every 24 hours)")

    def stop(self):
        """Stop the update checker task"""
        if self.task:
            self.task.cancel()

    async def _check_loop(self):
        """Background task that checks for updates every 24 hours"""
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            try:
                update_info = await self.check_for_updates()

                if update_info and update_info['update_available']:
                    await self._notify_owner(update_info)

            except Exception as e:
                print(f"[UPDATE CHECKER] Error: {e}")

            # Wait 24 hours before next check
            await asyncio.sleep(self.check_interval)

    async def check_for_updates(self) -> dict:
        """Check GitHub for newer version"""
        try:
            # Fetch version.py from GitHub
            url = f"https://raw.githubusercontent.com/{self.github_repo}/{self.github_branch}/bot/version.py"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        print(f"[UPDATE CHECKER] Failed to fetch version from GitHub: {response.status}")
                        return None

                    content = await response.text()

            # Parse version from content
            github_version = self._parse_version_from_file(content)

            if not github_version:
                return None

            # Compare versions
            current = version.parse(__version__)
            latest = version.parse(github_version)

            update_available = latest > current

            return {
                'update_available': update_available,
                'current_version': __version__,
                'latest_version': github_version,
                'github_url': f"https://github.com/{self.github_repo}/tree/{self.github_branch}"
            }

        except Exception as e:
            print(f"[UPDATE CHECKER] Error checking for updates: {e}")
            return None

    def _parse_version_from_file(self, content: str) -> str:
        """Extract version string from version.py content"""
        for line in content.split('\n'):
            if line.startswith('__version__'):
                # Extract version from: __version__ = "1.0.0"
                version_str = line.split('=')[1].strip().strip('"').strip("'")
                return version_str
        return None

    async def _notify_owner(self, update_info: dict):
        """Send DM to bot owner about available update"""
        try:
            owner = await self.bot.fetch_user(int(self.owner_id))

            embed = discord.Embed(
                title="TTRPGBot Update Available",
                description="A new version of TTRPGBot is available!",
                color=discord.Color.blue()
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
                name="Update Instructions",
                value=(
                    f"**From Discord:**\n"
                    f"Use `!update` to update automatically\n\n"
                    f"**Manually:**\n"
                    f"1. Run `update.bat` (Windows) or `./update.sh` (Linux/Mac)\n"
                    f"2. Or: `git pull origin {self.github_branch}`\n"
                    f"3. Restart the bot\n\n"
                    f"[View on GitHub]({update_info['github_url']})"
                ),
                inline=False
            )

            await owner.send(embed=embed)
            print(f"[UPDATE CHECKER] Notified owner about update: {update_info['latest_version']}")

        except Exception as e:
            print(f"[UPDATE CHECKER] Failed to notify owner: {e}")
