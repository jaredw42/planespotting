import math
import time
from utils import write_simple_msg_to_log

from pymap3d import geodetic2ned

# from get_adsb_data import ADSB_UPDATE_WAIT_SEC, SECS2MINS, write_to_log
ADSB_UPDATE_WAIT_SEC = 20  # [s]
ADSB_CATEGORY_HEAVY = "A5"  # string

SECS2MINS = 1 / 60


class Plane:
    """
    object for storing aircraft state information
    """

    def __init__(self, registry, flight, status):

        self.registry = registry
        self.flight = flight.strip()
        self.type = status["t"]

        self.time = 0
        self.lat = 0
        self.lon = 0
        self.alt_baro = 0
        self.true_hdg = 0
        self.nav_hdg = 0
        self.prev_lat = 0
        self.prev_lon = 0
        self.prev_alt_baro = 0
        self.prev_true_hdg = 0
        self.prev_nav_hdg = 0

        self.vertical_speed = 0  # [ft/minute]

        self.previous_altitudes = []

        self.position_updated = False
        self.stale_count = 0
        self.status = {}

        self.update_status(status)

    def update_status(self, status):
        """
        class method for updating aircraft state information
        """

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
            print(printstr)
            self.prev_lat = self.lat
            self.prev_lon = self.lon
            self.prev_alt_baro = self.alt_baro
            self.prev_nav_hdg = self.nav_hdg
            self.position_updated = True
            self.stale_count = 0

            if self.alt_baro != "ground":
                self.previous_altitudes.append(self.alt_baro)
                self.calculate_vertical_speed()
                self.previous_altitudes = self.previous_altitudes[0:10]

            else:
                if self.previous_altitudes:
                    self.previous_altitudes = []
                    self.vertical_speed = 0

        else:
            self.position_updated = False
            self.stale_count += 1
        # adsb exchange data
        status["time_ns"] = self.time
        self.status = status

    def calculate_vertical_speed(self):
        # this is just a rough estimate based on at most 10 samples
        distance = self.previous_altitudes[-1] - self.previous_altitudes[0]
        minutes = (len(self.previous_altitudes) * ADSB_UPDATE_WAIT_SEC) * SECS2MINS

        self.vertical_speed = distance / minutes

    def calculate_distance_to_point(self, coords):

        ned = geodetic2ned(self.lat, self.lon, self.alt_baro, coords[0], coords[1], coords[2], deg=True)

        distance_2d = math.sqrt(ned[0] ** 2 + ned[1] ** 2)
        distance_3d = math.sqrt(ned[0] ** 2 + ned[1] ** 2 + ned[2] ** 2)

        distance = {"north": ned[0], "east": ned[1], "down": ned[2], "horizontal": distance_2d, "spherical": distance_3d}

        return distance

    def calculate_bearing_from_point(self, coords):
        """
        θ = lat, L = lon
        X = cos θb * sin ∆L
        Y = cos θa * sin θb – sin θa * cos θb * cos ∆L
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


if __name__ == "__main__":
    pass
