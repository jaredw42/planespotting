"""
monitor_adsb_radio_traffic.py
starts an AdsbRadioStreamer and watches for aircraft of interest.
calculates range and bearing to each aircraft.
assumes ADSB json stream has been fed database file with registry/type information
"""
from copy import copy
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

from absl import logging


from plane import Plane
from utils import (
    DEFAULT_LOG_DIR,
    start_adsb_radio_listener,
    write_simple_msg_to_log,
    write_single_adsb_response_to_log,
)

# constants
logging.set_verbosity(logging.DEBUG)
AOI_MSG_PATH = Path(DEFAULT_LOG_DIR, "aoi_messages.txt")
ADSB_CATEGORY_HEAVY = "A5"
MONITORED_CATEGORIES = [ADSB_CATEGORY_HEAVY]
MONITORED_LOCATIONS = ["foster_city_southeast_large", "bayside_2000m", "bayside_5000m", "bayside_12km", "bayside_50km", "emeryville_10km"]

LOGGER_INFO_OUTPUT_SECS = 30  # [s]


def get_aoi_locations():
    """
    load json file with areas of interest.
    """
    locpath = Path(os.getcwd(), "resources/locations2.json")

    with open(locpath, "rt") as f:
        locations = json.load(f)

    return locations


def update_tracked_plane_information(plane: Plane, data: dict, location: dict) -> None:
    """
    update plane state with latest message and calculate distance and direction to primary monitoring point
    """
    coords = location["coordinates"]
    name = location["name"]
    plane.update_status(data)
    distance = plane.calculate_distance_to_point(coords)["spherical"] / 1000.0
    bearing = plane.calculate_bearing_from_point(coords)
    logging.info(
        f"flight {plane.flight} ({plane.type}) is {distance:.1f} km, {bearing:.0f} deg from {name}. Alt: {plane.alt_baro}, VS: {plane.vertical_speed:.0f}, HDG: {plane.nav_hdg:.0f} "
    )


def check_if_inside_aois(plane: Plane, aois: list = None):
    """
    iterate through list of areas of interest and do a series of checks
    to determine if plane has been in AOI before and if not, check if it's there now.
    """
    if not aois:
        aois = MONITORED_LOCATIONS

    for aoi in aois:
        if aoi not in plane.entered_aois:
            entered = False
            loc = locations["air_aois"][aoi]
            #
            if plane.alt_baro <= loc["ceiling"]:
                if loc["type"] == "circle" and plane.check_point_inside_circle(loc):
                    entered = True
                # do a cheap bounding box check before raycasting check
                elif (
                    loc["type"] == "polygon"
                    and plane.check_coarse_bounding_box(loc["coordinates"])
                    and plane.check_point_by_ray_casting(loc["coordinates"])
                ):
                    entered = True

                if entered:
                    logmsg = f"{datetime.now()}, {time.time_ns()}: {plane.flight}, {plane.registry}, {plane.type} has entered {aoi}. Alt: {plane.alt_baro:.0f}, Hdg: {plane.nav_hdg:.0f} VS: {plane.vertical_speed:.0f}"
                    logging.info(logmsg)
                    write_simple_msg_to_log(logmsg, AOI_MSG_PATH)
                    plane.entered_aois.append(aoi)


def monitor_adsb_radio_traffic():
    """
    entry point for monitoring script
    """

    adsbstreamer, streamdata = start_adsb_radio_listener(ip="192.168.0.151")
    stream_start_time = time.time()

    tracked_planes = {}
    location_name = sys.argv[-1]
    global locations
    locations = get_aoi_locations()
    monitored_loc = locations["ground_aois"][location_name]
    total_seen = 0
    log_update_t = 0
    while adsbstreamer:
        # streamdata is constantly updated and not thread-safe.
        # Make a copy in case an aircraft's broadcast goes stale during this iteration
        data = copy(streamdata)
        seen_adsb_hexcodes = []
        for key, adsb in data.items():
            if "category" in adsb:
                if adsb["category"] in MONITORED_CATEGORIES:
                    adsbhex = adsb["hex"]
                    seen_adsb_hexcodes.append(adsbhex)
                    if adsbhex in tracked_planes:
                        if adsb["now"] != tracked_planes[adsbhex].status["now"]:
                            try:
                                update_tracked_plane_information(tracked_planes[adsbhex], adsb, monitored_loc)
                                write_single_adsb_response_to_log(tracked_planes[adsbhex])
                                check_if_inside_aois(tracked_planes[adsbhex])
                            except Exception as e:
                                logging.error(f"couldn't update {adsb}, {e}")
                    else:
                        if "r" in adsb and "flight"  in adsb:
                            tracked_planes[adsbhex] = Plane(adsb["r"], adsb["flight"], adsb)
                            logging.info(
                                f"created new tracking entry: flight: {adsb['flight']}, type: {adsb['t']}, registry: {adsb['r']} "
                            )
                            total_seen += 1
        if time.monotonic() - log_update_t > LOGGER_INFO_OUTPUT_SECS:
            logging.debug(
                f"monitoring {len(tracked_planes)} A5 aircraft. monitor running for {(time.time() - stream_start_time)/3600:.1f}h. A5 aircraft seen: {total_seen}"
            )
            log_update_t = time.monotonic()

        timed_out = [adsbhex for adsbhex in tracked_planes if adsbhex not in seen_adsb_hexcodes]
        if timed_out:
            for adsbhex in timed_out:
                goodbye = tracked_planes[adsbhex]
                logging.info(f"{goodbye.flight} ({goodbye.type} has timed out.")
                del tracked_planes[adsbhex]
        time.sleep(2)


if __name__ == "__main__":
    monitor_adsb_radio_traffic()
