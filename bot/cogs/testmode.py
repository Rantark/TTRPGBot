"""Test mode cog: quickly spin up a temporary campaign with pre-built characters for testing."""

import discord
from discord.ext import commands

from bot.models.campaign import Campaign, CampaignPhase, GameSystem
from bot.models.character import Character
from bot.models.wod_character import WoDCharacter
from bot.storage import save_campaign, load_campaign, delete_campaign


# ── Pre-built D&D test characters ──────────────────────────────────

def _make_dnd_fighter(owner_id: str, owner_name: str) -> Character:
    """Level 3 Human Fighter — classic melee warrior."""
    c = Character(owner_id, owner_name)
    c.name = "Aldric Ironforge"
    c.gender = "Male"
    c.race = "Human"
    c.char_class = "Fighter"
    c.background = "Soldier"
    c.abilities = {"STR": 16, "DEX": 14, "CON": 15, "INT": 10, "WIS": 12, "CHA": 8}
    c.saving_throw_proficiencies = ["STR", "CON"]
    c.skill_proficiencies = ["Athletics", "Intimidation", "Perception", "Survival"]
    c.armor_proficiencies = ["Light", "Medium", "Heavy", "Shields"]
    c.weapon_proficiencies = ["Simple", "Martial"]
    c.languages = ["Common", "Dwarvish"]
    c.traits = ["Fighting Style: Defense", "Second Wind", "Action Surge"]
    c.features = ["Improved Critical"]
    c.weapons = [
        {"name": "Longsword", "damage": "1d8", "damage_type": "slashing",
         "properties": ["Versatile (1d10)"], "weapon_type": "martial",
         "category": "melee", "finesse": False},
        {"name": "Handaxe", "damage": "1d6", "damage_type": "slashing",
         "properties": ["Light", "Thrown (20/60)"], "weapon_type": "simple",
         "category": "melee", "finesse": False},
    ]
    c.inventory = ["Chain Mail", "Shield", "Handaxe", "Explorer's Pack",
                    {"name": "Rations", "quantity": 5}, "Rope (50 ft)"]
    c.equipped = {"armor": "Chain Mail", "shield": True}
    c.gold = 25
    c.hit_die = 10
    c.backstory = "A veteran soldier who served in the king's army for a decade before setting out on his own."
    c.finalize(starting_level=3)
    return c


def _make_dnd_wizard(owner_id: str, owner_name: str) -> Character:
    """Level 3 High Elf Wizard — arcane spellcaster."""
    c = Character(owner_id, owner_name)
    c.name = "Elara Nightwhisper"
    c.gender = "Female"
    c.race = "Elf"
    c.subrace = "High Elf"
    c.char_class = "Wizard"
    c.background = "Sage"
    c.abilities = {"STR": 8, "DEX": 14, "CON": 13, "INT": 16, "WIS": 12, "CHA": 10}
    c.saving_throw_proficiencies = ["INT", "WIS"]
    c.skill_proficiencies = ["Arcana", "History", "Investigation", "Perception"]
    c.armor_proficiencies = []
    c.weapon_proficiencies = ["Daggers", "Darts", "Slings", "Quarterstaffs", "Light Crossbows"]
    c.languages = ["Common", "Elvish", "Draconic", "Sylvan"]
    c.traits = ["Darkvision", "Fey Ancestry", "Trance", "Arcane Recovery"]
    c.features = ["Evocation Savant", "Sculpt Spells"]
    c.spellcasting_ability = "INT"
    c.cantrips = ["Fire Bolt", "Mage Hand", "Prestidigitation", "Light"]
    c.known_spells = ["Magic Missile", "Shield", "Mage Armor", "Detect Magic",
                      "Thunderwave", "Misty Step", "Scorching Ray", "Web"]
    c.prepared_spells = ["Magic Missile", "Shield", "Mage Armor", "Misty Step", "Scorching Ray"]
    c.weapons = [
        {"name": "Quarterstaff", "damage": "1d6", "damage_type": "bludgeoning",
         "properties": ["Versatile (1d8)"], "weapon_type": "simple",
         "category": "melee", "finesse": False},
    ]
    c.inventory = ["Spellbook", "Component Pouch", "Scholar's Pack",
                    {"name": "Ink (1 oz bottle)", "quantity": 2}, "Parchment (10 sheets)"]
    c.equipped = {"armor": None, "shield": False}
    c.gold = 35
    c.hit_die = 6
    c.backstory = "A scholar from an ancient elven academy, seeking lost magical knowledge."
    c.finalize(starting_level=3)
    return c


def _make_dnd_cleric(owner_id: str, owner_name: str) -> Character:
    """Level 3 Hill Dwarf Cleric — healer and divine caster."""
    c = Character(owner_id, owner_name)
    c.name = "Brom Stonehelm"
    c.gender = "Male"
    c.race = "Dwarf"
    c.subrace = "Hill Dwarf"
    c.char_class = "Cleric"
    c.background = "Acolyte"
    c.abilities = {"STR": 14, "DEX": 10, "CON": 14, "INT": 10, "WIS": 16, "CHA": 12}
    c.saving_throw_proficiencies = ["WIS", "CHA"]
    c.skill_proficiencies = ["Insight", "Medicine", "Religion", "History"]
    c.armor_proficiencies = ["Light", "Medium", "Shields"]
    c.weapon_proficiencies = ["Simple", "Battleaxe", "Handaxe", "Warhammer"]
    c.languages = ["Common", "Dwarvish", "Celestial"]
    c.traits = ["Darkvision", "Dwarven Resilience", "Stonecunning",
                "Dwarven Toughness", "Disciple of Life"]
    c.features = ["Channel Divinity: Turn Undead", "Channel Divinity: Preserve Life"]
    c.spellcasting_ability = "WIS"
    c.cantrips = ["Sacred Flame", "Guidance", "Spare the Dying"]
    c.known_spells = ["Cure Wounds", "Bless", "Healing Word", "Guiding Bolt",
                      "Shield of Faith", "Spiritual Weapon", "Prayer of Healing"]
    c.prepared_spells = ["Cure Wounds", "Bless", "Healing Word", "Guiding Bolt",
                         "Spiritual Weapon"]
    c.weapons = [
        {"name": "Warhammer", "damage": "1d8", "damage_type": "bludgeoning",
         "properties": ["Versatile (1d10)"], "weapon_type": "martial",
         "category": "melee", "finesse": False},
    ]
    c.inventory = ["Scale Mail", "Shield", "Holy Symbol", "Priest's Pack",
                    {"name": "Rations", "quantity": 5}]
    c.equipped = {"armor": "Scale Mail", "shield": True}
    c.gold = 20
    c.hit_die = 8
    c.backstory = "A devout priest of Moradin who left his temple to aid the world above."
    c.finalize(starting_level=3)
    return c


def _make_dnd_rogue(owner_id: str, owner_name: str) -> Character:
    """Level 3 Halfling Rogue — sneaky skill monkey."""
    c = Character(owner_id, owner_name)
    c.name = "Pip Shadowfoot"
    c.gender = "Male"
    c.race = "Halfling"
    c.subrace = "Lightfoot Halfling"
    c.char_class = "Rogue"
    c.background = "Criminal"
    c.abilities = {"STR": 8, "DEX": 16, "CON": 12, "INT": 13, "WIS": 10, "CHA": 14}
    c.saving_throw_proficiencies = ["DEX", "INT"]
    c.skill_proficiencies = ["Acrobatics", "Deception", "Investigation", "Perception",
                              "Sleight of Hand", "Stealth"]
    c.armor_proficiencies = ["Light"]
    c.weapon_proficiencies = ["Simple", "Hand Crossbows", "Longswords", "Rapiers", "Shortswords"]
    c.languages = ["Common", "Halfling", "Thieves' Cant"]
    c.traits = ["Lucky", "Brave", "Halfling Nimbleness", "Naturally Stealthy",
                "Expertise (Stealth, Thieves' Tools)", "Sneak Attack (2d6)",
                "Cunning Action", "Thieves' Cant"]
    c.features = ["Assassinate", "Bonus Proficiencies"]
    c.weapons = [
        {"name": "Rapier", "damage": "1d8", "damage_type": "piercing",
         "properties": ["Finesse"], "weapon_type": "martial",
         "category": "melee", "finesse": True},
        {"name": "Shortbow", "damage": "1d6", "damage_type": "piercing",
         "properties": ["Ammunition (80/320)", "Two-Handed"], "weapon_type": "simple",
         "category": "ranged", "finesse": False},
    ]
    c.inventory = ["Leather Armor", "Thieves' Tools", "Burglar's Pack",
                    {"name": "Dagger", "quantity": 2}, "Crowbar", "Dark Cloak"]
    c.equipped = {"armor": "Leather Armor", "shield": False}
    c.gold = 40
    c.hit_die = 8
    c.speed = 25
    c.backstory = "A former pickpocket from the city streets, now using his skills for bigger scores."
    c.finalize(starting_level=3)
    return c


# ── Pre-built WoD test characters ──────────────────────────────────

def _make_wod_daeva(owner_id: str, owner_name: str) -> WoDCharacter:
    """Daeva Invictus — seductive social vampire."""
    c = WoDCharacter(owner_id, owner_name)
    c.name = "Vivienne LaRoux"
    c.gender = "Female"
    c.concept = "Socialite art dealer who controls the city's elite"
    c.virtue = "Hope"
    c.vice = "Lust"
    c.clan = "Daeva"
    c.covenant = "Invictus"
    c.attributes = {
        "Intelligence": 2, "Wits": 3, "Resolve": 2,
        "Strength": 2, "Dexterity": 3, "Stamina": 2,
        "Presence": 4, "Manipulation": 3, "Composure": 3,
    }
    c.skills = {
        "Academics": 1, "Computer": 0, "Crafts": 2, "Investigation": 1,
        "Medicine": 0, "Occult": 1, "Politics": 2, "Science": 0,
        "Athletics": 1, "Brawl": 0, "Drive": 1, "Firearms": 0,
        "Larceny": 0, "Stealth": 2, "Survival": 0, "Weaponry": 0,
        "Animal Ken": 0, "Empathy": 3, "Expression": 2, "Intimidation": 1,
        "Persuasion": 3, "Socialize": 3, "Streetwise": 1, "Subterfuge": 2,
    }
    c.specialties = {"Persuasion": ["Seduction"], "Socialize": ["High Society"]}
    c.disciplines = {"Majesty": 2, "Celerity": 1}
    c.merits = {"Striking Looks": 2, "Resources": 3, "Status (City)": 2, "Herd": 1}
    c.backstory = "Embraced in the 1920s, she built an empire of influence through art and beauty."
    c.creation_complete = True
    c.calc_derived()
    return c


def _make_wod_gangrel(owner_id: str, owner_name: str) -> WoDCharacter:
    """Gangrel Carthian — feral street vampire."""
    c = WoDCharacter(owner_id, owner_name)
    c.name = "Marcus Hale"
    c.gender = "Male"
    c.concept = "Former biker gang leader, now a nocturnal predator"
    c.virtue = "Fortitude"
    c.vice = "Wrath"
    c.clan = "Gangrel"
    c.covenant = "Carthian Movement"
    c.attributes = {
        "Intelligence": 1, "Wits": 3, "Resolve": 3,
        "Strength": 3, "Dexterity": 3, "Stamina": 4,
        "Presence": 2, "Manipulation": 1, "Composure": 2,
    }
    c.skills = {
        "Academics": 0, "Computer": 0, "Crafts": 1, "Investigation": 0,
        "Medicine": 1, "Occult": 0, "Politics": 0, "Science": 0,
        "Athletics": 3, "Brawl": 3, "Drive": 2, "Firearms": 1,
        "Larceny": 1, "Stealth": 2, "Survival": 3, "Weaponry": 1,
        "Animal Ken": 2, "Empathy": 0, "Expression": 0, "Intimidation": 3,
        "Persuasion": 0, "Socialize": 0, "Streetwise": 2, "Subterfuge": 0,
    }
    c.specialties = {"Brawl": ["Grappling"], "Survival": ["Urban"]}
    c.disciplines = {"Protean": 2, "Resilience": 1}
    c.merits = {"Iron Stamina": 2, "Fighting Style (Boxing)": 2, "Danger Sense": 2}
    c.backstory = "Left for dead in an alley, the Beast claimed him and he never looked back."
    c.creation_complete = True
    c.calc_derived()
    return c


# ── Template maps ──────────────────────────────────────────────────

DND_TEMPLATES = {
    "fighter": ("⚔️ Fighter", _make_dnd_fighter),
    "wizard": ("📖 Wizard", _make_dnd_wizard),
    "cleric": ("⛪ Cleric", _make_dnd_cleric),
    "rogue": ("🗡️ Rogue", _make_dnd_rogue),
}

WOD_TEMPLATES = {
    "daeva": ("🌹 Daeva", _make_wod_daeva),
    "gangrel": ("🐺 Gangrel", _make_wod_gangrel),
}


class TestModeCog(commands.Cog, name="Test Mode"):
    """Commands for quickly spinning up test campaigns with pre-built characters."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track which channels are in test mode
        self._test_channels: set[str] = set()

    def _is_test_mode(self, channel_id: str) -> bool:
        return channel_id in self._test_channels

    @commands.command(name="testmode", aliases=["test"])
    async def testmode(self, ctx: commands.Context, system: str = ""):
        """Start a test campaign with pre-built characters.

        Usage:
          !testmode        — Choose D&D or WoD interactively
          !testmode dnd    — Start D&D test campaign
          !testmode wod    — Start WoD test campaign
        """
        channel_id = str(ctx.channel.id)

        # Check for existing campaign
        existing = load_campaign(channel_id)
        if existing and existing.phase != CampaignPhase.NONE:
            await ctx.send(
                "⚠️ There's already a campaign in this channel.\n"
                "Use `!endtest` to end the test campaign first, or use a different channel."
            )
            return

        # Determine game system
        system = system.lower().strip()
        if system in ("dnd", "dnd5e", "d&d", "dnd5"):
            game_system = "dnd5e"
        elif system in ("wod", "vampire", "vtm", "vtr"):
            game_system = "wod"
        elif system == "":
            # Interactive selection
            import asyncio
            msg = await ctx.send(
                "🧪 **Test Mode — Choose Game System**\n\n"
                "1️⃣ **D&D 5th Edition** — 4 pre-built characters (Fighter, Wizard, Cleric, Rogue)\n"
                "2️⃣ **World of Darkness** — 2 pre-built vampires (Daeva, Gangrel)\n\n"
                "*React to choose*"
            )
            emojis = ["1️⃣", "2️⃣"]
            for emoji in emojis:
                await msg.add_reaction(emoji)

            def check(reaction, user):
                return (
                    user == ctx.author
                    and str(reaction.emoji) in emojis
                    and reaction.message.id == msg.id
                )

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
                game_system = "dnd5e" if str(reaction.emoji) == "1️⃣" else "wod"
            except asyncio.TimeoutError:
                await ctx.send("⏰ Timed out. Use `!testmode dnd` or `!testmode wod` to start.")
                return
        else:
            await ctx.send("Unknown system. Use `!testmode dnd` or `!testmode wod`.")
            return

        # Create the test campaign
        campaign = Campaign(channel_id, str(ctx.guild.id), game_system=game_system)
        campaign.phase = CampaignPhase.ACTIVE
        campaign.dm_id = str(ctx.author.id)
        campaign.name = f"Test Campaign ({game_system.upper()})"
        campaign.description = "Temporary test campaign with pre-built characters."

        # Add all template characters, assigning them to the command user
        user_id = str(ctx.author.id)
        user_name = ctx.author.display_name

        if game_system == "dnd5e":
            templates = DND_TEMPLATES
            # Give the user the fighter, add others as "NPC party members"
            first_key = "fighter"
            first_label, first_fn = templates[first_key]
            char = first_fn(user_id, user_name)
            campaign.add_character(user_id, char)

            # Add the rest as bot-owned NPCs (use fake IDs)
            npc_idx = 0
            for key, (label, fn) in templates.items():
                if key == first_key:
                    continue
                npc_id = f"test_npc_{npc_idx}"
                npc_char = fn(npc_id, f"NPC-{label}")
                campaign.add_character(npc_id, npc_char)
                npc_idx += 1
        else:
            templates = WOD_TEMPLATES
            first_key = "daeva"
            first_label, first_fn = templates[first_key]
            char = first_fn(user_id, user_name)
            campaign.add_character(user_id, char)

            npc_idx = 0
            for key, (label, fn) in templates.items():
                if key == first_key:
                    continue
                npc_id = f"test_npc_{npc_idx}"
                npc_char = fn(npc_id, f"NPC-{label}")
                campaign.add_character(npc_id, npc_char)
                npc_idx += 1

        save_campaign(campaign)
        self._test_channels.add(channel_id)

        # Build the summary embed
        embed = discord.Embed(
            title="🧪 Test Mode Activated",
            description=(
                f"**System:** {game_system.upper()}\n"
                f"**Campaign:** {campaign.name}\n"
                f"**Your character:** {char.name}\n\n"
                "All characters are pre-built and ready to go. "
                "The campaign is in **ACTIVE** phase — you can use all gameplay commands."
            ),
            color=0x00CC66,
        )

        # List all characters
        char_lines = []
        for pid, c in campaign.characters.items():
            owner = "**You**" if pid == user_id else "NPC"
            if game_system == "dnd5e":
                race_display = c.subrace if c.subrace else c.race
                char_lines.append(
                    f"• {c.name} — Lv{c.level} {race_display} {c.char_class} ({owner})"
                )
            else:
                char_lines.append(
                    f"• {c.name} — {c.clan} {c.covenant} ({owner})"
                )
        embed.add_field(name="Party", value="\n".join(char_lines), inline=False)

        embed.add_field(
            name="Quick Commands",
            value=(
                "`!sheet` — View your character sheet\n"
                "`!action <text>` — Do something in-game\n"
                "`!roll <dice>` — Roll dice\n"
                "`!dndedit` / `!wodedit` — Edit character\n"
                "`!testchar <class>` — Switch your character\n"
                "`!endtest` — End this test campaign"
            ),
            inline=False,
        )

        embed.set_footer(text="Test mode — campaign data is saved but intended for testing only")
        await ctx.send(embed=embed)

    @commands.command(name="testchar", aliases=["switchchar"])
    async def testchar(self, ctx: commands.Context, template: str = ""):
        """Switch your test character to a different pre-built template.

        D&D:  !testchar fighter | wizard | cleric | rogue
        WoD:  !testchar daeva | gangrel
        """
        channel_id = str(ctx.channel.id)
        campaign = load_campaign(channel_id)

        if not campaign or campaign.phase != CampaignPhase.ACTIVE:
            await ctx.send("No active campaign. Use `!testmode` to start one.")
            return

        user_id = str(ctx.author.id)
        template = template.lower().strip()

        if campaign.game_system == GameSystem.DND5E:
            templates = DND_TEMPLATES
            options = ", ".join(f"`{k}`" for k in templates)
        else:
            templates = WOD_TEMPLATES
            options = ", ".join(f"`{k}`" for k in templates)

        if template not in templates:
            await ctx.send(f"Choose a template: {options}\nExample: `!testchar fighter`")
            return

        label, fn = templates[template]
        char = fn(user_id, ctx.author.display_name)
        campaign.add_character(user_id, char)
        save_campaign(campaign)

        await ctx.send(f"✅ Switched to **{char.name}** ({label})")

    @commands.command(name="endtest")
    async def endtest(self, ctx: commands.Context):
        """End the test campaign and clean up."""
        channel_id = str(ctx.channel.id)
        campaign = load_campaign(channel_id)

        if not campaign:
            await ctx.send("No campaign to end in this channel.")
            return

        campaign_name = campaign.name
        delete_campaign(channel_id)
        self._test_channels.discard(channel_id)

        embed = discord.Embed(
            title="🧪 Test Mode Ended",
            description=f"**{campaign_name}** has been cleaned up.\nAll test data removed.",
            color=0xFF6600,
        )
        await ctx.send(embed=embed)

    @commands.command(name="testlist")
    async def testlist(self, ctx: commands.Context):
        """Show available test character templates."""
        embed = discord.Embed(title="🧪 Test Character Templates", color=0x00CC66)

        dnd_lines = []
        for key, (label, fn) in DND_TEMPLATES.items():
            char = fn("0", "Preview")
            race_display = char.subrace if char.subrace else char.race
            dnd_lines.append(
                f"{label} `{key}` — {char.name}, Lv{char.level} {race_display}\n"
                f"  HP {char.max_hp} | AC {char.ac} | "
                + " ".join(f"{a}:{char.abilities[a]}" for a in ["STR", "DEX", "CON", "INT", "WIS", "CHA"])
            )
        embed.add_field(name="D&D 5e Templates", value="\n".join(dnd_lines), inline=False)

        wod_lines = []
        for key, (label, fn) in WOD_TEMPLATES.items():
            char = fn("0", "Preview")
            wod_lines.append(
                f"{label} `{key}` — {char.name}, {char.clan} {char.covenant}\n"
                f"  Health {char.health_max} | Willpower {char.willpower_max} | "
                f"Humanity {char.humanity}"
            )
        embed.add_field(name="World of Darkness Templates", value="\n".join(wod_lines), inline=False)

        embed.set_footer(text="Use !testmode to start | !testchar <name> to switch")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TestModeCog(bot))
