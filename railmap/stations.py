"""Parse the station information file.
"""

import dbf

from collections import namedtuple


StationRecord = namedtuple("StationRecord", "name,station_code,eastings,northings")


def dbf_to_dict(filename):
    """Read a DBF file containing station information from Network Rail's
    Railway Network Inspire data. Produces a dict which maps from station
    three-alpha-code to its name and location.
    """
    t = dbf.Table(filename)
    
    stations = {}
    
    t.open()
    try:
        for row in t:
            stations[row.stn_code.strip()] = StationRecord(
                row.name.strip(),
                row.stn_code.strip(),
                row.gis_eastin,
                row.gis_northi)
    finally:
        t.close()
    
    return stations
