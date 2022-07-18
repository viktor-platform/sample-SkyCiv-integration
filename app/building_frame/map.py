import geopy.distance
from munch import Munch
from numpy import arctan
from numpy import cos
from numpy import pi
from numpy import rad2deg
from numpy import sin
from numpy import sqrt

from viktor.geometry import Color
from viktor.views import MapPoint
from viktor.views import MapPolygon


def rotate(origin: (float, float), point: (float, float), angle: float) -> (float, float):
    """
    Rotate a point counterclockwise by a given angle around a given origin.

    The angle should be given in radians.
    """
    ox, oy = origin
    px, py = point

    qx = ox + cos(angle) * (px - ox) - sin(angle) * (py - oy)
    qy = oy + sin(angle) * (px - ox) + cos(angle) * (py - oy)
    return qx, qy


class Map:
    """The Map class is used for the MapView. Here you can set the location for the building so we can use it for the wind and snow calculator from SkyCiv."""

    def __init__(self, params: Munch) -> None:
        self.params = params

        if self.params:
            self.building_corner = self.params.step_design.loc.start
            self.building_rotation = self.params.step_design.loc.rotate

    def get_office_polygon(self) -> MapPolygon:
        """Get a MapPolygon so we can visualise the Building Frame on the MapView"""
        # Assign params
        y_width = self.params.step_design.frame.office.length
        x_width = self.params.step_design.frame.office.width

        # Rotation angle and starting point
        rotation_angle = -self.building_rotation * (pi / 180)
        start = geopy.Point(self.building_corner.lat, self.building_corner.lon)

        # Shape points
        point1 = (0, 0)
        point2 = (0, 0 + y_width)
        point3 = (0 + x_width, 0 + y_width)
        point4 = (0 + x_width, 0)
        shape_points = [point1, point2, point3, point4]

        # Rotate points and insert coordinates in MapPolygon
        rotated_shape_points = [rotate((0, 0), pnt, rotation_angle) for pnt in shape_points]
        coordinates = self._convert_points_to_map_coordinates(start, rotated_shape_points)
        return MapPolygon(points=[MapPoint(coord[0], coord[1]) for coord in coordinates], color=Color(0, 0, 255))

    def _convert_points_to_map_coordinates(self, start: tuple, points: list) -> list:
        """Convert the points of the model to coordinates that we can use on the MapView"""
        start_point = geopy.Point(*start)
        map_coordinates = [start_point]
        for i, point in enumerate(points):
            if i == 0:
                continue
            start_point_ = map_coordinates[i - 1]
            x_diff = points[i][0] - points[i - 1][0]
            y_diff = points[i][1] - points[i - 1][1]
            distance = sqrt(x_diff**2 + y_diff**2)
            d = geopy.distance.distance(kilometers=distance / 1000)
            if y_diff == 0:
                if x_diff >= 0:
                    bearing = 90
                else:
                    bearing = -90
            else:
                bearing = rad2deg(arctan(x_diff / y_diff))
                if y_diff < 0:
                    bearing = 180 + bearing
            next_point = d.destination(point=start_point_, bearing=bearing)
            map_coordinates.append(next_point)
        return map_coordinates
