"""Data parsing functions for the "FLF" (fixed links) file in Timetable
Information Service (TTIS) data dumps.
"""
import re

from enum import Enum
from collections import namedtuple


class Mode(Enum):
    bus = "BUS"
    tube = "TUBE"
    walk = "WALK"
    ferry = "FERRY"
    metro = "METRO"
    transfer = "TRANSFER"

RECORD_REGEX = re.compile(r"ADDITIONAL LINK: " +
                          (r"(?P<mode>" + 
                           r"|".join(re.escape(m.value) for m in Mode) +
                           r")") +
                          r" BETWEEN "
                          r"(?P<origin>[A-Z]{3})"
                          r" AND "
                          r"(?P<destination>[A-Z]{3})"
                          r" IN +"
                          r"(?P<time>[0-9]+)"
                          r" +MINUTES")

FixedLinkRecord = namedtuple("FixedLinkRecord", "mode,origin,destination,time")


def parse_flf(f):
    """Parse a Timetable Information Service (TTIS) FLF (fixed links) file,
    generating each record in turn.
    """
    for line in f:
        if line == "END\n":
            break
        else:
            match = RECORD_REGEX.match(line)
            assert match, "Unmatched line: {}".format(repr(line))
            yield FixedLinkRecord(Mode(match.group("mode")),
                                  match.group("origin"),
                                  match.group("destination"),
                                  int(match.group("time")))
