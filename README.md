# D&D 5e Discord Bot — AI Dungeon Master

A production-ready Discord bot for playing D&D 5th Edition where Claude (via Anthropic API) serves as the Dungeon Master. Full character creation, dice rolling, combat management, and AI-driven storytelling.

## Quick Start

### 1. Prerequisites
- Python 3.8+
- A [Discord bot token](https://discord.com/developers/applications)
- An [Anthropic API key](https://console.anthropic.com/)

### 2. Install
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your tokens
```

### 3. Run
```bash
python -m bot.main
```

### 4. Deploy to Railway
The included `Procfile` works with Railway.app out of the box. Set `DISCORD_TOKEN` and `ANTHROPIC_API_KEY` as environment variables.

## How It Works

1. **DM creates a campaign** with `!newcampaign` — they can name it directly or use the pitch/vote system
2. **Players create characters** with `!createchar` — interactive step-by-step with full PHB races, classes, backgrounds, and ability score methods
3. **DM starts the campaign** with `!startcampaign` — Claude generates an opening narration
4. **Players play** using `!action`, `!ic`, `!roll`, `!check` etc. — Claude responds as the DM
5. **Combat** is managed with initiative, turn order, and turn locking

## Command Reference

Use `!commands` in Discord to see the full command list.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Discord bot token |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `CLAUDE_MODEL` | No | Model ID (default: `claude-sonnet-4-20250514`) |
| `COMMAND_PREFIX` | No | Bot command prefix (default: `!`) |

## Discord Bot Permissions

Your bot needs these permissions/intents:
- **Message Content Intent** (enabled in Developer Portal)
- **Server Members Intent** (enabled in Developer Portal)
- Send Messages, Read Message History, Embed Links
