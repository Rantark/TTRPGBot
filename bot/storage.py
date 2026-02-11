"""Persistent JSON storage for campaigns."""

import json
import os
import logging

from bot.models.campaign import Campaign

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "campaigns")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _campaign_path(channel_id: str) -> str:
    return os.path.join(DATA_DIR, f"campaign_{channel_id}.json")


def save_campaign(campaign: Campaign):
    """Save a campaign to disk.

    If the campaign has a thread_id, also saves under that ID so commands
    in the thread can find it directly without scanning.
    """
    _ensure_dir()
    path = _campaign_path(campaign.channel_id)
    try:
        data = campaign.to_dict()
        # Write atomically via temp file
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)

        # Also save under thread_id for direct lookup from thread commands
        if campaign.thread_id and campaign.thread_id != campaign.channel_id:
            thread_path = _campaign_path(campaign.thread_id)
            tmp_path = thread_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, thread_path)

        # Also save under forum_post_id for direct lookup from forum post commands
        if campaign.forum_post_id and campaign.forum_post_id != campaign.channel_id:
            forum_path = _campaign_path(campaign.forum_post_id)
            tmp_path = forum_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, forum_path)
    except Exception:
        logger.exception(f"Failed to save campaign for channel {campaign.channel_id}")


def load_campaign(channel_id: str) -> Campaign | None:
    """Load a campaign from disk.

    Works for both regular channel IDs and thread IDs since campaigns
    with threads are saved under both their channel_id and thread_id.
    """
    path = _campaign_path(channel_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return Campaign.from_dict(data)
    except Exception:
        logger.exception(f"Failed to load campaign for channel {channel_id}")
        return None


def delete_campaign(channel_id: str):
    """Delete a campaign file."""
    path = _campaign_path(channel_id)
    if os.path.exists(path):
        os.remove(path)


def list_campaigns() -> list[str]:
    """Return list of channel IDs with saved campaigns."""
    _ensure_dir()
    ids = []
    for fname in os.listdir(DATA_DIR):
        if fname.startswith("campaign_") and fname.endswith(".json"):
            channel_id = fname[len("campaign_"):-len(".json")]
            ids.append(channel_id)
    return ids


# ── Guild settings (per-server config saved to disk) ──

SETTINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "settings")


def _settings_path(guild_id: str) -> str:
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    return os.path.join(SETTINGS_DIR, f"guild_{guild_id}.json")


def load_guild_settings(guild_id: str) -> dict:
    """Load settings for a guild. Returns empty dict if none exist."""
    path = _settings_path(guild_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        logger.exception(f"Failed to load settings for guild {guild_id}")
        return {}


def save_guild_settings(guild_id: str, settings: dict):
    """Save settings for a guild."""
    path = _settings_path(guild_id)
    try:
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        logger.exception(f"Failed to save settings for guild {guild_id}")
