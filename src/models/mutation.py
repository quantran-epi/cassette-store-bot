from enum import Enum


class IntentType(str, Enum):
    """3-way intent classification for incoming chat messages (D-03)."""

    CREATE = "CREATE"
    SEARCH = "SEARCH"
    MUTATE = "MUTATE"
