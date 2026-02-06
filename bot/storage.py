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
    """Save a campaign to disk."""
    _ensure_dir()
    path = _campaign_path(campaign.channel_id)
    try:
        data = campaign.to_dict()
        # Write atomically via temp file
        tmp_path = path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        logger.exception(f"Failed to save campaign for channel {campaign.channel_id}")


def load_campaign(channel_id: str) -> Campaign | None:
    """Load a campaign from disk. Returns None if not found."""
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
