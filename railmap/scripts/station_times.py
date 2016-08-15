"""
Script which finds the time taken to reach all stations from a specified
station.
"""

import logging
import os.path
import datetime

from argparse import ArgumentParser

from railmap.route_planner import load_schedule


def main():
    parser = ArgumentParser(
        description="Read Timetable Information Service (TTIS) data and "
                    "output the journey times from one station to all others.")
    
    parser.add_argument("ttis_files",
                        help="The name of one of the TTIS data files (.mca, "
                             ".msn, .flf), the names of the others will be "
                             "inferred.")
    parser.add_argument("three_alpha_code", nargs="+",
                        help="The three-alpha-code of the station to start "
                             "at. Give several to find paths from several "
                             "stations.")
    
    parser.add_argument("--datetime", "-d", type=int, nargs=5, action="append",
                        default=[],
                        metavar=("YYYY", "MM", "DD", "HH", "MM"),
                        help="The time/date to start at. May be given "
                             "multiple times to test several journeys.")
    
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show verbose status during processing.")
    
    args = parser.parse_args()
    
    # Handle arguments
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    
    if not args.datetime:
        now = datetime.datetime.now()
        args.datetime.append([now.year, now.month, now.day, now.hour, now.minute])
    
    base, ext = os.path.splitext(args.ttis_files)
    
    # Load schedule
    schedule = load_schedule("{}.mca".format(base),
                             "{}.msn".format(base),
                             "{}.flf".format(base))
    
    
    # Output journey times
    print("start_station,start_time,station,duration")
    for three_alpha_code in args.three_alpha_code:
        for year, month, day, hour, minute in args.datetime:
            # Get TIPLOC code
            tiploc_code = None
            for tiploc in schedule.tiplocs.values():
                if tiploc.three_alpha_code == three_alpha_code:
                    tiploc_code = tiploc.code
                    break
            
            # Generate routes
            start = datetime.datetime(year, month, day, hour, minute)
            schedule.plan_route(tiploc_code, None, start)
            for tiploc in schedule.tiplocs.values():
                if tiploc.visited and tiploc.three_alpha_code:
                    print("{},{},{},{}".format(three_alpha_code,
                                               start,
                                               tiploc.three_alpha_code,
                                               (tiploc.visited - start).total_seconds()))
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
