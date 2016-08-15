"""Annotate a CSV with station metadata."""

import sys
import datetime

from argparse import ArgumentParser

from railmap.stations import dbf_to_dict
from railmap.cif.msn import parse_msn, StationDetailsRecord


def main():
    parser = ArgumentParser(
        description="Annotate a CSV containing a station three-letter-code "
                    "column with metadata about that station from the Network"
                    "Rail Railway Network Inspire Data and Timetable "
                    "Information Service (TTIS).")
    
    parser.add_argument("--inspire", "-i",
                        help="The .dbf file containing the Network Rail "
                             "Railway Network Inspire station data. If "
                             "provided an 'eastings' and 'northings' column "
                             "will be added to the output.")
    parser.add_argument("--ttis", "-t",
                        help="The .msn file containing the Timetable "
                             "Information Service (TTIS) master station names "
                             "file. If provided an 'interchange_status' and "
                             "'change_time' column will be added to the "
                             "output.")
    
    parser.add_argument("--station-column", "-S", default="station",
                        help="The name of the column in the input containing "
                             "station three-alpha-codes.")
    
    args = parser.parse_args()
    
    # Load inspire data
    if args.inspire:
        inspire_data = dbf_to_dict(args.inspire)
    else:
        inspire_data = {}
    
    # Load TTIS data
    if args.ttis:
        msn_data = {}
        with open(args.ttis, "r") as f:
            for record in parse_msn(f):
                if isinstance(record, StationDetailsRecord):
                    msn_data[record.three_alpha_code] = record
    else:
        msn_data = {}
    
    station_field = None
    for line in sys.stdin:
        if station_field is None:
            fields = line.strip().split(",")
            for num, field in enumerate(fields):
                if field == args.station_column:
                    station_field = num
                    break
            fields += ["eastings", "northings"]
            fields += ["interchange_status", "change_time"]
            sys.stdout.write(",".join(fields) + "\n")
        else:
            fields = line.strip().split(",")
            station = fields[station_field]
            if station in inspire_data:
                data = inspire_data[station]
                fields += [data.eastings or "NA", data.northings or "NA"]
            else:
                fields += ["NA", "NA"]
            if station in msn_data:
                record = msn_data[station]
                fields += [record.interchange_status.value or "NA",
                           record.change_time or "NA"]
            else:
                fields += ["NA", "NA"]
            sys.stdout.write(",".join(map(str, fields)) + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
