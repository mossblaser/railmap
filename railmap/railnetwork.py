"""
Read all of the line segments out of a shape file in a National Rail Railway
Network Inspire data shapefile.
"""

# Provided by the PyPI package 'pyshp'
import shapefile

def shp_to_lists(filename):
    """Read all of the line segments out of a shape file in a National Rail
    Railway Network Inspire data shapefile. Outputs a simple list of lists of
    (x, y) tuples for all line segments.
    """
    sf = shapefile.Reader(filename)
    
    lists = []
    
    cur_list = []
    
    for s in sf.shapes():
        # All shapes are PolyLines in a valid data file.
        assert s.shapeType == 3
        
        parts = list(s.parts)
        for n, (x, y) in enumerate(s.points):
            if parts and n == parts[0]:
                parts.pop(0)
                if cur_list:
                    lists.append(cur_list)
                cur_list = []
            cur_list.append((x, y))
    
    if cur_list:
        lists.append(cur_list)
    
    return lists
