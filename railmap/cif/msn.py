"""
CIF data parsing functions for the "MSN" (master station names) file Timetable
Information Service (TTIS) data dumps.
"""

from enum import Enum

from .cif import \
    assert_is, from_ddmmyy, from_hhmmss, several, \
    Field, new_cif_record


def from_dd_mm_yy(s):
    return from_ddmmyy("".join(s.split("/")))


def from_hh_mm_ss(s):
    return from_hhmmss("".join(s.split(".")))


class RecordType(Enum):
    # XXX: The header also has this type... sigh...
    station_details = "A"
    station_alias = "L"
    routeing_groups = "V"


class InterchangeStatus(Enum):
    no = "0"
    small = "1"
    medium = "2"
    large = "3"
    subsidiary_tiploc = "9"

class EstimatedCoordinates(Enum):
    yes = "E"
    no = " "


def assert_record_type(value):
    """Return a field parser which verifies the field contains a specific
    RecordType.
    """
    
    def check(s):
        assert RecordType(s) == value, "{} == {}".format(repr(s), repr(value))
        return RecordType(s)
    
    return check


HeaderRecord = new_cif_record("HeaderRecord",
    Field("record_type", 1, assert_is("A")),
    Field("spaces0", 29, str.strip),
    Field("file_spec_eq", 10, assert_is("FILE-SPEC=")),
    Field("file_spec_version", 8, str.strip),
    Field("date", 8, from_dd_mm_yy),
    Field("space1", 1, str.strip),
    Field("time", 8, from_hh_mm_ss),
    Field("space2", 3, str.strip),
    Field("version", 2, int),
)

StationDetailsRecord = new_cif_record("StationDetailsRecord",
    Field("record_type", 1, assert_record_type(RecordType.station_details)),
    Field("spaces0", 4, str.strip),
    Field("station_name", 30, str.strip),
    Field("interchange_status", 1, InterchangeStatus),
    Field("tiploc_code", 7, str.strip),
    Field("subsidiary_three_alpha_code", 3, None),
    Field("spaces", 3, str.strip),
    Field("three_alpha_code", 3, None),
    Field("easting", 5, int),
    Field("estimated", 1, EstimatedCoordinates),
    Field("northing", 5, int),
    Field("change_time", 2, int),
)

StationAliasRecord = new_cif_record("StationAliasRecord",
    Field("record_type", 1, assert_record_type(RecordType.station_alias)),
    Field("spaces0", 4, str.strip),
    Field("station_name", 30, str.strip),
    Field("spaces1", 1, str.strip),
    Field("alias_name", 30, str.strip),
)

RouteingGroupsRecord = new_cif_record("RouteingGroupsRecord",
    Field("record_type", 1, assert_record_type(RecordType.routeing_groups)),
    Field("spaces0", 4, str.strip),
    Field("group_name", 30, str.strip),
    Field("spaces1", 1, str.strip),
    Field("stations", 40, several(None, size=4)),
)

RECORD_TYPES = {
    RecordType.station_details: StationDetailsRecord,
    RecordType.station_alias: StationAliasRecord,
    RecordType.routeing_groups: RouteingGroupsRecord,
}


def parse_msn(f):
    """Parse a Timetable Information Service (TTIS) MSN (master stations names)
    file, generating each record in turn. Historic data (which the spec.
    suggests ignoring) is not produced.
    """
    first = True
    for line in f:
        if first:
            print(line)
            yield HeaderRecord.from_string(line)
            first = False
        else:
            try:
                record_type = RecordType(line[:1])
            except:
                continue
            
            yield RECORD_TYPES.get(record_type).from_string(line)
