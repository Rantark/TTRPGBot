"""Balance and API usage tracking commands."""

import discord
from discord.ext import commands

from bot.balance_tracker import BalanceTracker, LOW_BALANCE_THRESHOLD


class BalanceCog(commands.Cog, name="Balance"):
    """Commands for monitoring API balance and usage."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _tracker(self) -> BalanceTracker | None:
        return getattr(self.bot, "balance_tracker", None)

    # ------------------------------------------------------------------
    # Public commands
    # ------------------------------------------------------------------

    @commands.command(name="balance", aliases=["bal", "apicost"])
    async def show_balance(self, ctx: commands.Context):
        """Show current API balance and usage statistics.

        Usage: !balance
        """
        tracker = self._tracker()
        if tracker is None:
            await ctx.send("Balance tracking is not enabled.")
            return

        info = tracker.get_balance_info()

        if info["uninitialized"]:
            await ctx.send(
                "No balance set yet. An admin can run `!setbalance <amount>` to initialize."
            )
            return

        pct = info["pct_remaining"]
        if pct > 50:
            color = discord.Color.green()
        elif pct > 20:
            color = discord.Color.orange()
        else:
            color = discord.Color.red()

        embed = discord.Embed(
            title="API Balance",
            color=color,
        )

        embed.add_field(
            name="Current Balance",
            value=f"**${info['current_balance']:.2f}** / ${info['initial_balance']:.2f}",
            inline=True,
        )
        embed.add_field(
            name="Remaining",
            value=f"**{pct:.1f}%**",
            inline=True,
        )
        embed.add_field(
            name="Total Spent",
            value=f"${info['total_spent']:.4f}",
            inline=True,
        )
        embed.add_field(
            name="Tokens Used",
            value=(
                f"Input:  {info['total_input_tokens']:,}\n"
                f"Output: {info['total_output_tokens']:,}\n"
                f"Total:  {info['total_tokens']:,}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Est. Remaining Requests",
            value=f"~{info['estimated_remaining_requests']:,}",
            inline=True,
        )
        embed.add_field(
            name="Avg Cost / Request",
            value=f"${info['avg_cost_per_request']:.5f}" if info["avg_cost_per_request"] else "N/A",
            inline=True,
        )

        if info["low_balance"]:
            embed.set_footer(text=f"⚠️ Low balance! Consider topping up (threshold: ${LOW_BALANCE_THRESHOLD:.2f})")
        else:
            embed.set_footer(text=f"API calls tracked: {info['session_count']}")

        await ctx.send(embed=embed)

    @commands.command(name="usage")
    async def show_usage(self, ctx: commands.Context, count: int = 10):
        """Show recent API call history.

        Usage: !usage
        Usage: !usage 20
        """
        tracker = self._tracker()
        if tracker is None:
            await ctx.send("Balance tracking is not enabled.")
            return

        count = max(1, min(count, 25))
        sessions = tracker.recent_sessions(count)

        if not sessions:
            await ctx.send("No API calls recorded yet.")
            return

        lines = [f"**Last {len(sessions)} API calls** (newest first)\n"]
        for s in sessions:
            ts = s["ts"][:16].replace("T", " ")  # "2026-03-07 14:22"
            family = s["model"].split("-")[1] if "-" in s["model"] else s["model"]
            lines.append(
                f"`{ts}` — {family} — "
                f"in:{s['in']:,} out:{s['out']:,} — **${s['cost']:.5f}**"
            )

        text = "\n".join(lines)
        if len(text) > 1990:
            text = text[:1990]
        await ctx.send(text)

    # ------------------------------------------------------------------
    # Admin commands
    # ------------------------------------------------------------------

    @commands.command(name="setbalance")
    @commands.has_permissions(administrator=True)
    async def set_balance(self, ctx: commands.Context, amount: float):
        """(Admin) Set the initial API balance.

        Usage: !setbalance 50.00
        """
        tracker = self._tracker()
        if tracker is None:
            await ctx.send("Balance tracking is not enabled.")
            return

        if amount < 0:
            await ctx.send("Amount must be positive.")
            return

        tracker.set_initial_balance(amount)
        info = tracker.get_balance_info()
        await ctx.send(
            f"Balance set to **${amount:.2f}**. "
            f"Current remaining: **${info['current_balance']:.2f}** "
            f"({info['pct_remaining']:.1f}%)"
        )

    @commands.command(name="addfunds")
    @commands.has_permissions(administrator=True)
    async def add_funds(self, ctx: commands.Context, amount: float):
        """(Admin) Add funds to the balance after topping up.

        Usage: !addfunds 25.00
        """
        tracker = self._tracker()
        if tracker is None:
            await ctx.send("Balance tracking is not enabled.")
            return

        if amount <= 0:
            await ctx.send("Amount must be greater than 0.")
            return

        tracker.add_funds(amount)
        info = tracker.get_balance_info()
        await ctx.send(
            f"Added **${amount:.2f}**. "
            f"New balance: **${info['current_balance']:.2f}** "
            f"({info['pct_remaining']:.1f}%)"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BalanceCog(bot))
