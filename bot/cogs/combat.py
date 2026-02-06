"""Combat system cog: initiative, turn order, turn lock."""

import discord
from discord.ext import commands

from bot.models.campaign import CampaignPhase
from bot.dice import roll_initiative
from bot.storage import load_campaign, save_campaign


class CombatCog(commands.Cog, name="Combat"):
    """Commands for managing combat encounters."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_campaign(self, ctx):
        return load_campaign(str(ctx.channel.id))

    def _is_dm(self, campaign, user_id: str) -> bool:
        return campaign.dm_id == user_id

    def _format_initiative(self, campaign) -> str:
        """Format the initiative order for display."""
        if not campaign.combat.initiative_order:
            return "No initiative order set."

        lines = [f"**Initiative Order — Round {campaign.combat.round_number}**"]
        for i, entry in enumerate(campaign.combat.initiative_order):
            marker = " **<<< CURRENT TURN**" if i == campaign.combat.current_turn_index else ""
            lines.append(f"  `{entry['roll']:2d}` — {entry['name']}{marker}")
        return "\n".join(lines)

    @commands.command(name="combatstart")
    async def combat_start(self, ctx: commands.Context):
        """DM starts a combat encounter.

        Usage: !combatstart
        """
        campaign = self._get_campaign(ctx)
        if not campaign or campaign.phase != CampaignPhase.ACTIVE:
            await ctx.send("No active campaign.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can start combat.")
            return
        if campaign.combat.active:
            await ctx.send("Combat is already active! Use `!combatend` to end it first.")
            return

        campaign.combat.active = True
        campaign.combat.initiative_order = []
        campaign.combat.current_turn_index = 0
        campaign.combat.round_number = 1
        save_campaign(campaign)

        campaign.add_session_log("Combat started!")

        await ctx.send(
            "**COMBAT STARTED!**\n"
            "All players: Roll initiative with `!initiative`\n"
            "DM: Add NPCs/monsters with `!addnpc <name> <initiative_roll>`\n"
            "Once everyone has rolled, DM uses `!begincombat` to set the order and start turns."
        )

    @commands.command(name="initiative")
    async def roll_initiative_cmd(self, ctx: commands.Context):
        """Roll initiative for your character (d20 + DEX modifier).

        Usage: !initiative
        """
        campaign = self._get_campaign(ctx)
        if not campaign:
            await ctx.send("No campaign in this channel.")
            return
        if not campaign.combat.active:
            await ctx.send("No combat active. DM starts combat with `!combatstart`.")
            return

        char = campaign.get_character(str(ctx.author.id))
        if not char:
            await ctx.send("You don't have a character.")
            return

        dex_mod = char.get_modifier("DEX")
        result = roll_initiative(dex_mod)

        # Remove existing entry for this player
        campaign.combat.initiative_order = [
            e for e in campaign.combat.initiative_order
            if e.get("player_id") != str(ctx.author.id)
        ]

        campaign.combat.initiative_order.append({
            "name": char.name,
            "roll": result["total"],
            "player_id": str(ctx.author.id),
        })

        save_campaign(campaign)

        await ctx.send(f"**{char.name}** rolls initiative: {result['breakdown']}")

    @commands.command(name="addnpc")
    async def add_npc_initiative(self, ctx: commands.Context, name: str, initiative: int):
        """DM adds an NPC/monster to initiative order.

        Usage: !addnpc Goblin1 14
        Usage: !addnpc "Orc Chieftain" 18
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can add NPCs to initiative.")
            return

        campaign.combat.initiative_order.append({
            "name": name,
            "roll": initiative,
            "player_id": None,  # NPC
        })
        save_campaign(campaign)
        await ctx.send(f"**{name}** added to initiative with roll **{initiative}**.")

    @commands.command(name="removenpc")
    async def remove_npc(self, ctx: commands.Context, *, name: str):
        """DM removes an NPC from initiative.

        Usage: !removenpc Goblin1
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can remove NPCs.")
            return

        before_len = len(campaign.combat.initiative_order)
        campaign.combat.initiative_order = [
            e for e in campaign.combat.initiative_order
            if e["name"].lower() != name.lower()
        ]
        if len(campaign.combat.initiative_order) == before_len:
            await ctx.send(f"No NPC named `{name}` found in initiative.")
            return

        # Fix turn index if needed
        if campaign.combat.current_turn_index >= len(campaign.combat.initiative_order):
            campaign.combat.current_turn_index = 0

        save_campaign(campaign)
        await ctx.send(f"**{name}** removed from initiative.")

    @commands.command(name="begincombat")
    async def begin_combat(self, ctx: commands.Context):
        """DM sorts initiative and starts the first turn.

        Usage: !begincombat
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can begin combat turns.")
            return

        if not campaign.combat.initiative_order:
            await ctx.send("No one has rolled initiative yet!")
            return

        # Sort by initiative (descending)
        campaign.combat.initiative_order.sort(key=lambda e: e["roll"], reverse=True)
        campaign.combat.current_turn_index = 0
        campaign.combat.round_number = 1
        save_campaign(campaign)

        order_display = self._format_initiative(campaign)
        current = campaign.combat.current_turn

        turn_msg = ""
        if current["player_id"]:
            turn_msg = f"\n<@{current['player_id']}>, it's **{current['name']}**'s turn! What do you do?"
        else:
            turn_msg = f"\nDM: It's **{current['name']}**'s turn."

        await ctx.send(f"{order_display}\n{turn_msg}")

    @commands.command(name="turnorder")
    async def turn_order(self, ctx: commands.Context):
        """Display the current initiative order.

        Usage: !turnorder
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        await ctx.send(self._format_initiative(campaign))

    @commands.command(name="next")
    async def next_turn(self, ctx: commands.Context):
        """DM advances to the next turn.

        Usage: !next
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can advance turns.")
            return

        campaign.combat.advance_turn()
        save_campaign(campaign)

        current = campaign.combat.current_turn
        order_display = self._format_initiative(campaign)

        turn_msg = ""
        if current["player_id"]:
            turn_msg = f"\n<@{current['player_id']}>, it's **{current['name']}**'s turn! What do you do?"
        else:
            turn_msg = f"\nDM: It's **{current['name']}**'s turn."

        await ctx.send(f"{order_display}\n{turn_msg}")

    async def pass_turn(self, ctx: commands.Context):
        """Skip your turn in combat (called from gameplay cog's !pass during combat)."""
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return

        current = campaign.combat.current_turn
        if not current:
            await ctx.send("No current turn.")
            return

        player_id = str(ctx.author.id)
        if current["player_id"] != player_id and campaign.dm_id != player_id:
            await ctx.send(f"It's not your turn. Current turn: **{current['name']}**")
            return

        char = campaign.get_character(player_id)
        name = char.name if char else ctx.author.display_name
        campaign.combat.advance_turn()
        save_campaign(campaign)

        next_turn = campaign.combat.current_turn
        turn_msg = ""
        if next_turn["player_id"]:
            turn_msg = f"<@{next_turn['player_id']}>, it's **{next_turn['name']}**'s turn!"
        else:
            turn_msg = f"DM: It's **{next_turn['name']}**'s turn."

        await ctx.send(f"**{name}** passes their turn.\n{turn_msg}")

    @commands.command(name="combatend")
    async def combat_end(self, ctx: commands.Context):
        """DM ends combat.

        Usage: !combatend
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can end combat.")
            return

        rounds = campaign.combat.round_number
        campaign.combat.active = False
        campaign.combat.initiative_order = []
        campaign.combat.current_turn_index = 0
        campaign.combat.round_number = 1
        save_campaign(campaign)

        campaign.add_session_log(f"Combat ended after {rounds} round(s).")

        await ctx.send(f"**Combat has ended** after {rounds} round(s).\nResume roleplay freely!")


async def setup(bot: commands.Bot):
    await bot.add_cog(CombatCog(bot))
