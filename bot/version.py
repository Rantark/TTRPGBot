"""
Version information for TTRPGBot
"""

__version__ = "1.0.0"
__version_info__ = {
    'major': 1,
    'minor': 0,
    'patch': 0
}

# Update this with each release
RELEASE_NOTES = """
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
- Auto-update checker
- Discord restart/update commands
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
