"""
plane.py
class and methods for storing and determining aircraft state
"""
import logging
import math
import time
from utils import write_simple_msg_to_log

from pymap3d import geodetic2ned

# constants
ADSB_CATEGORY_HEAVY = "A5"  # string
SECS2MINS = 1 / 60

REQUIRED_STATUS_UPDATE_KEYS = ["lat", "lon", "alt_baro"]


class Plane:
    """
    object for storing aircraft state information
    """

    def __init__(self, registry, flight, status, verbosity=logging.INFO):

        self.registry = registry
        self.flight = flight.strip()
        self.type = status["t"]

        self.time = 0
        self.lat = 0
        self.lon = 0
        self.alt_geom = 0
        self.true_hdg = 0
        self.nav_hdg = 0
        self.prev_lat = 0
        self.prev_lon = 0
        self.prev_alt_baro = 0
        self.prev_true_hdg = 0
        self.prev_nav_hdg = 0

        self.vertical_speed = 0  # [ft/minute]

        self.previous_statuses = []
        self.entered_aois = []

        self.position_updated = False
        self.stale_count = 0
        self.status = status

        self.update_status(status)

    def update_status(self, status):
        """
        class method for updating aircraft state information
        """

        missing = [k for k in REQUIRED_STATUS_UPDATE_KEYS if k not in status]
        if missing:
            logging.error(f"can't update {self.registry} missing keys: {missing} ")
        else:

            self.lat = status["lat"]
            self.lon = status["lon"]
            self.alt_baro = status["alt_baro"]
            if "nav_heading" in status:
                self.nav_hdg = status["nav_heading"]
            if "true_heading" in status:
                self.true_hdg = status["true_heading"]
            self.time = time.time_ns()

            if self.lat != self.prev_lat or self.lon != self.prev_lon:
                printstr = f"position update: flight:{self.flight}, t-r: {self.type}-{self.registry},  time: {self.time} now at lat:{self.lat}, lon:{self.lon}, alt:{self.alt_baro}, hdg: {self.nav_hdg}, vertical_speed (ft/min): {int(self.vertical_speed)}"
                write_simple_msg_to_log(printstr)
                logging.debug(printstr)
                self.prev_lat = self.lat
                self.prev_lon = self.lon
                self.prev_alt_baro = self.alt_baro
                self.prev_nav_hdg = self.nav_hdg
                self.position_updated = True
                self.stale_count = 0

                if self.alt_baro != "ground":
                    self.vertical_speed = self.calculate_vertical_speed()

                else:
                    self.vertical_speed = 0

            else:
                self.position_updated = False
                self.stale_count += 1
            # not all ADSB sources include "now" field so pack an extra timestamp just in case
            status["time_ns"] = self.time
            self.status = status
            self.previous_statuses.append(status)
            self.previous_statuses = self.previous_statuses[0:10]

    def calculate_vertical_speed(self):
        """
        estimate aircraft vertical speed by aggregating several previous altimeter readings
        """
        distance = 0
        timediff = 0
        vert_speed = 0
        previous_alts = [msg["alt_baro"] for msg in self.previous_statuses]
        previous_times = [msg["now"] for msg in self.previous_statuses]

        if len(previous_alts) != len(previous_times):
            logging.error("")

        for i in range(1, len(previous_alts)):
            distance += previous_alts[i] - previous_alts[i - 1]
            timediff += previous_times[i] - previous_times[i - 1]

        if timediff:
            vert_speed = distance / (timediff * SECS2MINS)

        return vert_speed

    def calculate_distance_to_point(self, coords: list[float]) -> dict:
        """
        uses pymap3d.geodetic2ned() to calculate distance between two geodetic points
        """

        ned = geodetic2ned(self.lat, self.lon, self.alt_baro, coords[0], coords[1], coords[2], deg=True)

        distance_2d = math.sqrt(ned[0] ** 2 + ned[1] ** 2)
        distance_3d = math.sqrt(ned[0] ** 2 + ned[1] ** 2 + ned[2] ** 2)

        distance = {
            "north": ned[0],
            "east": ned[1],
            "down": ned[2],
            "horizontal": distance_2d,
            "spherical": distance_3d,
        }

        return distance

    def calculate_bearing_from_point(self, coords: list[float]) -> float:
        """
        calculate absolute bearing (azimumth) from a given coordinate to the Plane object lat/lon
        θ = lat
        L = lon
        X = cos θb * sin ∆L
        Y = cos θa * sin θb - sin θa * cos θb * cos ∆L
        β = atan2(X,Y) [radians]
        a = coords
        b = self
        """

        X = math.cos(self.lat) * math.sin(self.lon - coords[1])
        Y = (math.cos(coords[0]) * math.sin(self.lat)) - (
            math.sin(coords[0]) * math.cos(self.lat) * math.cos(self.lon - coords[1])
        )

        bearing = math.atan2(X, Y) * (180 / math.pi)
        if bearing < 0:
            bearing = 360 + bearing
        return bearing

    def check_coarse_bounding_box(self, poly) -> bool:
        """
        the fastest way to check if an object is inside a polygon is to create
        a rough bounding box and simply check if the object is inside the box.
        this may return some false positives (to be checked later) but never a false negative
        """
        minlat = min([coord[0] for coord in poly])
        maxlat = max([coord[0] for coord in poly])
        minlon = min([coord[1] for coord in poly])
        maxlon = max([coord[1] for coord in poly])

        if minlat < self.lat < maxlat and minlon < self.lon < maxlon:
            return True

    def check_point_by_ray_casting(self, poly):
        """
        use ray casting technique
        https://stackoverflow.com/questions/217578/how-can-i-determine-whether-a-2d-point-is-within-a-polygon
        https://wrfranklin.org/Research/Short_Notes/pnpoly.html
        """
        vertx = [point[1] for point in poly]
        verty = [point[0] for point in poly]
        # Number of vertices in the polygon
        nvert = len(poly)
        c = 0
        for i in range(0, nvert):
            j = i - 1 if i != 0 else nvert - 1
            if ((verty[i] > self.lat) != (verty[j] > self.lat)) and (
                self.lon < (vertx[j] - vertx[i]) * (self.lat - verty[i]) / (verty[j] - verty[i]) + vertx[i]
            ):
                c += 1
        # If odd, that means that we are inside the polygon
        if c % 2 == 1:
            return True

    def check_point_inside_circle(self, circle: dict) -> bool:
        """
        check if plane object is inside circular AOI
        """
        distance = self.calculate_distance_to_point(circle["center_point"])
        return True if distance["horizontal"] < circle["radius"] else False


if __name__ == "__main__":
    pass
