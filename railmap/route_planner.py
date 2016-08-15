"""A simple (and not entirely correct) route planning system for the schedule
data from the Timetable Information Service (TTIS) data and other data files.
"""

import logging
import datetime

from heapq import heappush, heappop

from collections import namedtuple, defaultdict

from railmap.cif import parse_mca, parse_msn
from railmap.flf import parse_flf

from railmap.cif.mca import \
    RecordIdentity, STPIndicator, TransactionType, AssociationCateogry, \
    Activity

from railmap.cif.msn import \
    RecordType

logger = logging.getLogger(__name__)

class Validity(object):
    """Defines the regularity with which a train service runs."""
    
    __slots__ = ["runs_from", "runs_to", "days_run"]
    
    def __init__(self, runs_from, runs_to, days_run):
        """Create a Validity.
        
        Parameters
        ----------
        runs_from : :py:class:`datetime.date`
            First day on which the segment may be valid.
        runs_to : :py:class:`datetime.date`
            Last day on which the segment may be valid.
        days_run : int
            Bitmap indicating which days the service runs. Bit-0 is '1' if the
            service runs on Mondays, and so on.
        """
        self.runs_from = runs_from
        self.runs_to = runs_to
        self.days_run = days_run
    
    def valid_at(self, now):
        """Test whether a datetime.date is valid (True) or not (False)."""
        return (self.runs_from <= now <= self.runs_to and
                self.days_run & (1<<now.weekday()))
    
    def next_valid_at(self, now):
        """Return the datetime.date which is next valid or None otherwise."""
        # Past the end of the schedule? Give up.
        if now > self.runs_to:
            return None
        
        # Before the start of the schedule? Skip onwards
        if now < self.runs_from:
            now = self.runs_from
        
        # Advance one day at a time until either the validity runs out or we
        # reach a weekday where we're valid.
        while (self.runs_from <= now <= self.runs_to and
               not self.days_run & (1<<now.weekday())):
            now += datetime.timedelta(days=1)
        
        if self.valid_at(now):
            return now
        else:
            return None
    
    def __repr__(self):
        return "{}({}, {}, {})".format(
            self.__class__.__name__,
            repr(self.runs_from),
            repr(self.runs_to),
            bin(self.days_run),
        )


class Segment(object):
    """A segment of a timetabled service, or a transfer, between two
    TIPLOCs.
    
    An edge in the timetable graph.
    """
    
    __slots__ = ["tiploc", "destinations", "set_down", "take_up"]
    
    def __init__(self, tiploc, destinations=None, set_down=True, take_up=True):
        """Create a segment (not intended for direct use!).
        
        Parameters
        ----------
        tiploc : :py:class:`.TIPLOC`
            The TIPLOC that this segment is located on.
        destinations : [(:py:class:`.Segment`, validity), ...]
            The list of segments which this segment directly connects to,
            including the validity of that segment.
        set_down : bool
            True if passengers may disembark when arriving at this segment.
        take_up : bool
            True if passengers may board when arriving at this segment.
        """
        self.tiploc = tiploc
        self.destinations = destinations if destinations is not None else []
        self.set_down = set_down
        self.take_up = take_up
    
    def next_departure(self, now):
        """Find out what time this service next visits its destinations.
        
        Parameters
        ----------
        now : :py:class:`datetime.datetime`
            The current date/time.
        
        Returns
        -------
        datetime or None
        """
        raise NotImplementedError()
    
    def next_segments(self, now):
        """Find out what time we will arrive at the destinations of this
        segment given the current time.
        
        Parameters
        ----------
        now : :py:class:`datetime.datetime`
            The current date/time.
        
        Yields
        -------
        (datetime, segment)
        """
        raise NotImplementedError()
    
    def __repr__(self):
        return "<{} {} -> {}{}>".format(
            self.__class__.__name__,
            self.tiploc.code,
            ", ".join(d[0].tiploc.code for d in self.destinations),
            " (pass-through)" if not self.set_down and not self.take_up else "",
        )
    
    def __lt__(self, other):
        """Arbitrary ordering to allow this to be inserted into a heap."""
        return id(self) < id(other)


class RailSegment(Segment):
    """A segment of a timetabled service made by rail."""
    
    __slots__ = ["arrival", "departure"]
    
    def __init__(self, arrival=None, departure=None, *args, **kwargs):
        """Create a TransferSegment.
        
        Parameters
        ----------
        arrival : :py:class:`datetime.time` or None
            The time at which the train arrives at this segment or None if this
            is the starting point.
        departure : :py:class:`datetime.time` or None
            The time at which the train departs from this segment to the next
            or None if this is the endpoint.
        *remaining arguments*
            As for :py:class:`.Segment`.
        """
        super(RailSegment, self).__init__(*args, **kwargs)
        self.arrival = arrival
        self.departure = departure
    
    def next_departure(self, now):
        # Give up if no timing information is available
        if self.departure is None or self.departure == datetime.time(0, 0, 0):
            return None
        
        # If time is in the past, we'll have to try tomorrow
        if self.departure < now.time():
            now += datetime.timedelta(days=1)
        
        # Find the next day this service runs
        next_valid = min((validity.next_valid_at(now.date())
                          for dest, validity in self.destinations
                          if validity.next_valid_at(now.date()) is not None),
                         default=None)
        
        if next_valid:
            return datetime.datetime(year=next_valid.year,
                                     month=next_valid.month,
                                     day=next_valid.day,
                                     hour=self.departure.hour,
                                     minute=self.departure.minute,
                                     second=self.departure.second)
        else:
            return None
    
    def next_segments(self, now):
        for destination, validity in self.destinations:
            # If arrival time is unknown, just use current time
            if destination.arrival == datetime.time(0, 0, 0) or destination.arrival is None:
                arrival_time = now.time()
            else:
                arrival_time = destination.arrival
            
            # Have we missed this link for the day? If so, move on to the next
            # day.
            if arrival_time < now.time():
                now_date = now.date() + datetime.timedelta(days=1)
            else:
                now_date = now.date()
            
            # Find the day where this service is next valid (in case it doesn't
            # run today)
            now_date = validity.next_valid_at(now_date)
            
            # If this segment won't run again, just stop
            if now_date is None:
                continue
            
            arrival = datetime.datetime(year=now_date.year,
                                        month=now_date.month,
                                        day=now_date.day,
                                        hour=arrival_time.hour,
                                        minute=arrival_time.minute,
                                        second=arrival_time.second)
            
            yield (arrival, destination)
    
    def __repr__(self):
        return "<{} {} ({}) -> {} ({}){}>".format(
            self.__class__.__name__,
            self.tiploc.code,
            self.arrival,
            ", ".join(d[0].tiploc.code for d in self.destinations),
            self.departure,
            " (pass-through)" if not self.set_down and not self.take_up else "",
        )


class TransferSegment(Segment):
    """A segment of a timetabled service made by some other transfer method."""
    
    __slots__ = ["duration"]
    
    def __init__(self, duration=None, *args, **kwargs):
        """Create a TransferSegment.
        
        Parameters
        ----------
        duration : int or None
            Time taken for the transfer (minutes), or None if the terminus of a
            transfer.
        *remaining arguments*
            As for :py:class:`.Segment`.
        """
        super(TransferSegment, self).__init__(*args, **kwargs)
        self.duration = duration
    
    def next_departure(self, now):
        return now
    
    def next_segments(self, now):
        for dest, validity in self.destinations:
            yield (now + datetime.timedelta(seconds=self.duration * 60), dest)


class TIPLOC(object):
    """A TIPLOC or, approximately, a station.
    
    A node in the timetable graph.
    """
    
    __slots__ = ["code", "three_alpha_code", "segments", "change_time",
                 "same_station", "visited"]
    
    def __init__(self, code, three_alpha_code=None, segments=None,
                 change_time=0, same_station=None, visited=None):
        """Create a new TIPLOC.
        
        All parameters can be changed later by setting the same-named
        attribute.
        
        Parameters
        ----------
        code : str
            The TIPLOC code.
        three_alpha_code : str or None
            The three-alpha station code, if known.
        segments : [:py:class:`.Segment`, ...]
            The list of segments which pass through/start/terminate at this
            TIPLOC.
        change_time : int
            Time (minutes) to allow for transferring between different trains.
            Defaults to 0 if unknown.
        same_station : set([:py:class:`.TIPLOC`, ...])
            A set identifying TIPLOCs which are part of the same station.
        visited : anything
            A user-defined flag for graph search purposes
        """
        self.code = code
        self.three_alpha_code = three_alpha_code
        self.segments = segments if segments is not None else []
        self.change_time = change_time
        self.same_station = same_station if same_station is not None else set([self])
        self.visited = visited
    
    def __repr__(self):
        return "<{} {} ({}) {} segments>".format(
            self.__class__.__name__,
            self.code,
            self.three_alpha_code,
            len(self.segments),
        )
    
    def __lt__(self, other):
        """Arbitrary ordering to allow this to be inserted into a heap."""
        return id(self) < id(other)


def time_to_datetime(datetime_now, then):
    """Convert a datetime.time into the first datetime.datetime after
    datetime_now.
    """
    datetime_day = datetime.datetime(datetime_now.year,
                                     datetime_now.month,
                                     datetime_now.day)
    
    then_sec = (then.hour * 60 * 60) + (then.minute * 60) + then.second
    then_delta = datetime.timedelta(seconds=then_sec)
    
    if datetime_now.time() <= then:
        # Same day
        return datetime_day + then_delta
    else:
        # Next day
        return datetime_day + datetime.timedelta(days=1) + then_delta


class Schedule(object):
    """A schedule graph which may be queried for routes.
    """
    
    def __init__(self, tiplocs=None):
        """Create a schedule.
        
        Parameters
        ----------
        tiplocs : {tiploc_code: :py:class:`.TIPLOC`, ...} or None
            If None (the default) the tiploc list is set to an empty list. Maps
            TIPLOC codes to their associated object.
        """
        self.tiplocs = tiplocs if tiplocs is not None else {}
        
        self.visit_id = 0
    
    def __repr__(self):
        return "<{} {} tiplocs>".format(
            self.__class__.__name__,
            len(self.tiplocs),
        )
    
    def plan_route(self, start_tiploc_code, end_tiploc_code, start_time):
        """Find a route (if possible) between the two specified TIPLOCs.
        
        Parameters
        ----------
        start_tiploc_code : str
            The station TIPLOC code to start from.
        end_tiploc_code : str
            The station TIPLOC code to attempt to reach.
        start_time : :py:class:`datetime.datetime`
            The date/time at which the journey commences.
        
        Returns
        -------
        None or (end_time, [Segment, ...])
        """
        start_tiploc = self.tiplocs[start_tiploc_code]
        end_tiploc = self.tiplocs[end_tiploc_code]
        
        # Produce a new unique ID to write to stations to indicate they've been
        # visited during this planning process.
        self.visit_id += 1
        
        # A queue of TIPLOCs to visit, the time at which the visit occurred and
        # the list of segments visited thus far to reach that station
        #  (datetime, TIPLOC, segments_used)
        # XXX: Should be a priority queue!
        to_visit = []
        heappush(to_visit, (start_time, start_tiploc, []))
        
        while to_visit:
            now, tiploc, segments_used = heappop(to_visit)
            
            # Is this our destination?
            if tiploc == end_tiploc:
                # Terminate if we are allowed to get off only!
                if not segments_used or segments_used[-1].set_down:
                    return (now, segments_used)
            
            # Are we already on a sequence of segments, if so, consider staying
            # on it
            if segments_used:
                cur_segment = segments_used[-1]
                for next_time, next_segment in cur_segment.next_segments(now):
                    heappush(to_visit, (next_time,
                                        next_segment.tiploc,
                                        segments_used + [next_segment]))
            else:
                cur_segment = None
            
            # Consider changing train if we've not changed at this station
            # before and the current segment can set us down here.
            for tiploc in tiploc.same_station:
                if (tiploc.visited != self.visit_id and
                        (cur_segment is None or cur_segment.set_down)):
                    # Mark station as visited
                    tiploc.visited = self.visit_id
                    
                    # Allow time to change platform etc. if already on something
                    if cur_segment is not None:
                        after_change = now + datetime.timedelta(seconds=tiploc.change_time * 60)
                    else:
                        after_change = now
                    
                    # Consider all segments which are taking up passengers
                    for segment in tiploc.segments:
                        next_departure = segment.next_departure(after_change)
                        if segment.take_up and next_departure is not None:
                            for next_time, next_segment in segment.next_segments(next_departure):
                                heappush(to_visit, (next_time,
                                                    next_segment.tiploc,
                                                    segments_used + [segment, next_segment]))


_DivideJoinEvent = namedtuple("_DivideJoinEvent",
                              "main_train_uid,associated_train_uid,location,validity")


def _load_mca_file(schedule, filename):
    """Internal use. Loads an MCA (CIF timetable) into a schedule."""
    # Accumulate a list of train divison events and join events as
    # '_DivideJoinEvent's. Pulled out when parsing association entries
    joins_and_divisions = []
    
    # A mapping {(train_uid, tiploc_code): RailSegment, ...}
    segments = {}
    
    # The current train details
    cur_train_uid = None
    cur_validity = None
    
    # The last segment to be created
    last_segment = None
    
    with open(filename, "r") as f:
        for n, record in enumerate(parse_mca(f)):
            if n % 10000 == 0:
                logger.debug("Parsing MCA record %d", n)
            
            # Parse division and join events for later processing since these
            # proceed the main schedule information.
            if (record.record_identity == RecordIdentity.association and
                  record.stp_indicator != STPIndicator.stp_cancellation):
                if record.transaction_type != TransactionType.new:
                    logger.warning("Unexpected non-new association: %r",
                                   record)
                else:
                    dje = _DivideJoinEvent(
                        record.main_train_uid,
                        record.associated_train_uid,
                        record.association_location,
                        Validity(
                            record.association_start_date,
                            record.association_end_date,
                            record.association_days,
                        ),
                    )
                    
                    joins_and_divisions.append(dje)
            # Start of a (not-cancelled) train schedule entry
            elif (record.record_identity == RecordIdentity.basic_schedule and
                    record.stp_indicator != STPIndicator.stp_cancellation):
                if record.transaction_type != TransactionType.new:
                    logger.warning("Unexpected non-new association: %r",
                                   record)
                else:
                    cur_train_uid = record.train_uid
                    cur_validity = Validity(record.date_runs_from,
                                            record.date_runs_to,
                                            record.days_run)
            # Start of a journey
            elif (record.record_identity == RecordIdentity.origin_location or
                  record.record_identity == RecordIdentity.intermediate_location or
                  record.record_identity == RecordIdentity.terminating_location):
                # Find out if we're setting down or picking up
                set_down = False
                take_up = False
                for activity in record.activity:
                    if activity == Activity.stop_to_set_down_passengers:
                        set_down = True
                    elif activity == Activity.train_finishes:
                        set_down = True
                    elif activity == Activity.stop_to_take_up_passengers:
                        take_up = True
                    elif activity == Activity.train_begins:
                        take_up = True
                    elif activity == Activity.stop_to_take_up_and_set_down_passengers:
                        set_down = True
                        take_up = True
                
                if record.location in schedule.tiplocs:
                    tiploc = schedule.tiplocs[record.location]
                else:
                    tiploc = TIPLOC(record.location)
                    schedule.tiplocs[record.location] = tiploc
                
                segment = RailSegment(tiploc=tiploc,
                                      set_down=set_down,
                                      take_up=take_up,
                                      arrival=((record.public_arrival or
                                                record.scheduled_arrival)
                                               if hasattr(record, "public_arrival")
                                               else None),
                                      departure=((record.public_departure or
                                                  record.scheduled_departure)
                                                 if hasattr(record, "public_departure")
                                                 else None))
                
                # Record the segment (for later join/division edits)
                segments[(cur_train_uid, record.location)] = segment
                
                # Add to the TIPLOC
                tiploc.segments.append(segment)
                
                # If this isn't the start of the journey, add a link from the
                # previous segment to this one
                if record.record_identity != RecordIdentity.origin_location:
                    last_segment.destinations.append((segment, cur_validity))
                
                last_segment = segment
    
    # Process joins/divisions
    for dje in joins_and_divisions:
        main_segment = segments.get((dje.main_train_uid, dje.location))
        associated_segment = segments.get((dje.associated_train_uid, dje.location))
        
        # Skip joins/divisions for which no route is known in the first
        # place...
        if main_segment and associated_segment:
            main_segment.destinations.append((associated_segment, dje.validity))

def _load_msn_file(schedule, filename):
    """Internal use. Loads three-alpha codes and change times from a MSN
    (master station names file) into a schedule."""
    with open(filename, "r") as f:
        tac_to_tiplocs = defaultdict(set)
        
        first = True
        for record in parse_msn(f):
            if first:
                # Skip the first entry (the header)
                first = False
                continue
            elif record.record_type == RecordType.station_details:
                # Assign the three-character code and change time (where known)
                # to the timetable.
                tiploc = schedule.tiplocs.get(record.tiploc_code)
                if tiploc is not None:
                    tac_to_tiplocs[record.three_alpha_code].add(tiploc)
                    tiploc.three_alpha_code = record.three_alpha_code
                    tiploc.change_time = record.change_time
    
    # Add same-station info to TIPLOCs
    for tiplocs in tac_to_tiplocs.values():
        # NB: Adds reference to the same set in all cases
        for tiploc in tiplocs:
            tiploc.same_station = tiplocs
    
def _load_flf_file(schedule, filename):
    """Internal use. Loads non-rail transfers from a fixed link file."""
    tac_to_tiploc = {t.three_alpha_code: t
                     for t in schedule.tiplocs.values()
                     if t.three_alpha_code is not None}
    
    with open(filename, "r") as f:
        first = True
        for record in parse_flf(f):
            src_tiploc = tac_to_tiploc.get(record.origin)
            dst_tiploc = tac_to_tiploc.get(record.destination)
            
            # Silently skip tranfers to/from stations we don't know about
            if src_tiploc and dst_tiploc:
                dst_segment = TransferSegment(tiploc=dst_tiploc,
                                              set_down=True)
                src_segment = TransferSegment(tiploc=src_tiploc,
                                              destinations=[(dst_segment, None)],
                                              duration=record.time,
                                              take_up=True)
                
                dst_tiploc.segments.append(dst_segment)
                src_tiploc.segments.append(src_segment)
    

def load_schedule(mca_filename, msn_filename=None, flf_filename=None):
    """Load a schedule database from published datafiles.
    
    Parameters
    ----------
    mca_filename : str
        The complete timetable in a CIF-format file.
    msn_filename : str or None
        The master station names file. If not present, platform change times
        for all TIPLOCs will be set to 0 and the three-alpha-code field will
        not be populated for any TIPLOCs. Further, TIPLOCs which are part of
        the same station (i.e. have the same three-alpha code) will not be
        related to each other.
    flf_filename : str or None
        The fixed links file defining transfer times between TIPLOCs. If None,
        no transfer links between TIPLOCs will be present, possibly
        disconnecting the network.
        
        If not None, ``msn_filename`` argument must also be provided otherwise
        this data cannot be loaded.
    """
    schedule = Schedule()
    
    _load_mca_file(schedule, mca_filename)
    
    if msn_filename is not None:
        _load_msn_file(schedule, msn_filename)
    
    if flf_filename is not None:
        _load_flf_file(schedule, flf_filename)
    
    return schedule
