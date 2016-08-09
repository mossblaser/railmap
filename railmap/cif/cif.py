import sys

from collections import namedtuple
from enum import Enum, IntEnum

import datetime

def assert_is(value):
    """Return a field parser which checks the field has a particular value."""
    
    def check(s):
        assert s == value, "{} == {}".format(repr(s), repr(value))
        return s
    
    return check

def from_ddmmyy(s):
    """Convert a "DDMMYY" format date to a python datetime.date."""
    d = int(s[0:0+2])
    m = int(s[2:2+2])
    y = int(s[4:4+2])
    
    # Y2K complience mechanism (see note 5 of "associations" record layout in
    # CIF spec.
    if y < 60:
        y += 2000
    else:
        y += 1999
    
    return datetime.date(y, m, d)

def from_yymmdd(s):
    """Convert a "YYMMDD" format date to a python datetime.date."""
    return from_ddmmyy(s[4:6] + s[2:4] + s[0:2])

def from_hhmm(s):
    """Convert a "HHMM" format date to a python datetime.time."""
    h = int(s[0:0+2])
    m = int(s[2:2+2])
    
    return datetime.time(h, m)

def several(parse_fn, size=1):
    """Produce a parsing function which returns a list of values parsed by a
    supplied parse function.
    """
    def f(s):
        s = s.strip()
        out = []
        while s:
            substr, s = s[:size], s[size:]
            out.append(parse_fn(substr.strip())
                       if parse_fn is not None
                       else substr)
        return out
    return f


def if_not_blank(parse_fn):
    """Produce a parsing function which returns None if its input string is
    empty (or only spaces) and calls the provided parsing function on it
    otherwise.
    """
    def f(s):
        return parse_fn(s) if s.strip() else None
    return f



Field = namedtuple("Field", "name,size,parse_fn")


def new_cif_record(name, *fields):
    """Define a new namedtuple to hold a CIF record with a given set of fields.
    
    The returned namedtuple is given a ``from_string`` classmethod which
    constructs an instance of the record from a string defining a record of the
    appropriate type.
    
    The first argument is a name for the CIF record, the remaining arguments
    are Field tuples defining the name, size and a parsing function for each
    record. The ``from_string`` method will divide up the provided string into
    chunks according to the ``size`` value of each field. This chunk is then
    passed as the sole argument to the ``parse_fn`` in the field. The value
    returned is then placed in the corresponding tuple value.
    """
    t = namedtuple(name, ",".join(f.name for f in fields))
    
    def from_string(string):
        values = []
        for f in fields:
            substring, string = string[:f.size], string[f.size:]
            values.append(f.parse_fn(substring)
                          if f.parse_fn is not None
                          else substring)
        return t(*values)
    
    t.from_string = from_string
    
    return t
