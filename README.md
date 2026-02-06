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
  - [Character Creation](#character-creation)
  - [Gameplay (RP Scenes)](#gameplay-rp-scenes)
  - [Dice & Rolls](#dice--rolls)
  - [Combat](#combat)
  - [Progression & Resources](#progression--resources)
  - [Utility](#utility)
- [Character Creation Walkthrough](#character-creation-walkthrough)
- [RP Scene Coordination](#rp-scene-coordination)
- [Combat System](#combat-system)
- [Prompt Caching (Cost Savings)](#prompt-caching-cost-savings)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [FAQ](#faq)

---

## Features at a Glance

- **AI Dungeon Master** — Claude narrates the story, roleplays NPCs, manages encounters, and adjudicates rules
- **Full D&D 5e Character Creation** — All PHB races (with subraces), all 12 classes, 13 backgrounds, 3 ability score methods (roll, standard array, point buy), gender selection
- **Campaign System** — Pitch/vote on concepts, setup phase for character creation, DM-controlled start
- **RP Scene Coordination** — Player actions are queued and bundled so the DM responds to everyone at once (no overlapping storylines)
- **Combat System** — Initiative tracking, turn order, turn locking, NPC management
- **Full Dice Engine** — Standard notation (d20, 2d6+3), ability checks, saving throws, attack rolls with advantage/disadvantage
- **Progression** — Short/long rest, HP management, XP tracking, level up with HP rolls, inspiration, death saves
- **Utility** — AI recaps, investigation clue tracker, NPC journal, private DM whispers
- **`!ask` Command** — Ask the DM rules questions without advancing the story
- **Prompt Caching** — Anthropic prompt caching reduces API costs by up to 90% on repeat calls
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
   - Read Message History
   - Embed Links
   - Use External Emojis
4. Copy the generated URL and open it in your browser
5. Select your server and authorize

### 4. Get Your Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create an API key
3. Paste it as `ANTHROPIC_API_KEY` in your `.env`

---

## Running the Bot

```cmd
python -m bot.main
```

The bot will appear online in your Discord server with the status **"Playing D&D 5e | !commands"**.

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

### Phase 2: Character Creation

Each player runs `!createchar` and follows the interactive prompts (name, gender, race, class, ability scores, background, skills). See [Character Creation Walkthrough](#character-creation-walkthrough) below.

### Phase 3: Adventure Begins

```
DM:     !startcampaign
Bot:    [Claude generates an epic opening narration, addressing each character by name]
```

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

Type `!commands` in Discord to see these categories, or `!commands <category>` for details.

### Campaign Management

| Command | Who | Description |
|---|---|---|
| `!newcampaign [name]` | Anyone | Create a new campaign (you become the DM) |
| `!pitch <title> \| <desc>` | Anyone | Propose a campaign concept |
| `!pitches` | Anyone | View all proposed pitches |
| `!vote <#>` | Anyone | Vote for a pitch |
| `!selectpitch <#>` | DM | Select a pitch and move to setup phase |
| `!startcampaign` | DM | Begin the adventure (requires at least one character) |
| `!endcampaign` | DM | End the campaign permanently |
| `!campaigninfo` | Anyone | View campaign status and player list |

### Character Creation

| Command | Description |
|---|---|
| `!createchar` | Start interactive step-by-step character creation |
| `!cc <choice>` | Make a choice during creation (name, gender, race, class, etc.) |
| `!deletechar` | Delete your character and start over |
| `!sheet` | View your full character sheet |
| `!sheet @player` | View another player's character sheet |

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
| `!pending` | See who hasn't acted yet |
| `!resolve` | *(DM)* Force the round to resolve early |
| `!ask <question>` | Ask the DM a rules question *(does NOT advance the story)* |
| `!ooc <message>` | Out-of-character chat *(not queued, DM doesn't respond)* |

### Dice & Rolls

| Command | Example | Description |
|---|---|---|
| `!roll <notation>` | `!roll 2d6+3` | Roll any dice (d20, 4d6, d8+2, etc.) |
| `!check <skill>` | `!check perception` | Ability/skill check with your modifier |
| `!save <ability>` | `!save DEX` | Saving throw with proficiency if applicable |
| `!attack` | `!attack` | Attack roll (d20 + ability mod + proficiency) |

### Combat

| Command | Who | Description |
|---|---|---|
| `!combatstart` | DM | Begin a combat encounter |
| `!initiative` | Player | Roll initiative (d20 + DEX mod) |
| `!addnpc <name> <roll>` | DM | Add an NPC/monster to initiative |
| `!removenpc <name>` | DM | Remove an NPC from initiative |
| `!begincombat` | DM | Sort initiative and start turn order |
| `!turnorder` | Anyone | Display the current initiative order |
| `!next` | DM | Advance to the next turn |
| `!pass` | Player | Skip your combat turn |
| `!combatend` | DM | End the combat encounter |

### Progression & Resources

| Command | Who | Description |
|---|---|---|
| `!rest short` | Player | Short rest — spend hit dice to heal |
| `!rest long` | Player | Long rest — full HP, restore hit dice |
| `!hp` | Player | View your current HP |
| `!hp +5` / `!hp -3` | Player/DM | Heal or take damage |
| `!xp <amount>` | DM | Award XP to all players |
| `!xp <amount> @player` | DM | Award XP to one player |
| `!levelup` | Player | Level up if you have enough XP |
| `!inspiration @player` | DM | Grant inspiration |
| `!deathsave` | Player | Roll a death saving throw |

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
| `!commands [category]` | Show help menu (campaign, character, gameplay, dice, combat, progression, utility) |

---

## Character Creation Walkthrough

When a player types `!createchar`, the bot walks them through 7 steps:

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

After confirming, the character is saved and ready to play. View anytime with `!sheet`.

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
- `!resolve` — DM can force the round to resolve early (e.g., if someone is AFK)
- `!pass` — Player has nothing to do this round
- `!ooc` — Out-of-character chat, does NOT count as an action
- `!ask` — Rules questions, does NOT count as an action
- During **combat**, the queue system is disabled — actions go directly to Claude per the initiative turn order

---

## Combat System

### Starting Combat

```
DM:      !combatstart
Bot:     COMBAT STARTED! All players: Roll initiative with !initiative
```

### Rolling Initiative

```
Player:  !initiative
Bot:     Thandril rolls initiative: [14] +2 = 16
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

### Ending Combat

```
DM:      !combatend
Bot:     Combat has ended after 4 round(s). Resume roleplay freely!
```

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
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Which Claude model to use |
| `COMMAND_PREFIX` | No | `!` | Bot command prefix |

---

## Project Structure

```
TTRPGBot/
├── bot/
│   ├── main.py              # Entry point — bot setup, event handlers, error handling
│   ├── dm_engine.py          # Claude AI DM — API calls with prompt caching
│   ├── dice.py               # Dice rolling engine (notation parsing, ability checks)
│   ├── storage.py            # Persistent JSON file storage per campaign
│   ├── cogs/
│   │   ├── campaign.py       # !newcampaign, !pitch, !vote, !startcampaign, etc.
│   │   ├── character.py      # !createchar, !cc (7-step interactive flow), !sheet
│   │   ├── gameplay.py       # !action, !ic, !emote, !look, !ask, RP queue system
│   │   ├── combat.py         # !combatstart, !initiative, !next, turn order
│   │   ├── progression.py    # !rest, !hp, !xp, !levelup, !deathsave
│   │   └── utility.py        # !recap, !status, !clues, !npcs, !whisper, !commands
│   ├── models/
│   │   ├── character.py      # Character class — stats, abilities, serialization
│   │   └── campaign.py       # Campaign, CombatState, RP queue state
│   └── data/
│       ├── races.py          # All PHB races + subraces with bonuses and traits
│       ├── classes.py         # All 12 PHB classes with proficiencies
│       ├── backgrounds.py    # 13 PHB backgrounds with skills and features
│       └── rules.py          # Ability scores, skills, proficiency table, XP table
├── data/
│   └── campaigns/            # Auto-created — JSON save files live here
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
2. Your bot has **Send Messages** and **Read Message History** permissions in the channel
3. The `.env` file has the correct tokens
4. The Command Prompt window running the bot is still open

**Q: Can two campaigns run at the same time?**
A: Yes — campaigns are per-channel. Different channels can have different campaigns running simultaneously.

**Q: How much does the API cost?**
A: With prompt caching enabled, costs are very low. A typical 2-hour session with 50 exchanges costs roughly $0.50-$2.00 on Sonnet depending on response length. The caching saves ~90% on input tokens after the first call.

**Q: Can I add homebrew races or classes?**
A: Yes — add them to `bot/data/races.py`, `bot/data/classes.py`, or `bot/data/backgrounds.py`. Follow the same dictionary format as the existing entries.
