"""D&D 5e spell lists by class for character creation.

Only cantrips and 1st-level spells (for starting characters).
"""

CLASS_SPELL_LISTS = {
    'Bard': {
        'cantrips': [
            'Blade Ward', 'Dancing Lights', 'Friends', 'Light', 'Mage Hand',
            'Mending', 'Message', 'Minor Illusion', 'Prestidigitation',
            'Thunderclap', 'True Strike', 'Vicious Mockery',
        ],
        'level_1': [
            'Animal Friendship', 'Bane', 'Charm Person', 'Comprehend Languages',
            'Cure Wounds', 'Detect Magic', 'Disguise Self', 'Faerie Fire',
            'Feather Fall', 'Healing Word', 'Heroism', 'Identify',
            'Illusory Script', 'Longstrider', 'Silent Image', 'Sleep',
            'Speak with Animals', "Tasha's Hideous Laughter", 'Thunderwave',
            'Unseen Servant',
        ],
    },
    'Cleric': {
        'cantrips': [
            'Guidance', 'Light', 'Mending', 'Resistance', 'Sacred Flame',
            'Spare the Dying', 'Thaumaturgy',
        ],
        'level_1': [
            'Bane', 'Bless', 'Command', 'Create or Destroy Water',
            'Cure Wounds', 'Detect Evil and Good', 'Detect Magic',
            'Detect Poison and Disease', 'Guiding Bolt', 'Healing Word',
            'Inflict Wounds', 'Protection from Evil and Good',
            'Purify Food and Drink', 'Sanctuary', 'Shield of Faith',
        ],
    },
    'Druid': {
        'cantrips': [
            'Druidcraft', 'Guidance', 'Mending', 'Poison Spray',
            'Produce Flame', 'Resistance', 'Shillelagh', 'Thorn Whip',
        ],
        'level_1': [
            'Animal Friendship', 'Charm Person', 'Create or Destroy Water',
            'Cure Wounds', 'Detect Magic', 'Detect Poison and Disease',
            'Entangle', 'Faerie Fire', 'Fog Cloud', 'Goodberry',
            'Healing Word', 'Jump', 'Longstrider', 'Purify Food and Drink',
            'Speak with Animals', 'Thunderwave',
        ],
    },
    'Sorcerer': {
        'cantrips': [
            'Acid Splash', 'Blade Ward', 'Chill Touch', 'Dancing Lights',
            'Fire Bolt', 'Friends', 'Light', 'Mage Hand', 'Mending',
            'Message', 'Minor Illusion', 'Poison Spray', 'Prestidigitation',
            'Ray of Frost', 'Shocking Grasp', 'True Strike',
        ],
        'level_1': [
            'Burning Hands', 'Charm Person', 'Chromatic Orb', 'Color Spray',
            'Comprehend Languages', 'Detect Magic', 'Disguise Self',
            'Expeditious Retreat', 'False Life', 'Feather Fall', 'Fog Cloud',
            'Jump', 'Mage Armor', 'Magic Missile', 'Ray of Sickness',
            'Shield', 'Silent Image', 'Sleep', 'Thunderwave', 'Witch Bolt',
        ],
    },
    'Warlock': {
        'cantrips': [
            'Blade Ward', 'Chill Touch', 'Eldritch Blast', 'Friends',
            'Mage Hand', 'Minor Illusion', 'Poison Spray', 'Prestidigitation',
            'True Strike',
        ],
        'level_1': [
            'Armor of Agathys', 'Arms of Hadar', 'Charm Person',
            'Comprehend Languages', 'Expeditious Retreat', 'Hellish Rebuke',
            'Hex', 'Illusory Script', 'Protection from Evil and Good',
            'Unseen Servant', 'Witch Bolt',
        ],
    },
    'Wizard': {
        'cantrips': [
            'Acid Splash', 'Blade Ward', 'Chill Touch', 'Dancing Lights',
            'Fire Bolt', 'Friends', 'Light', 'Mage Hand', 'Mending',
            'Message', 'Minor Illusion', 'Poison Spray', 'Prestidigitation',
            'Ray of Frost', 'Shocking Grasp', 'True Strike',
        ],
        'level_1': [
            'Alarm', 'Burning Hands', 'Charm Person', 'Chromatic Orb',
            'Color Spray', 'Comprehend Languages', 'Detect Magic',
            'Disguise Self', 'Expeditious Retreat', 'False Life',
            'Feather Fall', 'Find Familiar', 'Fog Cloud', 'Grease',
            'Identify', 'Illusory Script', 'Jump', 'Longstrider',
            'Mage Armor', 'Magic Missile', 'Protection from Evil and Good',
            'Ray of Sickness', 'Shield', 'Silent Image', 'Sleep',
            "Tasha's Hideous Laughter", "Tenser's Floating Disk",
            'Thunderwave', 'Unseen Servant', 'Witch Bolt',
        ],
    },
    # Paladins and Rangers get spells at level 2+
    'Paladin': {
        'cantrips': [],
        'level_1': [
            'Bless', 'Command', 'Compelled Duel', 'Cure Wounds',
            'Detect Evil and Good', 'Detect Magic', 'Detect Poison and Disease',
            'Divine Favor', 'Heroism', 'Protection from Evil and Good',
            'Purify Food and Drink', 'Searing Smite', 'Shield of Faith',
            'Thunderous Smite', 'Wrathful Smite',
        ],
    },
    'Ranger': {
        'cantrips': [],
        'level_1': [
            'Alarm', 'Animal Friendship', 'Cure Wounds', 'Detect Magic',
            'Detect Poison and Disease', 'Ensnaring Strike', 'Fog Cloud',
            'Goodberry', "Hail of Thorns", 'Hunter\'s Mark', 'Jump',
            'Longstrider', 'Speak with Animals',
        ],
    },
}

# How many spells each class gets at level 1
CLASS_STARTING_SPELLS = {
    'Bard': {'cantrips': 2, 'spells': 4, 'spell_type': 'known'},
    'Cleric': {'cantrips': 3, 'spells': 'prepared', 'spell_type': 'prepared'},
    'Druid': {'cantrips': 2, 'spells': 'prepared', 'spell_type': 'prepared'},
    'Sorcerer': {'cantrips': 4, 'spells': 2, 'spell_type': 'known'},
    'Warlock': {'cantrips': 2, 'spells': 2, 'spell_type': 'known'},
    'Wizard': {'cantrips': 3, 'spells': 6, 'spell_type': 'spellbook'},
    'Paladin': {'cantrips': 0, 'spells': 0, 'spell_type': 'none'},
    'Ranger': {'cantrips': 0, 'spells': 0, 'spell_type': 'none'},
}


def get_spell_list(char_class: str) -> dict | None:
    """Get the spell list for a class."""
    return CLASS_SPELL_LISTS.get(char_class)


def get_starting_spell_counts(char_class: str) -> dict | None:
    """Get how many cantrips/spells a class starts with."""
    return CLASS_STARTING_SPELLS.get(char_class)


def calculate_prepared_count(char_class: str, level: int, wis_mod: int = 0, int_mod: int = 0) -> int:
    """Calculate how many spells a prepared caster can prepare."""
    if char_class in ('Cleric', 'Druid'):
        return max(1, wis_mod + level)
    elif char_class == 'Wizard':
        return max(1, int_mod + level)
    elif char_class == 'Paladin':
        return max(1, wis_mod + (level // 2))
    return 0
