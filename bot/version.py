"""
Version information for TTRPGBot
"""

__version__ = "1.4.3"
__version_info__ = {
    'major': 1,
    'minor': 4,
    'patch': 3
}

# Update this with each release
RELEASE_NOTES = """
**Version 1.4.3** - February 15, 2026
- New !cc restart — restart character creation from any step without deleting
- Auto-reroll stat rolls if no score is 15+ (up to 10 rerolls)
- Restart hint shown at the start of character creation

**Version 1.4.2** - February 15, 2026
- New !randompitch command — DM can let fate pick a random pitch
- New !deletepitch command — pitch authors or DM can remove pitches by number

**Version 1.4.1** - Feubary 13 2026
- Added a line in the initial prompt to protect children from being harmed in the campaign

**Version 1.4.0** - February 13, 2026
- History summarization: old messages are summarized before trimming, preserving story context
- Rolling "Story So Far" summary injected into DM system prompt for continuity
- Campaign pace modes: !setpace async (no timeout) or live (30-min AFK timeout)
- AFK background checker auto-passes idle players in LIVE pace campaigns
- New !afk command to mark yourself AFK (auto-pass until you act)
- Fixed !ask polluting conversation history — rules Q&A now uses isolated API calls

**Version 1.3.1** - February 13, 2026
- Emoji reaction selection for character creation — click to choose instead of typing
- Gender (♂️♀️⚧️), ability method (🎲📊🧮), confirm (✅❌) use themed emojis
- Race, class, background, equipment, weapons, and spells use numbered reactions (1️⃣-🔟)
- Falls back to text input for lists with more than 10 options
- !cc text input still works at every step (backward compatible)

**Version 1.3.0** - February 12, 2026
- Multiple concurrent campaigns: each gets its own forum post, all independent
- Campaign tracking moved to forum post thread ID as primary key
- New !forceend command lets admins end campaigns when DM is absent
- !newcampaign blocked inside threads (must use a regular channel)
- Improved campaign cleanup with set-based save file deletion

**Version 1.2.1** - February 12, 2026
- Full error tracebacks now sent to Discord instead of just console logs
- New !debugforum command shows forum config, channel access, and bot permissions
- Better error messages for forum post creation failures

**Version 1.2.0** - February 11, 2026
- Admin commands: !restart, !update, !shutdown, !checkupdate now use Discord admin permissions
- No longer requires BOT_OWNER_ID — any server admin can manage the bot
- Fixed cog naming issue (bot_info → show_bot_info) that could cause loading errors

**Version 1.1.1** - February 11, 2026
- Forum post support: !startcampaign auto-creates forum posts when CAMPAIGN_FORUM_ID is set
- Each campaign gets its own organized forum post for gameplay
- Falls back to threads/channels if forum not configured or permissions missing
- Campaign data saved under forum post ID for direct command lookup

**Version 1.1.0** - February 10, 2026
- Revamped !attack command — specify weapon for auto attack + damage rolls
- Manual dice support: !attack <weapon> <atk_dice> <dmg_dice>
- New !spellattack command for spell attack + damage rolls (aliases: !sa, !spellatk)
- Critical hits automatically roll extra damage dice
- Finesse weapons use higher of STR/DEX
- Auto-update & restart system with wrapper scripts
- New commands: !ping, !version, !botinfo, !checkupdate, !restart, !update, !shutdown
- Background update checker (24h GitHub polling)

**Version 1.0.0** - February 10, 2026
- Initial release
- Full D&D 5e character creation (all PHB races, classes, backgrounds)
- Claude AI Dungeon Master
- Combat system with initiative tracking
- RP scene coordination with action queuing
- Inventory and gold tracking
- Spell slot tracking for spellcasters
- Hit dice and rest system
- Prompt caching for cost optimization
"""

def get_version() -> str:
    """Get the current version string"""
    return __version__

def get_version_info() -> dict:
    """Get detailed version information"""
    return {
        'version': __version__,
        'version_info': __version_info__,
        'release_notes': RELEASE_NOTES
    }
