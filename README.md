Railmap: Visualising rail travel times in the UK
================================================

This is a quick-and-dirty project to try and visualise how long it takes to get
to any location in the UK rail network starting from a particular location.

Example images
--------------

Close up showing distances from Manchester:

![Manchester](./examples/closeupManchester.png)

Zoomed-out shot of the south of England:

![South](./examples/south.png)


Usage
-----

This repository contains a collection of tools which take publicly available
data about UK rail timetables, lines and stations and eventually process these
into a map such as the ones shown above. the following data sources are used
and should be downloaded and extracted:

* [*Timetable Information Service (TTIS) data:*](http://data.atoc.org/how-to)
  The short-term and long-term timetables in 'CIF' format. This is a somewhat
  arcane text-based format which encodes enough timetable information to
  perform rudamentrary route planning.
* [*Network Rail Railway Network Inspire Data:*](https://data.gov.uk/dataset/railway-network-inspire)
  This pair of datasets define geographical properties of the UK rail
  infrastructure and are used to generate the graphical map.
  * [Station locations](http://inspire.misoportal.com/geoserver/transport_direct_railnetwork/wfs?amp;version=2.0.0&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=transport_direct_railnetwork:stations&SRSNAME=EPSG:27700&outputFormat=shape-zip)
  * [Railway line map](http://inspire.misoportal.com/geoserver/transport_direct_railnetwork/wfs?amp;version=2.0.0&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=transport_direct_railnetwork:railnetwork&SRSNAME=EPSG:27700&outputFormat=shape-zip)
* [*Ordnance Survey Boundary-Line:*](https://www.ordnancesurvey.co.uk/opendatadownload)
  One of the Ordnance Survey OpenData free-to-download datasets which includes
  a detailed outline of the high-water level around the UK. This is used to
  draw an outline of the UK onto the rail map.

The railmap command-line tools and their dependencies may be installed using
`setup.py` as usual (you may wish to do this in a VirtualEnv).

    $ python setup.py install

Three commands are provided:

* `railmap_station_times`: Uses a simple route-planner to determine how long it
  takes to travel from a given station to all others, starting at a particular
  time.
* `railmap_draw`: Renders the output of `railmap_station_times` on a map.
* `railmap_add_station_info`: Summarises other station metadata from the
  various datasources and adds it to the CSVs produced by
  `railmap_station_times` for ease-of-consumption by other tools.

To produce a map, first work out the journey times from a particular station:

    $ railmap_station_times ttisf256.mca MAN --datetime 2016 8 15 9 0 > route_times.csv

Here, the `.mca` file from the TTIS data along with a starting station and time
are given. A CSV detailing the journey times to all stations is produced via
stdout like so:

    start_station,start_time,station,duration
    MAN,2016-08-15 09:00:00,PNL,6960.0
    MAN,2016-08-15 09:00:00,CUF,13680.0
    MAN,2016-08-15 09:00:00,BIT,15660.0
    MAN,2016-08-15 09:00:00,BSY,12120.0
    MAN,2016-08-15 09:00:00,SVB,17580.0
    MAN,2016-08-15 09:00:00,SHO,21480.0
    MAN,2016-08-15 09:00:00,DRG,12600.0
    MAN,2016-08-15 09:00:00,ANL,15000.0
    MAN,2016-08-15 09:00:00,DNS,14820.0
    ...

Note that this process may take several minutes. Add `-vvv` to show progress
information on stderr.

To generate a map, `railmap_draw` is used:

    railmap_draw map.pdf                                \
        --station-times route_times.csv                 \
        --railway-stations inspireStationLocations.dbf  \
        --railway-lines inspireRailLines.shp            \
        --coastline osHighWater.shp                     \
        --railway-station-details ttisf256.msn

To force the labling of certain stations, add `--prioritise` followed by a list
of three-letter station codes to include. By default only mid-size and above
interchange stations are named.

The future...
-------------

This is all rough-and-ready and lacks tests and better docs. Further the label
overlap-prevention code is known buggy and I'm too lazy to fix it right now.
I'd also like to add the ability to take average journey times starting at
several times of day rather than just reporting journey times starting at a
single time and date.
