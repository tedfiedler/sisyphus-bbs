"""What day it is on the mountain.

A game day turns over at local midnight in ``config.TZ`` (the server's zone
when unset). Everything that cares about the date asks here, so tests move
time by replacing ``now`` rather than by sleeping.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from lib import config


def now() -> datetime:
    """The current moment in the game's time zone."""
    if config.TZ:
        return datetime.now(ZoneInfo(config.TZ))
    return datetime.now().astimezone()


def today() -> date:
    return now().date()
