#include "utils.h"
#include <cmath>

const double PI = 3.14159265358979323846;

double Utils::calculateBearing(double lat1, double lon1, double lat2, double lon2) {
    double dLon = (lon2 - lon1) * PI / 180.0;
    lat1 = lat1 * PI / 180.0;
    lat2 = lat2 * PI / 180.0;

    double x = std::sin(dLon) * std::cos(lat2);
    double y = std::cos(lat1) * std::sin(lat2) - (std::sin(lat1) * std::cos(lat2) * std::cos(dLon));
    double angle = std::atan2(x, y) * 180.0 / PI;
    return std::fmod((angle + 360.0), 360.0);
}

bool Utils::onSegment(Point p, Point q, Point r) {
    return (q.lat <= std::max(p.lat, r.lat) && q.lat >= std::min(p.lat, r.lat) &&
            q.lon <= std::max(p.lon, r.lon) && q.lon >= std::min(p.lon, r.lon));
}

int Utils::orientation(Point p, Point q, Point r) {
    double val = (q.lon - p.lon) * (r.lat - q.lat) - (q.lat - p.lat) * (r.lon - q.lon);
    
    if (std::abs(val) < 1e-9) return 0; // Collinear
    
    return (val > 0) ? 1 : 2; // Clockwise or Counterclockwise
}

bool Utils::doIntersect(Point p1, Point q1, Point p2, Point q2) {
    int o1 = orientation(p1, q1, p2);
    int o2 = orientation(p1, q1, q2);
    int o3 = orientation(p2, q2, p1);
    int o4 = orientation(p2, q2, q1);

    if (o1 != o2 && o3 != o4) return true;

    if (o1 == 0 && onSegment(p1, p2, q1)) return true;
    if (o2 == 0 && onSegment(p1, q2, q1)) return true;
    if (o3 == 0 && onSegment(p2, p1, q2)) return true;
    if (o4 == 0 && onSegment(p2, q1, q2)) return true;

    return false;
}