from setuptools import setup, find_packages
import sys

with open("railmap/version.py", "r") as f:
    exec(f.read())

requirements = ["enum_compat", "pyshp", "dbf", "cairocffi"]

setup(
    name="railmap",
    version=__version__,
    packages=find_packages(),

    # Metadata for PyPi
    url="https://github.com/mossblaser/railmap",
    author="Jonathan Heathcote",
    description="UK National Rail data experiments",
    license="GPLv2",

    # Requirements
    install_requires=requirements,

    # Scripts
    entry_points={
        "console_scripts": [
            "railmap_station_times = railmap.scripts.station_times:main",
            "railmap_add_station_info = railmap.scripts.add_station_info:main",
            "railmap_draw = railmap.scripts.draw_railmap:main",
        ],
    }
)
