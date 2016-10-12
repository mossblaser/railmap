"""
Render a map showing journey times calculated by the railmap_station_times
script.
"""

import re

from argparse import ArgumentParser
from contextlib import contextmanager
from math import pi

import cairocffi as cairo

from railmap.railnetwork import shp_to_lists
from railmap.stations import dbf_to_dict
from railmap.cif import msn_to_dict
from railmap.cif.msn import InterchangeStatus


@contextmanager
def cairo_png(filename, width, height):
    """A context manager which provides a Cairo context which is written to a
    PNG of the specified size upon leaving the context.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    
    yield ctx
    
    surface.write_to_png(filename)


@contextmanager
def cairo_pdf(filename, width, height):
    """A context manager which provides a Cairo context which is written to a
    PDF of the specified size (in mm) upon leaving the context.
    """
    PT_PER_MM = 2.83464567
    
    surface = cairo.PDFSurface(filename,
                               width * PT_PER_MM,
                               height * PT_PER_MM)
    ctx = cairo.Context(surface)
    # Make the base unit mm.
    ctx.scale(PT_PER_MM, PT_PER_MM)
    
    yield ctx
    
    ctx.show_page()


@contextmanager
def fit_and_center(ctx, page_width, page_height, min_x, min_y, max_x, max_y):
    """Setup a cairo transformation which translates/sccales coordinates such
    that points between {min,max}_{x,y} are spread without distortion in the
    center of the specified page_width and page_height, presuming the page
    starts from (0, 0).
    """
    area_width = max_x - min_x
    area_height = max_y - min_y
    
    # Scale based on whichever dimension is tighter
    scale_x = page_width / area_width
    scale_y = page_height / area_height
    scale = min(scale_x, scale_y)
    
    with ctx:
        ctx.scale(scale, scale)
        
        # Move area into bottom-left corner of page
        ctx.translate(-min_x, -min_y)
        
        # Center on page
        ctx.translate(((page_width/scale) - area_width)/2,
                      ((page_height/scale) - area_height)/2)
        
        yield ctx

def draw_text_bounds(ctx, ox, oy, text, align_point=0.0, size=1.0, *args, **kwargs):
    """
    Get the bounding box of the specified text as a (x1, y1, x2, y2) tuple.
    """
    with ctx:
        ctx.select_font_face("Sans")
        ctx.set_font_size(size)
        x,y, w,h, _w,_h = ctx.text_extents(text)
        x1 = -x + ((1.0-w)*align_point)
        y1 = -y - size/2
        x2 = x1 + w
        y2 = y1 + h
        return (ox+x1,oy+y1, ox+x2,oy+y2)

def draw_text(ctx, ox, oy, text, align_point=0.0, size=1.0, rgba=(0.0,0.0,0.0, 1.0)):
    """
    Draw the desired text centered vertically around (0,0) horizontally
    "align_point" along the text's width.
    """
    with ctx:
        ctx.translate(ox, oy)
        ctx.select_font_face("Sans")
        ctx.set_source_rgba(*rgba)
        ctx.set_font_size(size)
        x,y, w,h, _w,_h = ctx.text_extents(text)
        ctx.move_to(-x + ((1.0-w)*align_point), -y - size/2)
        ctx.show_text(text)


def get_network_bounds(network_lines):
    """Given the output of shp_to_lists, return the bottom-left and top-right
    corners of the bounding box covering the network.
    """
    xys = []
    for line in network_lines:
        xys.extend(line)
    
    min_x = min(x for (x, y) in xys)
    min_y = min(y for (x, y) in xys)
    max_x = max(x for (x, y) in xys)
    max_y = max(y for (x, y) in xys)
    
    return (min_x, min_y, max_x, max_y)

def load_station_times(filename):
    """
    Given a route-times CSV file produced by the ``railmap_station_times``
    script, extracts the duration for each three-alpha-code. Blindly assumes
    all entries start from the same station.
    
    Returns
    -------
    {three_alpha_code: duration_in_seconds, ...}
    """
    out = {}
    with open(filename) as f:
        lines = list(filter(None, f.read().split("\n")))
        
        cols = lines[0].split(",")
        station_col = cols.index("station")
        duration_col = cols.index("duration")
        
        for line in lines[1:]:
            cols = line.split(",")
            out[cols[station_col]] = float(cols[duration_col])
    return out

def html_colour(string):
    """Parse a HTML colour into a (r, g, b, a) tuple where the values are
    between 0 and 1 and alpha is always 1.0.
    """
    match = re.match(r"^#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$", string)
    if match:
        r, g, b = (int(v, 16)/255.0 for v in match.groups())
        return (r, g, b, 1.0)
    else:
        raise TypeError(string)

class ObstructionTester(object):
    """Test if a given rectangle is obstructed by a set of existing rectangles.
    
    This object is used to avoid drawing (textual) labels on-top of previously
    drawn labels. Each time a label is drawn, it should be add()-ed to this
    object. Subsequent labels should be drawn iff the rectangle is not 'in'
    this object.
    """
    
    def __init__(self):
        # Internally this uses the simplest method that could possibly work:
        # scanning a list of previously added rectangles to see if any overlap
        # each time. Though It has O(N^2) runtime complexity, in practice N is
        # small enough that this process doesn't contribute noticably to the
        # runtime of this script. If the UK ever has a *lot* more train
        # stations one day, a quad tree/pack tree or something could probably
        # be used.
        self.obstructions = []
    
    def add(self, x1,y1, x2,y2):
        """Add a rectangle to the structure."""
        self.obstructions.append((x1,y1, x2,y2))
    
    def __contains__(self, rect):
        """Check if a given rectangle as a tuple (x1,y1, x2,y2) is obstructed
        by any rectangle previously added. Returns True if so, False otherwise.
        """
        for bx1,by1, bx2,by2 in self.obstructions:
            # (Maybe) clobbered in each iteration
            ax1,ay1, ax2,ay2 = rect
            
            # Flip to put 'a' as top-left-most
            if ax1 > bx1:
                ax1, ax2, bx1, bx2 = bx1, bx2, ax1, ax2
            if ay1 > by1:
                ay1, ay2, by1, by2 = by1, by2, ay1, ay2
            
            if bx1 <= ax2 and by1 <= ay2:
                return True
        return False


def draw_shp_lists(ctx, lists):
    """Given a list of lists containing line segments, e.g. from
    ``shp_to_lists``, execute the Cairo drawing commands to draw these
    outlines. Note that the caller is responsible for setting sources and
    stroking the path.
    """
    for line in lists:
        x, y = line[0]
        ctx.move_to(x, -y)
        for x, y in line[1:]:
            ctx.line_to(x, -y)


def main():
    parser = ArgumentParser(
        description="Render a map showing journey times calculated by the "
                    "railmap_station_times script.")
    
    output_group = parser.add_argument_group("output options")

    output_group.add_argument("filename", metavar="FILENAME",
                              help="The output filename *.pdf or *.png")
    output_group.add_argument("width", nargs="?", metavar="WIDTH", type=float,
                              help="Output size (PDF: mm, PNG: px). "
                                   "Automatic if not given.")
    output_group.add_argument("height", nargs="?", metavar="HEIGHT", type=float,
                              help="Automatic if not given.")
    
    input_group = parser.add_argument_group("input files")
    
    input_group.add_argument("--station-times", "-i", metavar="FILENAME",
                             required=True,
                             help="(Required.) CSV file enumerating "
                                  "journey times to all stations to be shown. "
                                  "The output of the railmap_station_times "
                                  "command.")
    
    input_group.add_argument("--railway-stations", "-t", metavar="FILENAME",
                             required=True,
                             help="(Required.) DBF file enumerating "
                                  "coordinates of all stations, from the "
                                  "railway 'inspire' data set.")
    
    input_group.add_argument("--railway-station-details", "-d", metavar="FILENAME",
                             help="(Optional.) A master Station Names (MSN) "
                                  "file from the Timetable Information "
                                  "Service (TTIS) dump. If omitted, all "
                                  "station names are shown on the map which "
                                  "will fit with no priority given to major "
                                  "stations.")
    
    input_group.add_argument("--railway-lines", "-l", metavar="FILENAME",
                             help="(Optional.) Shape file (*.shp) containing "
                                  "the paths of railway tracks, from the "
                                  "railway 'inspire' data set. If omitted no "
                                  "railway lines will be drawn.")
    
    input_group.add_argument("--coastline", "-L", metavar="FILENAME",
                             help="(Optional.) Shape file (*.shp) containing "
                                  "the outline of the UK, e.g. from OS "
                                  "Open Data. If omitted the UK outline will "
                                  "be omitted.")

    style_group = parser.add_argument_group(
        "aesthetic options",
        description="Options which affect the style of the generated image. "
                    "Colours are given as HTML-style '#RRGGBB' format. Sizes "
                    "are given in meters and are drawn to the scale of the map.")
    
    style_group.add_argument("--minimum-size", "-m", default="medium",
                             choices=["small", "medium", "large", "none"],
                             help="Minimum station (interchange) size for "
                                  "stations whose names are displayed. If "
                                  "--railway-station-details not given then "
                                  "this option has no effect and 'all' will "
                                  "be used. (Default: %(default)s)")
    
    style_group.add_argument("--prioritise", "-p", default=[], nargs="+",
                             type=str.upper,
                             help="List of three-alpha station codes which "
                                  "should be added to the map first, and "
                                  "shown regardless of their interchange "
                                  "size.")
    
    style_group.add_argument("--railway-line-thickness", "-r", type=float,
                             metavar="THICKNESS", default=500.0,
                             help="Thickness of railway lines. "
                                  "(Default: %(default)s)")
    style_group.add_argument("--railway-line-colour", "-R", type=html_colour,
                             metavar="COLOUR", default=html_colour("#888888"),
                             help="Colour of railway lines.")
    
    style_group.add_argument("--coastline-thickness", "-c", type=float,
                             metavar="THICKNESS", default=250.0,
                             help="Thickness of the UK coastline outline. "
                                  "(Default: %(default)s)")
    style_group.add_argument("--coastline-colour", "-C", type=html_colour,
                             metavar="COLOUR", default=html_colour("#729FCF"),
                             help="Colour of the UK coastline outline.")
    
    style_group.add_argument("--station-dot-size", "-s", type=float,
                             metavar="SIZE", default=1000.0,
                             help="Diameter of the dots drawn at station "
                                  "locations. (Default: %(default)s)")
    style_group.add_argument("--station-dot-colour", "-S", type=html_colour,
                             metavar="COLOUR", default=html_colour("#FF0000"),
                             help="Colour of the dots drawn at station "
                                  "locations.")
    
    style_group.add_argument("--station-name-size", "-n", type=float,
                             metavar="SIZE", default=5000.0,
                             help="Height of station name labels. "
                                  "(Default: %(default)s)")
    style_group.add_argument("--station-name-colour", "-N", type=html_colour,
                             metavar="COLOUR", default=html_colour("#008800"),
                             help="Colour of station name labels.")
    
    style_group.add_argument("--journey-time-size", "-j", type=float,
                             metavar="SIZE", default=2000.0,
                             help="Height of journey time labels. "
                                  "(Default: %(default)s)")
    style_group.add_argument("--journey-time-colour", "-J", type=html_colour,
                             metavar="COLOUR", default=html_colour("#000088"),
                             help="Colour of journey time labels.")
    
    args = parser.parse_args()
    
    interchange_statuses = []
    if args.minimum_size in ("large", "medium", "small"):
        interchange_statuses.append(InterchangeStatus.large)
    if args.minimum_size in ("medium", "small"):
        interchange_statuses.append(InterchangeStatus.medium)
    if args.minimum_size in ("small"):
        interchange_statuses.append(InterchangeStatus.small)
    
    # Check filetype and select sensible default image sizes etc.
    filetype = args.filename.split(".")[-1].lower()
    if filetype == "png":
        cairo_env_decorator = cairo_png
        default_width = 1000
        dimension_format = int
    elif filetype == "pdf":
        cairo_env_decorator = cairo_pdf
        # A4
        default_width = 297.0
        dimension_format = float
    else:
        parser.error("Output filename must end with *.png or *.pdf.")
    
    # Load and parse input data files
    station_times = load_station_times(args.station_times)
    railway_stations = dbf_to_dict(args.railway_stations)
    
    # Filter station list to just those stations for which distance information
    # is available and which are not at the invalid coordinate (0, 0)
    railway_stations = [
        station for station in railway_stations.values()
        if station.station_code in station_times and
        (station.eastings, station.northings) != (0, 0)
    ]
    
    # Sort the station list to put high-priorty entities first
    railway_stations = sorted(railway_stations, key=(lambda station:
        args.prioritise.index(station.station_code)
        if station.station_code in args.prioritise
        else len(args.prioritise)
        ))
    
    if args.railway_station_details is not None:
        railway_station_details = msn_to_dict(args.railway_station_details)
    else:
        railway_station_details = {}
    
    if args.railway_lines is not None:
        railway_lines = shp_to_lists(args.railway_lines)
    else:
        railway_lines = []
    
    if args.coastline is not None:
        coastline = shp_to_lists(args.coastline)
    else:
        coastline = []
    
    
    # Determine the dimensions of the network
    min_x, min_y, max_x, max_y = get_network_bounds(
        coastline + railway_lines +
        [[(station.eastings, station.northings) for station in railway_stations]])
    
    # Determine map dimensions
    network_width = max_x - min_x
    network_height = max_y - min_y
    network_ratio = network_width / network_height
    
    # Determine requested dimensions
    if args.width is None:
        width = default_width
    else:
        width = args.width
    if args.height is None:
        height = width / network_ratio
    else:
        height = args.height
    
    width = dimension_format(width)
    height = dimension_format(height)
    
    with cairo_env_decorator(args.filename, width, height) as ctx:
        # Draw lines with rounded joints and caps to avoid highly detailed
        # segments (e.g. coastline) becoming jagged horror-shows with large
        # mitres pointing out.
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        
        # Center the map and re-scale to map distance units... NB: From here
        # on, 'y' coordinates are inverted as map coordinates go from south to
        # north while Cairo coordinates do the opposite.
        with fit_and_center(ctx, width, height, min_x, -max_y, max_x, -min_y):
            # Draw coastline
            ctx.set_line_width(args.coastline_thickness)
            ctx.set_source_rgba(*args.coastline_colour)
            draw_shp_lists(ctx, coastline)
            ctx.stroke()
            
            # Draw railway lines
            ctx.set_line_width(args.railway_line_thickness)
            ctx.set_source_rgba(*args.railway_line_colour)
            draw_shp_lists(ctx, railway_lines)
            ctx.stroke()
            
            # Draw station dots
            for station in railway_stations:
                # Draw a dot where the station is located
                ctx.set_source_rgba(*args.station_dot_colour)
                ctx.arc(station.eastings, -station.northings,
                        args.station_dot_size/2.0,
                        0.0, 2.0*pi)
                ctx.fill()
            
            # Draw station names and journey times
            ot = ObstructionTester()
            for station in railway_stations:
                # Only show station names for sufficiently major stations, or
                # stations granted higher priority
                sub_stations = railway_station_details.get(station.station_code)
                if (not railway_station_details or 
                        station.station_code.upper() in args.prioritise or
                        (sub_stations and any(s.interchange_status
                                              in interchange_statuses
                                              for s in sub_stations))):
                    fargs = [ctx,
                             station.eastings - args.station_dot_size,
                             -station.northings,
                             station.station_code]
                    fkwargs = {"align_point": 1,
                               "size": args.station_name_size,
                               "rgba": args.station_name_colour}
                    bbox = draw_text_bounds(*fargs, **fkwargs)
                    if bbox not in ot:
                        ot.add(*bbox)
                        draw_text(*fargs, **fkwargs)
                
                # Show journey times
                duration = int(station_times[station.station_code]) // 60
                hours = duration // 60
                minutes = duration - (hours * 60)
                fargs = [ctx,
                         station.eastings + args.station_dot_size,
                         -station.northings,
                         "{}:{:02d}".format(hours, minutes)]
                fkwargs = {"align_point": 0,
                           "size": args.journey_time_size,
                           "rgba": args.journey_time_colour}
                bbox = draw_text_bounds(*fargs, **fkwargs)
                if bbox not in ot:
                    ot.add(*bbox)
                    draw_text(*fargs, **fkwargs)

if __name__ == "__main__":
    main()
