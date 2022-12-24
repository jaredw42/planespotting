"""
monitor_adsb_radio_traffic.py
starts an AdsbRadioStreamer and watches for aircraft of interest.
calculates range and bearing to each aircraft.
"""
from copy import copy
import json
import os
from pathlib import Path
import requests
import sys
import time

from absl import logging


from plane import Plane
from utils import (
    start_adsb_radio_listener,
    write_single_adsb_response_to_log,
)

# constants
ADSB_CATEGORY_HEAVY = "A5"
MONITORED_CATEGORIES = [ADSB_CATEGORY_HEAVY]
logging.set_verbosity(logging.DEBUG)

AEROAPI_BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
AEROAPI_KEY = os.environ["AEROAPI_KEY"]
AEROAPI = requests.Session()
AEROAPI.headers.update({"x-apikey": AEROAPI_KEY})

STATUS_EN_ROUTE = "En Route"


def get_aoi_locations():
    """
    load json file with areas of interest.
    """
    locpath = Path(os.getcwd(), "resources/locations.json")

    with open(locpath, "rt") as f:
        locations = json.load(f)

    return locations


def get_flight_data_from_aeroapi(flight: str):
    """
    given a flight number, generate a aeroapi response request
    and filter by flights currently 'En Route'
    """

    headers = {"x-apikey": AEROAPI_KEY}
    flight = flight.strip()
    api_resource = f"/flights/{flight}"
    payload = {"max_pages": 1}
    url = f"{AEROAPI_BASE_URL}{api_resource}"
    response = requests.request("GET", url, headers=headers, params=payload)
    if response.status_code == 200:
        enroute = [flt for flt in response.text if "En Route" in flt["status"]]
        if enroute:
            logging.info(f"En Route data found for {flight}")
            return enroute[0]
        else:
            logging.error(f"no info found for {flight}")


def update_tracked_plane_information(plane: Plane, data: dict, location) -> None:
    """
    update plane state with latest message.
    """
    coords = location["coordinates"]
    name = location["name"]
    plane.update_status(data)
    distance = plane.calculate_distance_to_point(coords)["spherical"] / 1000.0
    bearing = plane.calculate_bearing_from_point(coords)
    logging.info(f"flight {plane.flight} ({plane.type}) is {distance:.1f} km, {bearing:.1f} deg from {name} ")


def monitor_adsb_radio_traffic():
    """
    entry point for monitoring script
    """

    stuff = start_adsb_radio_listener()
    stream = stuff[0]
    streamdata = stuff[1]
    stream_start_time = time.time()

    tracked_planes = {}
    location_name = sys.argv[-1]
    locations = get_aoi_locations()
    monitored_loc = locations[location_name]
    total_seen = 0

    while stream:
        updated = False
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
                                updated = True
                            except Exception as e:
                                logging.info(f"couldn't update {adsb}, {e}")
                    else:
                        tracked_planes[adsbhex] = Plane(adsb["r"], adsb["flight"], adsb)
                        logging.info(
                            f"created new tracking entry: flight: {adsb['flight']}, type: {adsb['t']}, registry: {adsb['r']} "
                        )
                        updated = True
                        total_seen +=1
        if not updated:
            logging.debug(
                f"no A5 aircraft updates. monitor running for {time.time() - stream_start_time:.1f}s. A5 aircraft seen: {total_seen}"
            )
            timed_out = [adsbhex for adsbhex in tracked_planes if adsbhex not in seen_adsb_hexcodes]
            if timed_out:
                for adsbhex in timed_out:
                    goodbye = tracked_planes[adsbhex]
                    logging.info(f"{goodbye.flight} ({goodbye.type} has timed out.")
                    del goodbye
        else:
            logging.debug(
                f"monitoring {len(tracked_planes)} A5 aircraft. monitor running for {time.time() - stream_start_time:.1f}s. A5 aircraft seen: {total_seen}"
            )
        time.sleep(2)


if __name__ == "__main__":
    monitor_adsb_radio_traffic()
