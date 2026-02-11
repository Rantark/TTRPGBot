# D&D 5e Discord Bot — AI Dungeon Master

A production-ready Discord bot for playing **Dungeons & Dragons 5th Edition** where **Claude** (via the Anthropic API) serves as the Dungeon Master. Full interactive character creation, dice rolling, combat management, RP scene coordination, and AI-driven storytelling — all inside Discord.

Claude handles **all** narration, NPC dialogue, world-building, and rules adjudication. No pre-programmed responses. Every game is unique.

---

## Table of Contents

- [Features at a Glance](#features-at-a-glance)
- [Setup Guide (Windows)](#setup-guide-windows)
- [Setup Guide (Mac / Linux)](#setup-guide-mac--linux)
- [Discord Bot Setup](#discord-bot-setup)
- [Running the Bot](#running-the-bot)
- [Deploying to Railway](#deploying-to-railway)
- [How a Game Works](#how-a-game-works)
- [Command Reference](#command-reference)
  - [Campaign Management](#campaign-management)
  - [Character Creation & Sheets](#character-creation--sheets)
  - [Gameplay (RP Scenes)](#gameplay-rp-scenes)
  - [Dice & Rolls](#dice--rolls)
  - [Combat & Tactical Map](#combat--tactical-map)
  - [Progression & Resources](#progression--resources)
  - [Spells & Spellcasting](#spells--spellcasting)
  - [Utility](#utility)
  - [Bot Info & Admin](#bot-info--admin)
- [Character Creation Walkthrough](#character-creation-walkthrough)
- [RP Scene Coordination](#rp-scene-coordination)
- [Combat System & Tactical Map](#combat-system--tactical-map)
- [Inventory & Equipment](#inventory--equipment)
- [Armor & AC System](#armor--ac-system)
- [Consumables](#consumables)
- [Spell System](#spell-system)
- [Rest & Hit Dice](#rest--hit-dice)
- [Death Saves & Unconscious](#death-saves--unconscious)
- [Game Threads](#game-threads)
- [DM Tools & Action Tags](#dm-tools--action-tags)
- [Advantage & Disadvantage](#advantage--disadvantage)
- [Quick Stat Commands](#quick-stat-commands)
- [Fuzzy Matching & Error Messages](#fuzzy-matching--error-messages)
- [Auto-Update & Restart System](#auto-update--restart-system)
- [Prompt Caching (Cost Savings)](#prompt-caching-cost-savings)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [FAQ](#faq)

---

## Features at a Glance

- **AI Dungeon Master** — Claude narrates the story, roleplays NPCs, manages encounters, and adjudicates rules
- **Full D&D 5e Character Creation** — All PHB races (with subraces), all 12 classes, 13 backgrounds, 3 ability score methods (roll, standard array, point buy), gender selection, starting equipment, weapon selection, spell/cantrip selection for casters, backstory. **Private DM-based flow** so multiple players can create simultaneously with step-by-step help text
- **Campaign System** — Pitch/vote on concepts, `!suggestcampaign` for AI-generated ideas, setup phase for character creation, game threads to keep campaigns organized
- **RP Scene Coordination** — Player actions are queued and bundled so the DM responds to everyone at once (no overlapping storylines)
- **Combat System** — Initiative tracking, turn order, turn locking, NPC management, ASCII tactical map
- **Spell System** — Track spell slots, known/prepared spells, cantrips, and casting (full/half/pact casters)
- **DM Tools** — `!dm` narration, `!rewind` to undo DM mistakes, `!loot`/`!giveall` for item distribution, action tags for automatic state updates, DM whispers
- **Full Dice Engine** — Standard notation (d20, 2d6+3), ability checks, saving throws, attack rolls — all with `adv`/`dis` keyword support for advantage/disadvantage
- **Progression** — Short/long rest, HP management, XP tracking, level up with HP rolls, inspiration, death saves, feats, stat modifiers
- **Quick Stat Commands** — Instant views for AC, ability scores, skills, saves, and weapons (`!ac`, `!stats`, `!skills`, `!saves`, `!weapons`)
- **Inventory & Loot System** — Gold tracking, item stacking, `!give` items between players, `!use` consumables with auto-effects (healing potions), `!equip` armor/shields with AC recalculation, `[LOOT:]` tags for automatic inventory updates from Claude
- **Fuzzy Matching** — Mistype a skill or ability? The bot suggests the closest match ("Did you mean Perception?")
- **Undo System** — Cancel pending RP actions with `!undo`, DM can `!rewind` to undo AI mistakes
- **Utility** — AI recaps, investigation clue tracker, NPC journal, private DM whispers
- **`!ask` Command** — Ask the DM rules questions without advancing the story
- **Game Threads** — Each campaign gets its own Discord thread to keep gameplay organized and separate from other chat
- **`!commands` via DM** — Help text is sent to your DMs to keep game chat clean
- **Prompt Caching** — Anthropic prompt caching reduces API costs by up to 90% on repeat calls
- **Auto-Update System** — Background update checker (every 24 hours), `!update` to pull from GitHub and restart, `!restart`/`!shutdown` owner commands, version tracking
- **Persistent Storage** — Campaigns save to JSON files, survive bot restarts
- **Async-Friendly** — Designed for play-by-post (3-6 players responding over hours or days)

---

## Setup Guide (Windows)

### 1. Install Python

Download Python 3.8+ from [python.org](https://www.python.org/downloads/). During install, **check "Add Python to PATH"**.

### 2. Clone or download the repository

```cmd
git clone https://github.com/YOUR_USERNAME/TTRPGBot.git
cd TTRPGBot
```

Or download the ZIP and extract it, then open a Command Prompt in that folder.

### 3. Install dependencies

```cmd
pip install -r requirements.txt
```

### 4. Create your config file

```cmd
copy .env.example .env
```

Open `.env` in Notepad and fill in your tokens:

```
DISCORD_TOKEN=paste_your_discord_bot_token_here
ANTHROPIC_API_KEY=paste_your_anthropic_api_key_here
```

### 5. Run the bot

```cmd
python -m bot.main
```

You should see:

```
2026-02-06 12:00:00 [INFO] dnd-bot: Logged in as YourBot#1234 (ID: ...)
2026-02-06 12:00:00 [INFO] dnd-bot: Claude DM engine initialized (model: claude-sonnet-4-20250514)
2026-02-06 12:00:00 [INFO] dnd-bot: Bot is ready!
```

Leave the Command Prompt window open — the bot runs as long as the window is open.

---

## Setup Guide (Mac / Linux)

```bash
git clone https://github.com/YOUR_USERNAME/TTRPGBot.git
cd TTRPGBot
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your tokens (nano .env, vim .env, etc.)
python -m bot.main
```

---

## Discord Bot Setup

If you don't have a Discord bot yet:

### 1. Create the Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application**, give it a name
3. Go to the **Bot** tab, click **Add Bot**
4. Copy the **Token** — paste it as `DISCORD_TOKEN` in your `.env`

### 2. Enable Required Intents

In the **Bot** tab, scroll down to **Privileged Gateway Intents** and enable:

- **MESSAGE CONTENT INTENT** (required — the bot reads command messages)
- **SERVER MEMBERS INTENT** (required — the bot needs to see who's in the server)

### 3. Invite the Bot to Your Server

1. Go to the **OAuth2 > URL Generator** tab
2. Under **Scopes**, check `bot`
3. Under **Bot Permissions**, check:
   - Send Messages
   - Send Messages in Threads
   - Create Public Threads
   - Manage Threads
   - Read Message History
   - Embed Links
   - Use External Emojis
   - Add Reactions

   **Thread permissions are required** — the bot creates a Discord thread for each campaign when `!startcampaign` is used. If thread permissions are missing, the bot will fall back to playing in the main channel instead.
4. Copy the generated URL and open it in your browser
5. Select your server and authorize

### 4. Get Your Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create an API key
3. Paste it as `ANTHROPIC_API_KEY` in your `.env`

---

## Running the Bot

**Basic start (no restart/update support):**

```cmd
python -m bot.main
```

**With restart/update support (recommended):**

```cmd
# Windows
start.bat

# Linux/Mac
chmod +x start.sh update.sh
./start.sh
```

The wrapper scripts enable `!restart`, `!update`, and `!shutdown` commands from Discord. They create a `.wrapper_active` marker file so the bot knows it can restart itself.

The bot will appear online in your Discord server with the status **"Playing D&D 5e | !commands | v1.0.0"**.

Type `!commands` in any channel to see the category menu.

---

## Deploying to Railway

The included `Procfile` works with [Railway.app](https://railway.app/) out of the box:

1. Push the repo to GitHub
2. Connect it to Railway
3. Add environment variables: `DISCORD_TOKEN` and `ANTHROPIC_API_KEY`
4. Deploy — Railway will run `python -m bot.main` automatically

---

## How a Game Works

Here's the typical flow of a session:

### Phase 1: Campaign Setup

```
DM:     !newcampaign Curse of the Crimson Keep
Bot:    Campaign Created: Curse of the Crimson Keep
        DM: @DungeonMaster
        Phase: Setup — Players can now create characters with !createchar
```

Or use the pitch/vote system:

```
DM:     !newcampaign
Player: !pitch Dragon's Bane | A quest to slay an ancient red dragon
Player: !pitch The Lost City | Explore ruins beneath the desert
DM:     !selectpitch 1
```

Or let Claude suggest ideas:

```
DM:     !suggestcampaign
Bot:    What kind of campaign? React: 1️⃣ Combat | 2️⃣ Roleplay | 3️⃣ Mystery | 4️⃣ Exploration | 5️⃣ Surprise Me
DM:     [reacts with 2️⃣]
Bot:    [Claude generates 3 campaign pitches focused on roleplay]
        React 1️⃣/2️⃣/3️⃣ to select, or !newcampaign to create your own.
DM:     [reacts with 1️⃣]
Bot:    Campaign Created: The Masquerade of Mirrors
```

**Optional:** Set a starting level if you want players to begin at a higher level:

```
DM:     !setlevel 3
Bot:    Starting level set to 3. New characters will begin at level 3.
```

### Phase 2: Character Creation

Each player runs `!createchar` in the server channel. The bot sends them a **DM** with the interactive creation prompts — keeping the process private so multiple players can create characters simultaneously without spoilers. See [Character Creation Walkthrough](#character-creation-walkthrough) below.

### Phase 3: Adventure Begins

```
DM:     !startcampaign
Bot:    Campaign has begun! All gameplay will happen in #🎲-Curse-of-the-Crimson-Keep
        [Claude generates an epic opening narration in the new game thread]
```

The bot creates a **Discord thread** for the campaign. All gameplay (`!action`, `!roll`, etc.) happens in the thread, keeping the main channel clean. When the campaign ends, the thread is archived.

### Phase 4: Play

Players submit actions, and after everyone has acted (or passed), Claude narrates the results:

```
Player1: !action I search the bookshelf for hidden compartments
Player2: !ic "Does anyone else smell smoke?"
Player3: !pass
Bot:     [Claude responds to all actions in one cohesive scene]
```

### Phase 5: Combat (when it happens)

```
DM:      !combatstart
Players: !initiative
DM:      !addnpc Goblin1 14
DM:      !begincombat
Bot:     [Shows initiative order, announces first turn]
```

---

## Command Reference

Type `!commands` in Discord to see these categories, or `!commands <category>` for details. Help text is sent via **DM** to keep game chat clean (falls back to channel if DMs are disabled).

### Campaign Management

| Command | Who | Description |
|---|---|---|
| `!newcampaign [name]` | Anyone | Create a new campaign (you become the DM) |
| `!suggestcampaign` | Anyone | Ask Claude to suggest campaign ideas (react to select) |
| `!pitch <title> \| <desc>` | Anyone | Propose a campaign concept |
| `!pitches` | Anyone | View all proposed pitches |
| `!vote <#>` | Anyone | Vote for a pitch |
| `!selectpitch <#>` | DM | Select a pitch and move to setup phase |
| `!setlevel <level>` | DM | Set starting level for new characters (1-20) |
| `!loot @player <item>` | DM | Give item/gold to a player's inventory |
| `!giveall <item>` | DM | Give item/gold to all players |
| `!startcampaign` | DM | Begin the adventure — creates a game thread |
| `!endcampaign` | DM | End the campaign — archives the game thread |
| `!campaigninfo` | Anyone | View campaign status and player list |

### Character Creation & Sheets

| Command | Description |
|---|---|
| `!createchar` | Start character creation (sent to your DMs for privacy) |
| `!cc <choice>` | Make a choice during creation (use in DMs) |
| `!deletechar` | Delete your character and start over |
| `!sheet` | View your full character sheet |
| `!sheet @player` | View another player's character sheet |
| `!ac` | View your AC breakdown |
| `!stats` | View your ability scores and modifiers |
| `!skills` | View all skill modifiers (with proficiency markers) |
| `!saves` | View saving throw modifiers |
| `!weapons` | View your weapons and attack bonuses |
| `!equipment` | View your inventory/gear (aliases: `!inv`, `!inventory`) |
| `!equipment add <item>` | Add an item to your inventory |
| `!equipment remove <item or #>` | Remove an item by name or number |
| `!gold` | View your gold |
| `!gold +50` / `!gold -10` | Adjust your gold (DM can target: `!gold @player +50`) |
| `!give @player <item>` | Give an item or gold to another player |
| `!use <item>` | Use a consumable (auto-effects for healing potions, antitoxin) |
| `!equip <armor/shield>` | Equip armor or shield (recalculates AC) |
| `!equip none` | Remove armor; `!equip no shield` to remove shield |
| `!backstory` | View your character's backstory |
| `!backstory <text>` | Set or update your backstory |

### Gameplay (RP Scenes)

During non-combat play, actions are **queued** until all players have submitted an action or passed. Then Claude responds to everyone at once in a single cohesive scene.

| Command | Description |
|---|---|
| `!action <desc>` | Describe what your character does *(queued)* |
| `!ic <dialogue>` | Speak in character *(queued)* |
| `!emote <action>` | Describe expressions or body language *(queued)* |
| `!look` | Ask the DM to describe the current scene *(queued)* |
| `!inspect <target>` | Examine something closely *(queued)* |
| `!talk <NPC>` | Speak to an NPC — Claude roleplays them *(queued)* |
| `!pass` | Do nothing this round |
| `!undo` | Cancel your pending action before the round resolves |
| `!pending` | See who hasn't acted yet |
| `!resolve` | *(DM)* Force the round to resolve early |
| `!dm <prompt>` | *(DM)* Prompt Claude to narrate a scene or event |
| `!dm-whisper @player <msg>` | *(DM)* Send a private message to a player via DM |
| `!ask <question>` | Ask the DM a rules question *(does NOT advance the story)* |
| `!rewind [prompt]` | *(DM)* Undo the last AI response; optional re-prompt |
| `!ooc <message>` | Out-of-character chat *(not queued, DM doesn't respond)* |

### Dice & Rolls

All dice commands support **advantage** and **disadvantage** — just add `adv` or `dis` at the end.

| Command | Example | Description |
|---|---|---|
| `!roll <notation> [adv\|dis]` | `!roll 2d6+3` | Roll any dice (d20, 4d6, d8+2, etc.) |
| `!check <skill> [adv\|dis]` | `!check perception adv` | Ability/skill check with your modifier |
| `!save <ability> [adv\|dis]` | `!save DEX dis` | Saving throw with proficiency if applicable |
| `!attack <weapon> [adv\|dis]` | `!attack greatsword adv` | Attack + damage roll with a weapon from your sheet |
| `!attack <weapon> <atk> <dmg>` | `!attack greatsword 1d20+4 2d6+2` | Manual attack + damage with custom dice |
| `!spellattack <spell> <dmg>` | `!spellattack Fire Bolt 1d10` | Spell attack + damage (auto spell attack mod) |
| `!spellattack <spell> <atk> <dmg>` | `!spellattack Eldritch Blast 1d20+5 1d10+3` | Manual spell attack + damage |

`!spellattack` aliases: `!sa`, `!spellatk`

Advantage rolls the d20 twice and takes the higher result. Disadvantage takes the lower. Both individual rolls are shown. Critical hits (nat 20) automatically roll extra damage dice.

### Combat & Tactical Map

| Command | Who | Description |
|---|---|---|
| `!combatstart` | DM | Begin a combat encounter |
| `!initiative [adv\|dis]` | Player | Roll initiative (d20 + DEX mod) |
| `!addnpc <name> <roll>` | DM | Add an NPC/monster to initiative |
| `!removenpc <name>` | DM | Remove an NPC from initiative |
| `!begincombat` | DM | Sort initiative and start turn order |
| `!turnorder` | Anyone | Display the current initiative order |
| `!next` | DM | Advance to the next turn |
| `!pass` | Player | Skip your combat turn |
| `!map` | Anyone | Display the ASCII tactical map |
| `!place <name> <x> <y>` | DM | Place a token on the map (optional 4th arg for custom label) |
| `!move <dir> <dist>` | Player/DM | Move on map (n/s/e/w/ne/nw/se/sw + distance) |
| `!move <x> <y>` | Player/DM | Move to absolute coordinates |
| `!mapsize <w> <h>` | DM | Resize the map grid (5-20 each dimension) |
| `!combatend` | DM | End the combat encounter |

### Progression & Resources

| Command | Who | Description |
|---|---|---|
| `!rest short` | Player | Short rest — spend hit dice to heal (warlock pact slots restored) |
| `!rest long` | Player | Long rest — full HP, restore hit dice & all spell slots |
| `!hitdie [count]` | Player | Spend hit dice to heal (alias: `!hd`) |
| `!hp` | Player | View your current HP (shows unconscious status) |
| `!hp +5` / `!hp -3` | Player/DM | Heal or take damage |
| `!hp @player -5` | DM | DM adjusts another player's HP |
| `!xp <amount>` | DM | Award XP to all players |
| `!xp <amount> @player` | DM | Award XP to one player |
| `!levelup` | Player | Level up if you have enough XP (spell slots update automatically) |
| `!inspiration @player` | DM | Grant inspiration |
| `!deathsave` | Player | Roll a death saving throw |
| `!stabilize @player` | Anyone | Stabilize an unconscious character at 0 HP |
| `!feat` | Player | List your feats |
| `!feat add <name>` | Player | Add a feat |
| `!feat remove <name>` | Player | Remove a feat |
| `!modifier` | Player | List active stat modifiers (magic items, buffs, etc.) |
| `!modifier add <source> <stat> <+/-val>` | Player | Add a named modifier (e.g., `Shield ac +2`) |
| `!modifier remove <source>` | Player | Remove a modifier by source name |

### Spells & Spellcasting

| Command | Description |
|---|---|
| `!spells` | View your known spells, prepared spells, and cantrips |
| `!slots` | View your current spell slots (visual diamond pips) |
| `!learn <spell>` | Add a spell to your known spells |
| `!learncantrip <name>` | Learn a cantrip (enforces class max) |
| `!forget <spell>` | Remove a spell from your known list |
| `!forget cantrip <name>` | Remove a cantrip |
| `!prepare <spell>` | Prepare or unprepare a known spell |
| `!cast <spell>` | Cast a spell using the lowest available slot |
| `!cast <spell> <level>` | Cast a spell at a specific slot level |

Spell slots are tracked per D&D 5e rules: full casters (Bard, Cleric, Druid, Sorcerer, Wizard), half casters (Paladin, Ranger), and pact casters (Warlock) each have their own slot progression. Warlock pact magic slots recover on short rest; all other slots recover on long rest.

### Utility

| Command | Description |
|---|---|
| `!recap` | AI-narrated dramatic recap of recent events |
| `!status` | Campaign phase + party HP/AC at a glance |
| `!clues` | View investigation clues |
| `!clues add <text>` | Add a clue |
| `!clues remove <#>` | Remove a clue |
| `!npcs` | View known NPCs |
| `!npcs add <name> \| <desc>` | Add an NPC to the journal |
| `!npcs remove <#>` | Remove an NPC |
| `!whisper <msg>` | Private message to the DM (sent via Discord DM) |
| `!commands [category]` | Show help menu via DM (campaign, character, gameplay, dice, combat, progression, spells, utility, botinfo) |

### Bot Info & Admin

| Command | Description |
|---|---|
| `!ping` | Check bot latency and status |
| `!version` (`!v`, `!ver`) | Show version info and release notes |
| `!botinfo` (`!about`, `!info`) | Detailed bot statistics (uptime, memory, server count) |
| `!checkupdate` | *(Owner only)* Check GitHub for new versions |
| `!restart` | *(Owner only)* Restart the bot (requires wrapper script) |
| `!update` | *(Owner only)* Pull updates from GitHub and restart |
| `!shutdown` (`!stop`) | *(Owner only)* Shut down the bot completely |

> Owner-only commands use Discord.py's `is_owner()` check, which verifies against `BOT_OWNER_ID` in your `.env` file.

---

## Character Creation Walkthrough

When a player types `!createchar` in the server channel, the bot sends them a **private DM** to walk through character creation. This keeps character choices secret from other players and allows multiple players to create characters at the same time. All `!cc` responses happen in DMs — only the final "character joined the party" announcement appears in the server channel.

Every step includes **help text** showing available options, numbered lists, and usage examples so players never have to guess what to type.

### Step 1: Name

```
!cc Thandril
```

### Step 2: Gender

```
!cc Male
```

Options: Male, Female, Non-binary, or type anything custom.

### Step 3: Race

All Player's Handbook races and subraces:

| Race | Subraces |
|---|---|
| Dwarf | Hill Dwarf, Mountain Dwarf |
| Elf | High Elf, Wood Elf, Dark Elf (Drow) |
| Halfling | Lightfoot, Stout |
| Human | — |
| Dragonborn | + Draconic Ancestry choice (10 types) |
| Gnome | Forest Gnome, Rock Gnome |
| Half-Elf | + Choose 2 bonus ability scores |
| Half-Orc | — |
| Tiefling | — |

Racial ability bonuses, traits, speed, and languages are applied automatically.

### Step 4: Class

All 12 PHB classes:

| Class | Hit Die | Primary | Description |
|---|---|---|---|
| Barbarian | d12 | STR | Primal rage warrior |
| Bard | d8 | CHA | Song and magic inspire allies |
| Cleric | d8 | WIS | Divine champion of a deity |
| Druid | d8 | WIS | Nature magic and wild shapes |
| Fighter | d10 | STR | Master of martial combat |
| Monk | d8 | DEX | Martial arts and ki |
| Paladin | d10 | STR | Holy warrior with a sacred oath |
| Ranger | d10 | DEX | Wilderness warrior and tracker |
| Rogue | d8 | DEX | Stealth and trickery |
| Sorcerer | d6 | CHA | Innate magical bloodline |
| Warlock | d8 | CHA | Pact magic from a patron |
| Wizard | d6 | INT | Arcane spells through study |

### Step 5: Ability Scores

Three methods:

- **Roll** — 4d6 drop lowest, six times. The bot rolls and shows every die.
- **Standard Array** — [15, 14, 13, 12, 10, 8]. Assign to STR/DEX/CON/INT/WIS/CHA.
- **Point Buy** — 27 points to spend. Interactively adjust scores 8-15.

Racial bonuses are added on top automatically.

### Step 6: Background

13 PHB backgrounds (Acolyte, Charlatan, Criminal, Entertainer, Folk Hero, Guild Artisan, Hermit, Noble, Outlander, Sage, Sailor, Soldier, Urchin). Each grants:

- 2 skill proficiencies
- A background feature
- Tool/language proficiencies

### Step 7: Class Skills

Choose from your class's skill list (skills already granted by background are excluded).

### Step 8: Starting Equipment

Each class comes with a set of starting equipment. Some items are fixed (e.g., "Explorer's pack"), while others present a choice:

```
Bot:     Choose starting equipment (1 of 2):
           1. Greataxe
           2. Any martial weapon
!cc 1
Bot:     You selected: Greataxe
         Choose starting equipment (2 of 2):
           1. Two handaxes
           2. Any simple weapon
!cc 2
Bot:     You selected: Any simple weapon
         Fixed items added: Explorer's pack, 4 javelins
```

### Step 9: Weapon Selection

Choose your starting weapons from class-appropriate options. Each class has one or more weapon choice groups. The bot shows weapon stats (damage, type, properties) for each option:

```
Bot:     Choose your Primary weapon:
           1. Longsword — 1d8 slashing [Versatile (1d10)]
           2. Battleaxe — 1d8 slashing [Versatile (1d10)]
           3. Greatsword — 2d6 slashing [Heavy, Two-handed]
           4. Rapier — 1d8 piercing [Finesse]
!cc 4
Bot:     Selected: Rapier
         Choose your Ranged weapon:
           1. Light Crossbow — 1d8 piercing [Ammunition, Loading, Two-handed]
           2. Longbow — 1d8 piercing [Ammunition, Heavy, Two-handed]
!cc 2
Bot:     Selected: Longbow
```

Weapons appear on your character sheet with calculated attack bonuses (STR or DEX mod + proficiency). Use `!weapons` anytime to view them.

### Step 10: Spell Selection (Spellcasters Only)

If your class can cast spells, you'll choose starting cantrips and 1st-level spells. The number depends on your class:

| Class | Cantrips | Level 1 Spells | Type |
|---|---|---|---|
| Bard | 2 | 4 known | Known |
| Cleric | 3 | WIS mod + 1 prepared | Prepared |
| Druid | 2 | WIS mod + 1 prepared | Prepared |
| Sorcerer | 4 | 2 known | Known |
| Warlock | 2 | 2 known | Known |
| Wizard | 3 | 6 in spellbook | Spellbook |
| Paladin | 0 | WIS mod + 1 prepared | Prepared |
| Ranger | 0 | 2 known | Known |

```
Bot:     Choose cantrip 1 of 3:
           1. Guidance  2. Light  3. Sacred Flame  4. Spare the Dying  5. Thaumaturgy
!cc 3
Bot:     Learned cantrip: Sacred Flame (1/3)
         Choose cantrip 2 of 3:
           1. Guidance  2. Light  3. Spare the Dying  4. Thaumaturgy
!cc 1
Bot:     Learned cantrip: Guidance (2/3)
```

Non-caster classes (Barbarian, Fighter, Monk, Rogue) skip this step automatically.

### Step 11: Backstory (Optional)

Write a short backstory for your character, or type `skip` to leave it blank. You can always set or update it later with `!backstory <text>`.

```
!cc A former soldier who deserted after witnessing corruption in the ranks.
Bot:     Backstory saved!
```

After confirming, the character is saved and ready to play. View anytime with `!sheet`, `!equipment`, `!weapons`, or `!backstory`.

---

## RP Scene Coordination

This is a key design feature: during non-combat RP, the bot **does not** send player actions to Claude one at a time. Instead:

1. Player A types `!action I search the bookshelf`
2. Bot says: **"Player A's action is locked in. Waiting on: @PlayerB, @PlayerC"**
3. Player B types `!ic "Does anyone else hear that noise?"`
4. Player C types `!pass`
5. **All players have acted** — the bot bundles all actions and sends them to Claude in one prompt
6. Claude narrates a single cohesive scene responding to everyone

This prevents the problem where two players talk to the DM separately and get conflicting or overlapping storylines.

**Special commands:**

- `!pending` — See who hasn't acted yet
- `!undo` — Cancel your pending action and rejoin the waiting list
- `!resolve` — DM can force the round to resolve early (e.g., if someone is AFK)
- `!pass` — Player has nothing to do this round
- `!ooc` — Out-of-character chat, does NOT count as an action
- `!ask` — Rules questions, does NOT count as an action
- During **combat**, the queue system is disabled — actions go directly to Claude per the initiative turn order

---

## Combat System & Tactical Map

### Starting Combat

```
DM:      !combatstart
Bot:     COMBAT STARTED! All players: Roll initiative with !initiative
```

### Rolling Initiative

```
Player:  !initiative
Bot:     Thandril rolls initiative: [14] +2 = 16

Player:  !initiative adv       # With advantage (e.g., Alert feat)
Bot:     Thandril rolls initiative (advantage): [14, 8] → 14 +2 = 16
```

The DM adds NPCs manually:

```
DM:      !addnpc Goblin1 12
DM:      !addnpc "Orc Warchief" 18
```

### Beginning Turns

```
DM:      !begincombat
Bot:     Initiative Order — Round 1
           18 — Orc Warchief <<< CURRENT TURN
           16 — Thandril
           12 — Goblin1
         DM: It's Orc Warchief's turn.
```

### Turn Flow

- Only the current player can use `!action` (or the DM for NPC turns)
- `!pass` skips a turn
- `!next` (DM only) advances to the next turn
- `!turnorder` shows the current order at any time

### Tactical Map

When combat starts, the DM can place tokens on an ASCII grid map. Players can then see positions and move their characters.

**Placing tokens (DM):**

```
DM:      !place Thandril 3 2
Bot:     Thandril (TH) placed at (3, 2).

DM:      !place Goblin1 7 4 G1
Bot:     Goblin1 (G1) placed at (7, 4).
```

**Viewing the map:**

```
Player:  !map
Bot:     Combat Map — Round 1
            0  1  2  3  4  5  6  7  8  9
            ┌──┬──┬──┬──┬──┬──┬──┬──┬──┬──┐
          0 │  │  │  │  │  │  │  │  │  │  │
            ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
          1 │  │  │  │  │  │  │  │  │  │  │
            ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
          2 │  │  │  │TH│  │  │  │  │  │  │
            ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
          3 │  │  │  │  │  │  │  │  │  │  │
            ├──┼──┼──┼──┼──┼──┼──┼──┼──┼──┤
          4 │  │  │  │  │  │  │  │G1│  │  │
            ...
         Legend: G1=Goblin1 (7,4)  TH=Thandril (3,2)
```

**Moving tokens:**

```
Player:  !move north 2       # Directional: n/s/e/w/ne/nw/se/sw + distance
Player:  !move 5 3           # Absolute: move to coordinates (5, 3)
DM:      !move Goblin1 south 1   # DM can move NPCs by name
```

**Resizing the map (DM):**

```
DM:      !mapsize 15 12
Bot:     Combat map resized to 15x12. All tokens cleared.
```

The map grid supports sizes from 5x5 to 20x20. Tokens are clamped to stay within bounds.

### Ending Combat

```
DM:      !combatend
Bot:     Combat has ended after 4 round(s). Resume roleplay freely!
```

---

## Inventory & Equipment

The bot tracks each character's inventory, gold, and equipped items. Claude can automatically give loot via `[LOOT:]` tags, and players can manage their gear with commands.

### Gold

```
Player:  !gold
Bot:     Thandril's Gold: 150 gp

Player:  !gold +50
Bot:     Thandril's gold: 100 → 150 gp

Player:  !give @Player2 25 gold
Bot:     Gave 25 gold to Elara.
```

The DM can also adjust gold:

```
DM:      !gold @Player +100
DM:      !loot @Player 50 gold
DM:      !giveall 100 gold
```

### Items

```
Player:  !equipment
Bot:     Thandril's Inventory:
         Gold: 150 gp
         Equipped: Chain Mail, Shield

         • Potion of Healing x2
         • Rope (50 ft)
         • Torch x5

Player:  !equipment add Rope (50 ft)
Bot:     Added Rope (50 ft) to inventory.

Player:  !give @Player2 Potion of Healing
Bot:     Gave Potion of Healing to Elara.
```

Items stack automatically — adding another "Torch" increments the quantity rather than creating a duplicate entry.

### DM Loot Commands

```
DM:      !loot @Player Potion of Healing
DM:      !loot @Player 3 Arrows
DM:      !giveall Potion of Healing     (gives to all players)
DM:      !giveall 50 gold               (gives to all players)
```

Claude can also give loot automatically during narration using `[LOOT:]` tags — see [DM Tools & Action Tags](#dm-tools--action-tags).

---

## Armor & AC System

AC is calculated automatically based on equipped armor, shield, DEX modifier, and class features.

### Armor Types

| Armor | Type | Base AC | DEX Bonus | Stealth |
|---|---|---|---|---|
| Leather | Light | 11 | Full DEX | — |
| Studded Leather | Light | 12 | Full DEX | — |
| Hide | Medium | 12 | Max +2 | — |
| Chain Shirt | Medium | 13 | Max +2 | — |
| Scale Mail | Medium | 14 | Max +2 | Disadvantage |
| Breastplate | Medium | 14 | Max +2 | — |
| Half Plate | Medium | 15 | Max +2 | Disadvantage |
| Ring Mail | Heavy | 14 | None | Disadvantage |
| Chain Mail | Heavy | 16 | None | Disadvantage |
| Splint | Heavy | 17 | None | Disadvantage |
| Plate | Heavy | 18 | None | Disadvantage |

**Shield:** +2 AC (can be equipped alongside armor).

### Unarmored Defense

- **Barbarian:** 10 + DEX mod + CON mod
- **Monk:** 10 + DEX mod + WIS mod
- **Others (no armor):** 10 + DEX mod

### Starting Armor

Each class receives appropriate starting armor during character creation:

| Class | Starting Armor | Shield |
|---|---|---|
| Fighter, Paladin | Chain Mail | Yes |
| Cleric | Scale Mail | Yes |
| Ranger | Scale Mail | No |
| Rogue, Bard, Warlock, Druid | Leather | No |
| Barbarian, Monk, Sorcerer, Wizard | None (unarmored) | No |

### Equipping Armor

```
Player:  !equip armor Studded Leather
Bot:     Equipped Studded Leather. AC: 12 → 14

Player:  !equip shield
Bot:     Equipped shield. AC: 14 → 16

Player:  !equip no shield
Bot:     Removed shield. AC: 16 → 14

Player:  !equip none
Bot:     Removed armor. AC: 14 → 12

Player:  !ac
Bot:     Thandril's AC: 16 (Chain Mail, Shield)
```

---

## Consumables

Certain items have automatic effects when used with `!use`. The bot rolls dice and applies healing or removes conditions automatically.

### Available Consumables

| Item | Effect | Dice |
|---|---|---|
| Potion of Healing | Heal | 2d4 + 2 |
| Potion of Greater Healing | Heal | 4d4 + 4 |
| Potion of Superior Healing | Heal | 8d4 + 8 |
| Potion of Supreme Healing | Heal | 10d4 + 20 |
| Antitoxin | Remove poisoned condition | — |

### Using Consumables

```
Player:  !use Potion of Healing
Bot:     Thandril uses Potion of Healing.
         Healed 7 HP (rolled 2d4+2: [3, 2] + 2 = 7)
         HP: 15 → 22/30

Player:  !use Antitoxin
Bot:     Thandril uses Antitoxin.
         Condition removed: poisoned
```

Items not in the consumables database are simply removed from inventory — Claude handles the narrative effect.

---

## Spell System

The bot tracks spellcasting for all D&D 5e caster types:

| Caster Type | Classes | Slot Recovery |
|---|---|---|
| **Full Caster** | Bard, Cleric, Druid, Sorcerer, Wizard | Long rest |
| **Half Caster** | Paladin, Ranger | Long rest |
| **Pact Caster** | Warlock | Short rest |

Non-caster classes (Barbarian, Fighter, Monk, Rogue) have no spell slots.

**Half-caster note:** Paladins and Rangers gain spellcasting at **level 2**, not level 1. If the campaign starting level is 2+, they'll choose spells during character creation. At level 1, they have no spell slots.

### Spellcasting Workflow

```
Player:  !learncantrip Fire Bolt
Bot:     Learned cantrip: Fire Bolt (2/3 cantrips known)

Player:  !learn Magic Missile
Bot:     Learned spell: Magic Missile

Player:  !prepare Magic Missile
Bot:     Magic Missile is now prepared.

Player:  !cast Magic Missile
Bot:     Cast Magic Missile using a level 1 slot! (3/4 slots remaining)

Player:  !slots
Bot:     Spell Slots for Thandril:
         Lv1: ◆◆◆◇ (3/4)

Player:  !rest long
Bot:     [All slots restored]
```

### Spell Save DC & Attack Bonus

These are calculated automatically based on your spellcasting ability:

- **Spell Save DC** = 8 + proficiency bonus + spellcasting ability modifier
- **Spell Attack** = proficiency bonus + spellcasting ability modifier

View them on your character sheet (`!sheet`) or spell list (`!spells`).

---

## Rest & Hit Dice

### Short Rest

During a short rest, characters can spend **hit dice** to heal. Each hit die rolls the class's die + CON modifier (minimum 1 HP per die).

```
Player:  !rest short
Bot:     Thandril takes a short rest.
         Spent 1 hit die: d10 [6] + CON (+2) = 8 HP healed
         HP: 15 → 23/30
         Hit Dice remaining: 4

Player:  !hitdie 2
Bot:     Thandril spends 2 hit dice:
           d10 [7] + CON (+2) = 9
           d10 [4] + CON (+2) = 6
         Healed: 15 HP
         HP: 23 → 30/30
         Hit Dice remaining: 2/5
```

Warlock pact magic slots are restored on short rest. All other spell slots require a long rest.

### Long Rest

A long rest fully restores HP and spell slots, and recovers half your max hit dice (minimum 1):

```
Player:  !rest long
Bot:     Thandril takes a long rest.
         HP fully restored: 30/30 (+7)
         Hit Dice restored: 2 (total: 4)
         Death saves reset.
         All spell slots restored!
```

### Hit Dice Summary

| Level | Max Hit Dice | Short Rest | Long Rest Recovery |
|---|---|---|---|
| 1 | 1 | Spend any available | Recover at least 1 |
| 5 | 5 | Spend any available | Recover 2 |
| 10 | 10 | Spend any available | Recover 5 |

Hit dice can never exceed your character level.

---

## Death Saves & Unconscious

### Falling to 0 HP

When a character drops to 0 HP, they fall **unconscious** and begin making death saving throws. The bot:

1. Adds the "unconscious" condition automatically
2. Shows **UNCONSCIOUS** status in `!hp` output
3. Reports death save progress to Claude so the DM can narrate it

```
DM:      !hp @Player -15
Bot:     Thandril took 15 damage: 8 → 0/30
         Thandril has fallen to 0 HP! Death saving throws begin...
```

### Death Saving Throws

Each turn at 0 HP, the player rolls a d20:

| Roll | Result |
|---|---|
| 1 | 2 failures (critical fail) |
| 2-9 | 1 failure |
| 10-19 | 1 success |
| 20 | Regain 1 HP and consciousness (critical success) |

Three successes = **stabilized** (no longer dying). Three failures = **death**.

```
Player:  !deathsave
Bot:     Thandril rolls a death save: [14] — Success
         Successes: O.. | Failures: ...

Player:  !deathsave
Bot:     Thandril rolls a death save: [20] NAT 20!
         Thandril regains consciousness with 1 HP!
```

### Stabilizing

Any player can stabilize an unconscious ally:

```
Player:  !stabilize @FallenPlayer
Bot:     Thandril has been stabilized. No longer making death saves.
```

### Healing from Unconscious

Any healing brings the character back to consciousness:

```
DM:      !hp @Player +5
Bot:     Thandril healed 5 HP: 0 → 5/30
         Thandril regains consciousness!
```

Death saves reset automatically when a character regains HP or takes a long rest.

---

## Game Threads & Forum Posts

When a campaign starts, the bot creates a **Discord forum post** or **thread** to keep the game organized and separate from other channel activity.

### Forum Posts (Recommended)

Set your forum channel directly from Discord:

```
!setforum #campaigns
```

That's it! The setting is saved per-server and persists across bot restarts. Use `!clearforum` to switch back to threads.

Alternatively, you can set `CAMPAIGN_FORUM_ID` in your `.env` file (the `!setforum` command takes priority over the env var):

```
CAMPAIGN_FORUM_ID=1234567890123456789
```

When `!startcampaign` is used:
1. The bot creates a **forum post** in your designated forum channel
2. The opening narration appears in the forum post
3. All gameplay happens in that organized forum post
4. The setup channel gets a link to the forum post

### Thread Fallback

If no forum is configured, the bot falls back to creating a **public thread** in the current channel (same as before).

### How It Works

1. **Setup phase** (`!newcampaign`, `!createchar`) happens in any channel
2. When the DM types `!startcampaign`:
   - With `CAMPAIGN_FORUM_ID` set: creates a forum post in the designated forum
   - Without forum: creates a public thread in the current channel
   - Without thread permissions: plays directly in the current channel
3. All gameplay commands (`!action`, `!roll`, `!check`, etc.) should be used **in the forum post/thread**
4. When the campaign ends (`!endcampaign`), the forum post/thread is archived

### Required Permissions

The bot needs these Discord permissions:

**For forum posts:**
- **Create Posts** — to create forum posts
- **Send Messages in Threads** — to post in the forum post
- **Manage Threads** — to archive when the campaign ends

**For threads (fallback):**
- **Create Public Threads** — to create the game thread
- **Send Messages in Threads** — to post in the thread
- **Manage Threads** — to archive the thread when the campaign ends
- **Add Reactions** — for `!suggestcampaign` emoji reactions

If the bot lacks permissions, it falls back gracefully: forum post > thread > playing in the channel directly.

### Multiple Campaigns

Each channel can have one campaign at a time. With forum posts, all campaigns are organized in one forum channel, making them easy to find and browse.

---

## DM Tools & Action Tags

### DM-Initiated Narration (`!dm`)

The DM can prompt Claude to narrate scenes, events, or story beats without waiting for player actions:

```
DM:      !dm A dragon lands in front of the party, shaking the ground
Bot:     *The earth trembles beneath your feet as a massive shadow blots out
         the sun. A red dragon descends, its wings sending gusts of scorching
         air across the clearing...*
```

Use this for scene transitions, NPC arrivals, time passing, traps triggering, or any story moment the DM wants to drive.

### Action Tags (Automatic Game State Updates)

Claude automatically updates game state through hidden tags in its narration. Players never see the tags — they only see the narrative text. The bot parses and executes them behind the scenes.

| Tag | Effect | Example |
|---|---|---|
| `[DAMAGE: Name -X]` | Deal X damage | `[DAMAGE: Thandril -9]` |
| `[DAMAGE: Name +X]` | Heal X HP | `[DAMAGE: Elara +5]` |
| `[CONDITION: Name add X]` | Apply a condition | `[CONDITION: Kael add poisoned]` |
| `[CONDITION: Name remove X]` | Remove a condition | `[CONDITION: Kael remove poisoned]` |
| `[NPC_DEFEAT: Name]` | Remove NPC from combat | `[NPC_DEFEAT: Goblin1]` |
| `[SPELL_SLOT: Name -level]` | Consume a spell slot | `[SPELL_SLOT: Elara -1]` |
| `[LOOT: Name \| items]` | Add items/gold to inventory | `[LOOT: Thandril \| Potion of Healing, 50 gold]` |
| `[WHISPER: Name] msg` | Private DM to one player | `[WHISPER: Elara] You see a hidden door` |

**Example of what Claude might write:**

> "The orc's axe crashes down! [DAMAGE: Thandril -9] Thandril, you stagger from 9 slashing damage."

Players see: *"The orc's axe crashes down! Thandril, you stagger from 9 slashing damage."*
Behind the scenes: Thandril's HP is reduced by 9.

### DM Rewind (`!rewind`)

If Claude makes a mistake (wrong NPC name, contradicts lore, kills the wrong character), the DM can undo it:

```
DM:      !rewind
Bot:     Last DM response removed. Continue from the previous action.
```

This removes the last assistant + user exchange from Claude's conversation history. Optionally, the DM can provide a new prompt to replace the scene:

```
DM:      !rewind The dragon doesn't attack yet — it speaks first
Bot:     [Claude generates a new scene where the dragon speaks]
```

### DM Whispers

Two ways to send private information to a player:

1. **Manual:** `!dm-whisper @Player Your passive Perception notices a tripwire` (aliases: `!dmw`, `!secret`)
2. **Automatic:** Claude includes `[WHISPER: CharName]` tags in narration — the bot sends the secret as a Discord DM

Whispers are hidden from the channel. Only the target player sees the message.

### Campaign Suggestions (`!suggestcampaign`)

Don't have a campaign idea? Ask Claude to brainstorm:

```
DM:      !suggestcampaign
Bot:     What kind of campaign are you interested in?
         1️⃣ Combat-Focused    2️⃣ Roleplay-Heavy    3️⃣ Mystery/Investigation
         4️⃣ Exploration        5️⃣ Surprise Me
         React with a number or type 1-5

DM:      [reacts with 2️⃣ or types "2"]
Bot:     Claude is brainstorming campaign ideas...

         Campaign Suggestions:

         **1. The Masquerade of Mirrors**
         A political intrigue campaign set in a decadent city-state...
         *Starting Level: 3*

         **2. The Traveling Theater Troupe**
         You're performers traveling between villages...
         *Starting Level: 1*

         **3. The Diplomatic Envoys**
         Prevent a war between two kingdoms through negotiation...
         *Starting Level: 2*

         React 1️⃣/2️⃣/3️⃣ to start that campaign, or !newcampaign to create your own.

DM:      [reacts with 1️⃣]
Bot:     Campaign Created: The Masquerade of Mirrors
         Starting Level: 3
         Players can now create characters with !createchar
```

The selected campaign is created in setup phase with the suggested starting level applied automatically.

### Full Party Stats for Claude

Claude sees detailed stats for every character in its prompt, including:
- HP, AC, ability modifiers, proficiency bonus
- Key skill modifiers (Perception, Investigation, Stealth, Insight, Athletics, Arcana)
- Passive Perception & Investigation scores
- Active conditions, prepared spells, equipment, and backstory

This allows Claude to make informed DM decisions — calling for appropriate checks, adjusting difficulty, and referencing character details in narration.

### Stat Modifiers

Track magic items, equipment bonuses, buffs, and other stat adjustments with the `!modifier` command (aliases: `!mod`, `!buff`):

```
Player:  !modifier add Shield ac +2
Bot:     Thandril gained modifier: Shield (ac +2)

Player:  !modifier add Gauntlets of Ogre Power STR +5
Bot:     Thandril gained modifier: Gauntlets of Ogre Power (STR +5)

Player:  !modifier add Boots of Elvenkind Stealth +5
Bot:     Thandril gained modifier: Boots of Elvenkind (Stealth +5)

Player:  !modifier
Bot:     Thandril's Modifiers:
           • Shield — ac +2
           • Gauntlets of Ogre Power — STR +5
           • Boots of Elvenkind — Stealth +5

Player:  !modifier remove Shield
Bot:     Removed modifier Shield (ac +2) from Thandril.
```

**Supported stats:** STR, DEX, CON, INT, WIS, CHA, ac, hp, speed, and all 18 skill names (Perception, Stealth, Athletics, etc.).

Modifiers automatically affect all derived calculations — ability checks, saving throws, skill rolls, AC, and passive scores. They're visible on `!sheet` and to Claude in the DM context.

### Advantage & Disadvantage

All dice commands support advantage and disadvantage via the `adv` and `dis` keywords:

```
Player:  !check perception adv
Bot:     Perception check (advantage): [14, 8] → 14 +3 = 17

Player:  !save DEX dis
Bot:     DEX saving throw (disadvantage): [12, 18] → 12 +4 = 16

Player:  !attack adv
Bot:     Attack roll (advantage): [19, 7] → 19 +5 = 24

Player:  !roll d20 dis
Bot:     Rolling d20 (disadvantage): [4, 15] → 4
```

The bot rolls the d20 twice and takes the higher (advantage) or lower (disadvantage) result. Both individual rolls are always displayed.

### Quick Stat Commands

View specific parts of your character sheet without the full `!sheet`:

```
Player:  !ac
Bot:     Thandril's AC: 16 (base 10 + DEX +3 + armor/shield)

Player:  !stats
Bot:     Thandril — Ability Scores:
         STR 16 (+3)  DEX 14 (+2)  CON 13 (+1)
         INT 10 (+0)  WIS 12 (+1)  CHA  8 (-1)

Player:  !skills
Bot:     Thandril — Skill Modifiers:
         Athletics +5★  Acrobatics +2  Stealth +2 ...
         (★ = proficient)

Player:  !saves
Bot:     Thandril — Saving Throws:
         STR +5★  DEX +2  CON +3★  INT +0  WIS +1  CHA -1

Player:  !weapons
Bot:     Thandril — Weapons:
         Longsword — +5 to hit, 1d8+3 slashing [Versatile (1d10)]
         Longbow — +4 to hit, 1d8+2 piercing [Ammunition, Heavy, Two-handed]
```

### Fuzzy Matching & Error Messages

Mistype a skill, ability, or condition name? The bot suggests the closest match:

```
Player:  !check percption
Bot:     Unknown skill: `percption`. Did you mean **Perception**?

Player:  !save DEXTERITY
Bot:     Unknown ability: `DEXTERITY`. Did you mean **DEX**?
```

All gameplay commands also include usage examples when called without arguments:

```
Player:  !action
Bot:     Describe what your character does.
         Usage: `!action <description>`
         Examples: `!action I search the room for traps`
```

---

## Auto-Update & Restart System

TTRPGBot includes a built-in update and restart system that can be controlled from Discord.

### How It Works

1. **Version tracking** — `bot/version.py` stores the current version number (semver)
2. **Background checker** — Every 24 hours, the bot fetches the latest `bot/version.py` from GitHub and compares versions
3. **Owner notifications** — If a newer version is found, the bot DMs the owner
4. **Discord commands** — `!update` pulls latest code and restarts; `!restart` restarts without updating; `!shutdown` stops the bot

### Wrapper Scripts

The `!restart` and `!update` commands require the bot to be started with a wrapper script:

- **Windows:** `start.bat`
- **Linux/Mac:** `start.sh` (run `chmod +x start.sh update.sh` first)

The wrapper script monitors the bot's exit code:
- **Exit 0** — Normal shutdown, wrapper exits
- **Exit 42** — Restart requested, wrapper restarts the bot
- **Exit 43** — Update requested, wrapper runs the update script then restarts

A `.wrapper_active` marker file is created when running through the wrapper. If this file doesn't exist, `!restart`/`!update` will show instructions instead.

### Setting Up Owner Commands

1. Add your Discord user ID to `.env`:
   ```
   BOT_OWNER_ID=123456789012345678
   ```
2. To find your ID: Enable Developer Mode in Discord settings, right-click yourself, select "Copy User ID"
3. Owner-only commands: `!checkupdate`, `!restart`, `!update`, `!shutdown`

---

## Prompt Caching (Cost Savings)

The bot uses [Anthropic's prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) to dramatically reduce API costs. Three cache breakpoints are placed strategically:

| What Gets Cached | How Often It Changes | Savings |
|---|---|---|
| DM system instructions (~2000 tokens) | Never | Cached after 1st call — free on every subsequent call |
| Campaign context (party stats, NPCs, combat state) | Between rounds | Cached within each round |
| Conversation history | +1 message per turn | Prior messages cached, only new message is billed |

**Cached input tokens cost 90% less.** For a typical session with 50+ exchanges, this means:

- The system prompt is only billed at full price **once**
- The growing conversation history is mostly served from cache
- You'll see cache stats in the console log:

```
Cache stats — read: 3200, created: 150, uncached: 85, output: 312
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | Yes | — | Your Discord bot token |
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `BOT_OWNER_ID` | No | — | Your Discord user ID (enables owner-only commands) |
| `CAMPAIGN_FORUM_ID` | No | — | Forum channel ID for auto-creating campaign posts |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Which Claude model to use |
| `COMMAND_PREFIX` | No | `!` | Bot command prefix |

---

## Project Structure

```
TTRPGBot/
├── bot/
│   ├── main.py              # Entry point — bot setup, event handlers, shutdown, update checker
│   ├── version.py            # Version tracking (semver) and release notes
│   ├── update_checker.py     # Background GitHub version checker (24h interval)
│   ├── dm_engine.py          # Claude AI DM — API calls, prompt caching, action tag parser
│   ├── dice.py               # Dice rolling engine (notation parsing, ability checks, adv/dis)
│   ├── storage.py            # Persistent JSON file storage per campaign
│   ├── cogs/
│   │   ├── campaign.py       # !newcampaign, !suggestcampaign, !pitch, !startcampaign, !loot, threads
│   │   ├── character.py      # !createchar, !sheet, !ac/stats/skills/saves/weapons, !equip, !use, !give
│   │   ├── gameplay.py       # !action, !ic, !emote, !look, !ask, !dm, !undo, !rewind, RP queue
│   │   ├── combat.py         # !combatstart, !initiative, !next, !map, !place, !move
│   │   ├── progression.py    # !rest, !hp, !xp, !levelup, !deathsave, !stabilize, !hitdie, !feat, !modifier
│   │   ├── spells.py         # !spells, !slots, !learn, !prepare, !cast, !forget
│   │   ├── utility.py        # !recap, !status, !clues, !npcs, !whisper, !commands (via DM)
│   │   └── info.py           # !ping, !version, !botinfo, !restart, !update, !shutdown
│   ├── models/
│   │   ├── character.py      # Character class — stats, abilities, spells, weapons, serialization
│   │   └── campaign.py       # Campaign, CombatState, CombatMap, RP queue state
│   ├── utils/
│   │   └── fuzzy_match.py    # Fuzzy matching for skills, abilities, conditions
│   └── data/
│       ├── races.py          # All PHB races + subraces with bonuses and traits
│       ├── classes.py         # All 12 PHB classes with proficiencies & starting equipment
│       ├── backgrounds.py    # 13 PHB backgrounds with skills and features
│       ├── spells.py         # Spell slot tables for full/half/pact casters
│       ├── rules.py          # Ability scores, skills, proficiency table, XP table
│       ├── weapons.py        # All PHB weapons + class starting weapon choices
│       ├── spell_lists.py    # Spell lists per class + starting spell counts
│       ├── armor.py          # PHB armor database + AC calculation
│       └── consumables.py    # Consumable items (healing potions, antitoxin)
├── data/
│   └── campaigns/            # Auto-created — JSON save files live here
├── start.bat                 # Windows wrapper script (enables !restart/!update)
├── start.sh                  # Linux/Mac wrapper script (enables !restart/!update)
├── update.bat                # Windows auto-updater (git pull + pip install)
├── update.sh                 # Linux/Mac auto-updater (git pull + pip install)
├── requirements.txt          # Python dependencies
├── Procfile                  # Railway.app deployment config
├── .env.example              # Template for environment variables
└── .gitignore
```

---

## FAQ

**Q: Can I change the DM's personality or style?**
A: Yes — edit the `SYSTEM_PROMPT_STATIC` string in `bot/dm_engine.py`. That's the instruction set that tells Claude how to DM. You can make it more serious, more comedic, more rules-strict, etc.

**Q: How many players can play?**
A: Designed for 3-6 players, but there's no hard limit. The RP queue system waits for all players with completed characters.

**Q: Can I play solo?**
A: Yes. With one player, the RP queue resolves immediately on your action (since you're the only player).

**Q: Does the bot remember things between sessions?**
A: Yes. Campaign data (characters, history, NPCs, clues, XP) is saved to JSON files in `data/campaigns/` and persists across bot restarts.

**Q: How long does the conversation history last?**
A: The bot keeps the last 80 messages of conversation history for Claude context. Older messages are trimmed, but the `!recap` command can summarize what happened.

**Q: How do I change the Claude model?**
A: Set `CLAUDE_MODEL` in your `.env` file. For example, `CLAUDE_MODEL=claude-sonnet-4-20250514` for Sonnet or `CLAUDE_MODEL=claude-opus-4-20250514` for Opus (higher quality, higher cost).

**Q: The bot isn't responding to commands.**
A: Check that:
1. **Message Content Intent** is enabled in the Discord Developer Portal
2. Your bot has **Send Messages**, **Read Message History**, **Create Public Threads**, and **Send Messages in Threads** permissions in the channel
3. The `.env` file has the correct tokens
4. The Command Prompt window running the bot is still open

**Q: Can two campaigns run at the same time?**
A: Yes — campaigns are per-channel. Different channels can have different campaigns running simultaneously. Each campaign gets its own thread when started.

**Q: The bot isn't creating threads — what's wrong?**
A: The bot needs **Create Public Threads**, **Send Messages in Threads**, and **Manage Threads** permissions. Check your bot's permissions in Server Settings > Roles. If threads can't be created, the bot falls back to playing in the main channel.

**Q: Can I play without threads?**
A: Yes. If the bot lacks thread permissions, it will run the campaign directly in the channel. Everything works the same — you just don't get the organizational benefit of a dedicated thread.

**Q: Why does `!commands` send a DM instead of posting in the channel?**
A: To keep the game thread clean. The full help text is 30+ lines. If your DMs are disabled, the bot falls back to posting in the channel.

**Q: What are campaign phases?**
A: Campaigns go through these phases:
1. **Pitching** — Players propose and vote on concepts (`!pitch`, `!vote`)
2. **Setup** — Players create characters (`!createchar`), DM sets options (`!setlevel`)
3. **Active** — Adventure is live, all gameplay commands work

You skip Pitching if you use `!newcampaign <name>` or `!suggestcampaign` directly.

**Q: How much does the API cost?**
A: With prompt caching enabled, costs are very low. A typical 2-hour session with 50 exchanges costs roughly $0.50-$2.00 on Sonnet depending on response length. The caching saves ~90% on input tokens after the first call.

**Q: Can I add homebrew races or classes?**
A: Yes — add them to `bot/data/races.py`, `bot/data/classes.py`, or `bot/data/backgrounds.py`. Follow the same dictionary format as the existing entries.

**Q: Can I add custom consumables or armor?**
A: Yes — add consumables to `bot/data/consumables.py` and armor to `bot/data/armor.py`. Follow the existing dictionary format. Consumables support healing effects (`effect_type: "heal"`) and condition removal (`effect_type: "remove_condition"`).
