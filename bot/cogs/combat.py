"""Combat system cog: initiative, turn order, turn lock."""

import discord
from discord.ext import commands

from bot.models.campaign import CampaignPhase
from bot.dice import roll_initiative, parse_adv_dis
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

        from bot.models.campaign import CombatMap
        campaign.combat.active = True
        campaign.combat.initiative_order = []
        campaign.combat.current_turn_index = 0
        campaign.combat.round_number = 1
        campaign.combat.combat_map = CombatMap()
        save_campaign(campaign)

        campaign.add_session_log("Combat started!")

        await ctx.send(
            "**COMBAT STARTED!**\n"
            "All players: Roll initiative with `!initiative`\n"
            "DM: Add NPCs/monsters with `!addnpc <name> <initiative_roll>`\n"
            "Once everyone has rolled, DM uses `!begincombat` to set the order and start turns."
        )

    @commands.command(name="initiative")
    async def roll_initiative_cmd(self, ctx: commands.Context, *, args: str = ""):
        """Roll initiative for your character (d20 + DEX modifier).

        Usage: !initiative
        Usage: !initiative adv
        Usage: !initiative dis
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

        # Parse advantage/disadvantage
        _, advantage, disadvantage = parse_adv_dis(args) if args else ("", False, False)

        dex_mod = char.get_modifier("DEX")
        result = roll_initiative(dex_mod, advantage=advantage, disadvantage=disadvantage)

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

    @commands.command(name="map")
    async def show_map(self, ctx: commands.Context):
        """Display the combat map.

        Usage: !map
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat. The map is only available during combat.")
            return

        cmap = campaign.combat.combat_map
        if not cmap.positions:
            await ctx.send(
                "**Combat Map** — *No tokens placed yet.*\n"
                "DM: Use `!place <name> <x> <y>` to place characters on the map."
            )
            return

        rendered = cmap.render()
        await ctx.send(f"**Combat Map — Round {campaign.combat.round_number}**\n```\n{rendered}\n```")

    @commands.command(name="place")
    async def place_token(self, ctx: commands.Context, name: str = "", x: str = "", y: str = "", token: str = ""):
        """DM places a token on the combat map.

        Usage: !place Thorin 3 5
        Usage: !place Goblin1 7 2 G1
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can place tokens on the map.")
            return

        if not name or not x or not y:
            await ctx.send("Usage: `!place <name> <x> <y>` or `!place <name> <x> <y> <token>`")
            return

        try:
            px, py = int(x), int(y)
        except ValueError:
            await ctx.send("Coordinates must be numbers. Usage: `!place Thorin 3 5`")
            return

        cmap = campaign.combat.combat_map
        if px < 0 or px >= cmap.width or py < 0 or py >= cmap.height:
            await ctx.send(f"Out of bounds. Map is {cmap.width}x{cmap.height} (0-{cmap.width-1}, 0-{cmap.height-1}).")
            return

        cmap.place(name, px, py, token)
        save_campaign(campaign)

        tk = cmap.tokens.get(name, name[:2].upper())
        await ctx.send(f"**{name}** (`{tk}`) placed at ({px}, {py}).")

    @commands.command(name="move")
    async def move_token(self, ctx: commands.Context, *, args: str = ""):
        """Move your token on the combat map.

        Usage: !move north 2 (or n/s/e/w/ne/nw/se/sw)
        Usage: !move 3 5 (move to absolute position)
        DM can: !move Goblin1 north 3
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return

        if not args.strip():
            await ctx.send(
                "Usage: `!move <direction> <distance>` or `!move <x> <y>`\n"
                "Directions: `north`/`n`, `south`/`s`, `east`/`e`, `west`/`w`, `ne`, `nw`, `se`, `sw`"
            )
            return

        cmap = campaign.combat.combat_map
        parts = args.strip().split()
        is_dm = self._is_dm(campaign, str(ctx.author.id))

        # Determine who is moving
        char = campaign.get_character(str(ctx.author.id))
        token_name = char.name if char else None

        # DM can specify a name as the first argument
        if is_dm and len(parts) >= 2 and parts[0] in cmap.positions:
            token_name = parts[0]
            parts = parts[1:]
        elif is_dm and len(parts) >= 2:
            # Check case-insensitive
            for pname in cmap.positions:
                if pname.lower() == parts[0].lower():
                    token_name = pname
                    parts = parts[1:]
                    break

        if not token_name or token_name not in cmap.positions:
            await ctx.send("Your character isn't on the map yet. Ask the DM to place you with `!place`.")
            return

        # Direction mapping
        DIRS = {
            "north": (0, -1), "n": (0, -1),
            "south": (0, 1), "s": (0, 1),
            "east": (1, 0), "e": (1, 0),
            "west": (-1, 0), "w": (-1, 0),
            "northeast": (1, -1), "ne": (1, -1),
            "northwest": (-1, -1), "nw": (-1, -1),
            "southeast": (1, 1), "se": (1, 1),
            "southwest": (-1, 1), "sw": (-1, 1),
        }

        # Try directional move
        direction = parts[0].lower()
        if direction in DIRS:
            dx_unit, dy_unit = DIRS[direction]
            distance = 1
            if len(parts) > 1 and parts[1].isdigit():
                distance = int(parts[1])
            dx = dx_unit * distance
            dy = dy_unit * distance
            cmap.move(token_name, dx, dy)
            save_campaign(campaign)
            pos = cmap.positions[token_name]
            await ctx.send(f"**{token_name}** moves {direction} {distance} -> ({pos[0]}, {pos[1]})")
            return

        # Try absolute position
        if len(parts) >= 2 and parts[0].lstrip("-").isdigit() and parts[1].lstrip("-").isdigit():
            new_x, new_y = int(parts[0]), int(parts[1])
            if 0 <= new_x < cmap.width and 0 <= new_y < cmap.height:
                cmap.place(token_name, new_x, new_y)
                save_campaign(campaign)
                await ctx.send(f"**{token_name}** moves to ({new_x}, {new_y})")
                return
            else:
                await ctx.send(f"Out of bounds. Map is {cmap.width}x{cmap.height}.")
                return

        await ctx.send(
            "Invalid move. Use a direction (`north`, `n`, `se`, etc.) or coordinates (`3 5`).\n"
            "Example: `!move north 2` or `!move 3 5`"
        )

    @commands.command(name="mapsize")
    async def map_size(self, ctx: commands.Context, width: int = 0, height: int = 0):
        """DM sets the combat map size.

        Usage: !mapsize 15 12 (15 wide, 12 tall)
        """
        campaign = self._get_campaign(ctx)
        if not campaign or not campaign.combat.active:
            await ctx.send("No active combat.")
            return
        if not self._is_dm(campaign, str(ctx.author.id)):
            await ctx.send("Only the DM can resize the map.")
            return

        if width < 5 or width > 20 or height < 5 or height > 20:
            await ctx.send("Map size must be 5-20 for both width and height.")
            return

        from bot.models.campaign import CombatMap
        campaign.combat.combat_map = CombatMap(width, height)
        save_campaign(campaign)
        await ctx.send(f"Combat map resized to **{width}x{height}**. All tokens cleared.")

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
