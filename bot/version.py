"""
Version information for TTRPGBot
"""

__version__ = "1.2.0"
__version_info__ = {
    'major': 1,
    'minor': 2,
    'patch': 0
}

# Update this with each release
RELEASE_NOTES = """
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
