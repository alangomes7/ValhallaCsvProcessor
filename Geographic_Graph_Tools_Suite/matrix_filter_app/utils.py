import numpy as np
from math import atan2, degrees

def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate angle (bearing) between two points in degrees.
    """
    delta_lon = np.radians(lon2 - lon1)
    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    x = np.sin(delta_lon) * np.cos(lat2)
    y = np.cos(lat1) * np.sin(lat2) - (np.sin(lat1) * np.cos(lat2) * np.cos(delta_lon))
    angle = atan2(x, y)
    return degrees(angle) % 360

def on_segment(p, q, r):
    """Check if point q lies on segment pr."""
    if (q[0] <= max(p[0], r[0]) and q[0] >= min(p[0], r[0]) and
        q[1] <= max(p[1], r[1]) and q[1] >= min(p[1], r[1])):
        return True
    return False

def orientation(p, q, r):
    """
    Find the orientation of the ordered triplet (p, q, r).
    0 -> p, q, r are collinear
    1 -> Clockwise
    2 -> Counterclockwise
    """
    val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    if val == 0:
        return 0
    return 1 if val > 0 else 2

def do_intersect(p1, q1, p2, q2):
    """
    Check if line segment 'p1q1' intersects 'p2q2'.
    Points are tuples (latitude, longitude).
    """
    # Find the four orientations needed for general and special cases
    o1 = orientation(p1, q1, p2)
    o2 = orientation(p1, q1, q2)
    o3 = orientation(p2, q2, p1)
    o4 = orientation(p2, q2, q1)

    # General case
    if o1 != o2 and o3 != o4:
        return True

    # Special Cases (collinear points on segment) - Usually implies overlap
    # We treat collinear overlaps as intersections here
    if o1 == 0 and on_segment(p1, p2, q1): return True
    if o2 == 0 and on_segment(p1, q2, q1): return True
    if o3 == 0 and on_segment(p2, p1, q2): return True
    if o4 == 0 and on_segment(p2, q1, q2): return True

    return False