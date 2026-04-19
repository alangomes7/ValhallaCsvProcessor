#ifndef UTILS_H
#define UTILS_H

#include <utility>

struct Point {
    double lat;
    double lon;
    
    bool operator==(const Point& other) const {
        return lat == other.lat && lon == other.lon;
    }
    
    // Add this operator to allow std::pair<double, Point> comparisons
    bool operator<(const Point& other) const {
        if (lat != other.lat) {
            return lat < other.lat;
        }
        return lon < other.lon;
    }
};

class Utils {
public:
    static double calculateBearing(double lat1, double lon1, double lat2, double lon2);
    static bool doIntersect(Point p1, Point q1, Point p2, Point q2);

private:
    static bool onSegment(Point p, Point q, Point r);
    static int orientation(Point p, Point q, Point r);
};

#endif // UTILS_H