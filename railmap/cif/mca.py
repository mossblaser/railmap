"""
CIF data parsing functions for the "MCA" (full timetable) Timetable Information
Service (TTIS) data dumps.
"""

import datetime

from enum import Enum, IntEnum

from .cif import \
    assert_is, from_ddmmyy, from_yymmdd, from_hhmm, several, if_not_blank, \
    Field, new_cif_record


class RecordIdentity(Enum):
    header = "HD"
    tiploc_insert = "TI"
    association = "AA"
    basic_schedule = "BS"
    basic_schedule_extra_details = "BX"
    origin_location = "LO"
    intermediate_location = "LI"
    terminating_location = "LT"
    changes_en_route = "CR"
    trailer = "ZZ"

class TransactionType(Enum):
    new = "N"
    delete = "D"
    revise = "R"

class AssociationDateIndex(Enum):
    standard = "S"
    over_next_midnight = "N"
    over_previous_midnight = "P"

class AssociationType(Enum):
    passenger_use = "P"
    operating_use = "O"

class AssociationCateogry(Enum):
    join = "JJ"
    divide = "VV"
    next = "NP"

class STPIndicator(Enum):
    non_overlay_user = " "
    stp_cancellation = "C"
    new_stp_association = "N"
    permenent_association = "P"
    overlay_of_permenent_association = "O"

class BankHolidayRunning(Enum):
    """A.K.A. BHX"""
    yes = " "
    does_not_run_on_bank_holiday_mondays = "X"
    does_not_run_on_edinburgh_holiday_mondays = "E"
    does_not_run_on_glasgow_holiday_mondays = "G"

class TrainStatus(Enum):
    bus = "B"
    freight = "F"
    passenger_and_parcels = "P"
    ship = "S"
    trip = "T"
    
    stp_passenger_and_parcels = "1"
    stp_freight = "2"
    stp_trip = "3"
    stp_ship = "4"
    stp_bus = "5"

class TrainCategory(Enum):
    # Ordinary passenger trains
    london_underground_or_metro = "OL"
    unadvertised_ordinary_passenger = "OU"
    ordinary_passenger = "OO"
    staff_train = "OS"
    mixed = "OW"
    
    # Express passenger trains
    channel_tunnel = "XC"
    sleeper_europe_night_service = "XD"
    international = "XI"
    motorail = "XR"
    unadvertised_express = "XU"
    express_passenger = "XX"
    sleeper = "XZ"
    
    # Busses
    bus_replacement = "BR"
    bus = "BS"
    
    # Empty coaching stock trains
    ecs = "EE"
    ecs_london_underground_metro = "EL"
    ecs_and_staff = "ES"
    
    # Parcels and postal trains
    postal = "JJ"
    post_office_controlled_parcels = "PM"
    parcels = "PP"
    empty_npccs = "PV"
    
    # Departmental trains
    departmental = "DD"
    civil_engineer = "DH"
    mechanical_and_electrical_engineer = "DI"
    stores = "DQ"
    test = "DT"
    signal_and_telecommunications_engineer = "DY"
    
    # Light locomotives
    locomotive_and_brake_van = "ZB"
    light_locomotive = "ZZ"
    
    # Rail freight distribution
    rfd_automotive_components = "J2"
    rfd_automotive_vehicles = "H2"
    rfd_edible_products = "J3"
    rfd_industrial_minerals = "J4"
    rfd_chemicals = "J5"
    rfd_building_materials = "J6"
    rfd_general_merchendise = "J8"
    rfd_european = "H8"
    rfd_freightliner_contracts = "J9"
    rfd_freightliner_other = "H9"
    
    # Trainload freight
    coal_distributive = "A0"
    coal_electricity_mgr = "E0"
    coal_and_nuclear = "B0"
    metals = "B1"
    aggregates = "B4"
    domestic_and_industrial_waste = "B5"
    building_materials = "B6"
    petrolium_products = "B7"
    
    # Rail freight distribution (channel tunnel)
    rfd_channel_tunnel_mixed_business = "H0"
    rfd_channel_tunnel_intermodal = "H1"
    rfd_channel_tunnel_automotive = "H3"
    rfd_channel_tunnel_contract_services = "H4"
    rfd_channel_tunnel_haulmark = "H5"
    rfd_channel_tunnel_joint_venture = "H6"


class PortionID(Enum):
    """A.K.A. BUSSEC"""
    may_be_used_for_red_star_parcels = "Z"
    portion_id_0 = "0"
    portion_id_1 = "1"
    portion_id_2 = "2"
    portion_id_4 = "4"
    portion_id_8 = "8"

class PowerType(Enum):
    diesel = "D"
    diesel_electric_multiple_unit = "DEM"
    diesel_mechanical_multiple_unit = "DMU"
    electric = "E"
    electro_diesel = "ED"
    emu_plus_d_e_ed_locomotive = "EML"
    electric_multiple_unit = "EMU"
    electric_parcels_unit = "EPU"
    high_speed_train = "HST"
    diesel_shunting_locomotive = "LDS"

class OperatingCharacteristics(Enum):
    vaccum_braked = "B"
    timed_at_100_mph = "C"
    doo_coaching_stock_trains = "D"
    mark_4_coaches = "E"
    trainman_required = "G"
    timed_at_110_mph = "M"
    push_pull_train = "P"
    runs_as_required = "Q"
    air_conditioned_with_pa_system = "R"
    steam_heated = "S"
    runs_to_terminals_yards_as_required = "Y"
    may_convey_traffice_to_sb1c_gauge = "Z"


class TrainClass(Enum):
    first_and_standard_seats = ""
    standard_class_only = "S"

class Sleepers(Enum):
    first_and_standard_class = "B"
    first_class_only = "F"
    standard_class_only = "S"

class Reservations(Enum):
    compulsary = "A"
    for_bikes = "E"
    recommended = "R"
    possible_from_any_station = "S"

class CateringCode(Enum):
    buffet_service = "C"
    restraunt_car_first_class = "F"
    hot_food_available = "H"
    meal_included_first_class = "M"
    wheelchair_only_reservations = "P"
    restraunt = "R"
    trolley_service = "T"

class ServiceBrand(Enum):
    none = " "
    eurostar = "E"
    alphaline = "A"

class AppliccableTimetableCode(Enum):
    """A.K.A. ATS Code"""
    performance_monitored = "Y"
    performance_not_monitored = "N"

class Activity(Enum):
    stops_or_shunts_for_other_trains_to_pass = "A"
    attach_detach_assisting_locomotive = "AE"
    stop_for_banking_locomotive = "BL"
    stop_to_change_trainmen = "C"
    stop_to_set_down_passengers = "D"
    stop_to_detach_vehicles = "-D"
    stop_for_examination = "E"
    national_rail_timetable_data_to_add = "G"
    notional_activity_to_prevent_wtt_timing_columns_merge = "H"
    as_H_where_a_third_column_is_involved = "HH"
    passenger_count_point = "K"
    ticket_collection_and_examination_point = "KC"
    ticket_examination_point = "KE"
    ticket_Examination_Point_1st_class_only = "KF"
    selective_ticket_examination_point = "KS"
    stop_to_change_locomotives = "L"
    stop_not_advertised = "N"
    stop_for_other_operating_reasons = "OP"
    train_locomotive_on_rear = "OR"
    propelling_between_points_shown = "PR"
    stop_when_required = "R"
    reversing_movement_or_driver_changes_ends = "RM"
    stop_for_locomotive_to_run_round_train = "RR"
    stop_for_railway_personnel_only = "S"
    stop_to_take_up_and_set_down_passengers = "T"
    stop_to_attach_and_detach_vehicles = "-T"
    train_begins = "TB"
    train_finishes = "TF"
    detail_consist_for_tops_direct_requested_by_ews = "TS"
    stop_for_tablet_staff_or_token = "TW"
    stop_to_take_up_passengers = "U"
    stop_to_attach_vehicles = "-U"
    stop_for_watering_of_coaches = "W"
    passes_another_train_at_crossing_point_on_single_line = "X"

class Day(IntEnum):
    mon = 0
    tue = 1
    wed = 2
    thu = 3
    fri = 4
    sat = 5
    sun = 6


def assert_record_identity(value):
    """Return a field parser which verifies the field contains a specific
    RecordIdentity.
    """
    
    def check(s):
        assert RecordIdentity(s) == value, "{} == {}".format(repr(s), repr(value))
        return RecordIdentity(s)
    
    return check

def from_hhmmh(s):
    """Convert a "HHMM[H]" format date to a python datetime.time.
    
    Expected input format is either "hhmm " or "hhmmH". The hh and mm fields
    are hours and minutes (as usual). Iff the H is present, the time is
    incremented by 30 seconds.
    """
    h = int(s[0:0+2])
    m = int(s[2:2+2])
    half = s[4] == "H"
    
    return datetime.time(h, m, 30 if half else 0)

def from_minutes_and_halves(s):
    """Converts a time in minutes-and-halves to an integer number of seconds.
    
    Example inputs and outputs:
    
    * "0 " -> 0
    * "0h" -> 30
    * "1 " -> 60
    * "1h" -> 90
    * "2" -> 120
    * "2h" -> 150
    * "10" -> 600
    """
    s = s.strip()
    half = s.endswith("H")
    s = s.strip("H ")
    
    return (int(s) * 60 if s else 0) + (30 if half else 0)
        

def from_day_set(s):
    """Read a binary-encoded days-of-week bitfield to an integer."""
    return int(s[::-1], 2)


RECORD_TYPES = {
    RecordIdentity.header: new_cif_record("HeaderRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.header)),
        Field("file_mainframe_identity", 20, str.strip),
        Field("date_of_extract", 6, from_ddmmyy),
        Field("time_of_extract", 4, from_hhmm),
        Field("current_file_ref", 7, None),
        Field("last_file_ref", 7, None),
        Field("bleed_of_update_int", 1, None),
        Field("version", 1, None),
        Field("user_extract_start_date", 6, from_ddmmyy),
        Field("user_extract_end_date", 6, from_ddmmyy),
    ),
    RecordIdentity.tiploc_insert: new_cif_record("TiplocInsertRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.tiploc_insert)),
        Field("tiploc_code", 7, str.strip),
        Field("capitals_identification", 2, int),
        Field("nalco", 6, int),
        Field("nlc_check_character", 1, None),
        Field("tps_description", 26, str.strip),
        Field("stanox", 5, int),
        Field("po_mcp_code", 4, int),
        Field("crs_code", 3, str.strip),
        Field("description", 16, str.strip),
    ),
    RecordIdentity.association: new_cif_record("AssociationRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.association)),
        Field("transaction_type", 1, TransactionType),
        Field("main_train_uid", 6, str.strip),
        Field("associated_train_uid", 6, str.strip),
        Field("association_start_date", 6, from_yymmdd),
        Field("association_end_date", 6, from_yymmdd),
        Field("association_days", 7, from_day_set),
        Field("association_category", 2, if_not_blank(AssociationCateogry)),
        Field("association_date_ind", 1, if_not_blank(AssociationDateIndex)),
        Field("association_location", 7, str.strip),
        Field("base_location_suffix", 1, None),
        Field("assoc_location_suffix", 1, None),
        Field("diagram_type", 1, assert_is("T")),
        Field("association_type", 1, if_not_blank(AssociationType)),
        Field("spare", 31, assert_is(" "*31)),
        Field("stp_indicator", 1, STPIndicator),
    ),
    RecordIdentity.basic_schedule: new_cif_record("BasicScheduleRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.basic_schedule)),
        Field("transaction_type", 1, TransactionType),
        Field("train_uid", 6, str.strip),
        Field("date_runs_from", 6, from_yymmdd),
        Field("date_runs_to", 6, from_yymmdd),
        Field("days_run", 7, from_day_set),
        Field("bank_holiday_running", 1, BankHolidayRunning),
        Field("train_status", 1, if_not_blank(TrainStatus)),
        Field("train_category", 2, if_not_blank(TrainCategory)),
        Field("train_identity", 4, None),
        Field("headcode", 4, None),
        Field("course_indicator", 1, assert_is("1")),
        Field("train_service_code", 8, None),
        Field("portion_id", 1, if_not_blank(PortionID)),
        Field("power_type", 3, if_not_blank(lambda s: PowerType(s.strip()))),
        Field("timing_load", 4, str.strip),
        Field("speed", 3, if_not_blank(int)),
        Field("operating_characteristics", 6, several(OperatingCharacteristics)),
        Field("train_class", 1, (lambda s: TrainClass(s.strip("B ")))),
        Field("sleepers", 1, if_not_blank(Sleepers)),
        Field("reservations", 1, if_not_blank(Reservations)),
        Field("connection_indicator", 1, None),
        Field("catering_code", 4, several(CateringCode)),
        Field("service_branding", 4, several(ServiceBrand)),
        Field("spare", 1, assert_is(" ")),
        Field("stp_indicator", 1, STPIndicator),
    ),
    RecordIdentity.basic_schedule_extra_details: new_cif_record("BasicScheduleExtraDetailsRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.basic_schedule_extra_details)),
        Field("traction_class", 4, None),
        Field("uic_code", 5, None),
        Field("atoc_code", 2, None),
        Field("applicable_timetable_code", 1, AppliccableTimetableCode),
        Field("rsid", 8, None),
        Field("data_source", 1, None),
    ),
    RecordIdentity.origin_location: new_cif_record("OriginLocationRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.origin_location)),
        Field("location", 7, str.strip),
        Field("location_suffix", 1, None),
        Field("scheduled_departure", 5, from_hhmmh),
        Field("public_departure", 4, from_hhmm),
        Field("platform", 3, str.strip),
        Field("line", 3, str.strip),
        Field("engineering_allowance", 2, from_minutes_and_halves),
        Field("pathing_allowance", 2, from_minutes_and_halves),
        Field("activity", 12, several(Activity, size=2)),
        Field("performance_allowance", 2, from_minutes_and_halves),
    ),
    RecordIdentity.intermediate_location: new_cif_record("IntermediateLocationRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.intermediate_location)),
        Field("location", 7, str.strip),
        Field("location_suffix", 1, None),
        Field("scheduled_arrival", 5, if_not_blank(from_hhmmh)),
        Field("scheduled_departure", 5, if_not_blank(from_hhmmh)),
        Field("scheduled_pass", 5, if_not_blank(from_hhmmh)),
        Field("public_arrival", 4, if_not_blank(from_hhmm)),
        Field("public_departure", 4, if_not_blank(from_hhmm)),
        Field("platform", 3, str.strip),
        Field("line", 3, str.strip),
        Field("path", 3, str.strip),
        Field("activity", 12, several(Activity, size=2)),
        Field("engineering_allowance", 2, from_minutes_and_halves),
        Field("pathing_allowance", 2, from_minutes_and_halves),
        Field("performance_allowance", 2, from_minutes_and_halves),
    ),
    RecordIdentity.terminating_location: new_cif_record("TerminatingLocationRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.terminating_location)),
        Field("location", 7, str.strip),
        Field("location_suffix", 1, None),
        Field("scheduled_arrival", 5, from_hhmmh),
        Field("public_arrival", 4, from_hhmm),
        Field("platform", 3, str.strip),
        Field("path", 3, str.strip),
        Field("activity", 12, several(Activity, size=2)),
    ),
    RecordIdentity.changes_en_route: new_cif_record("ChangesEnRouteRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.changes_en_route)),
        Field("location", 7, str.strip),
        Field("location_suffix", 1, None),
        Field("train_category", 2, TrainCategory),
        Field("train_identity", 4, None),
        Field("headcode", 4, None),
        Field("course_indicator", 1, assert_is("1")),
        Field("train_service_code", 8, None),
        Field("portion_id", 1, if_not_blank(PortionID)),
        Field("power_type", 3, if_not_blank(lambda s: PowerType(s.strip()))),
        Field("timing_load", 4, str.strip),
        Field("speed", 3, if_not_blank(int)),
        Field("operating_characteristics", 6, several(OperatingCharacteristics)),
        Field("train_class", 1, (lambda s: TrainClass(s.strip("B ")))),
        Field("sleepers", 1, if_not_blank(Sleepers)),
        Field("reservations", 1, if_not_blank(Reservations)),
        Field("connection_indicator", 1, None),
        Field("catering_code", 4, several(CateringCode)),
        Field("service_branding", 4, several(ServiceBrand)),
        Field("traction_class", 4, None),
        Field("uic_code", 5, None),
        Field("rsid", 8, None),
    ),
    RecordIdentity.trailer: new_cif_record("TrailerRecord",
        Field("record_identity", 2, assert_record_identity(RecordIdentity.trailer)),
    )
}


def parse_mca(f):
    """Parse a Timetable Information Service (TTIS) MCA (full timetable) file,
    generating each record in turn.
    """
    for line in f:
        yield RECORD_TYPES[RecordIdentity(line[:2])].from_string(line)
