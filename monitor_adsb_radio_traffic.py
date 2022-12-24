"""
monitor_adsb_radio_traffic.py

"""
from copy import copy
import json
import os
from pathlib import Path
import requests
import time

from absl import logging

from adsb_radio_listener import EXTERNAL_IP

from plane import Plane
from utils import (
    start_adsb_radio_listener,
    write_single_adsb_response_to_log,
    DEFAULT_HEX_LOG_PATH,
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

def get_locations():
    locpath = Path(os.getcwd(),"resources/locations.json")

    with open(locpath, 'rt') as f:
        locations = json.load(f)

    return locations

def get_flight_data_from_aeroapi(flight: str):

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
            # TODO - implement fallback logic


def update_tracked_plane_information(plane: Plane, data: dict, coords) -> None:
    # print(f"updating plane: {data['r']}")
    plane.update_status(data)
    distance = plane.calculate_distance_to_point(coords) / 1000.
    logging.info(f"flight {plane.flight} ({plane.type}) is {distance:.1f} km from emeryville ")


def get_known_adsb_hex_codes(jsonpath: Path = DEFAULT_HEX_LOG_PATH):

    adsbdata = {}
    with open(jsonpath, "rt") as f:
        raw = f.readlines()
        for line in raw:
            data = json.loads(line)
            adsbdata[data["hex"]] = data

    return adsbdata



def monitor_adsb_radio_traffic():

    stuff = start_adsb_radio_listener()
    stream = stuff[0]
    streamdata = stuff[1]
    stream_start_time = time.time()

    tracked_planes = {}

    locations = get_locations()
    oakland_coords = locations['ground_aois'][3]['coordinates']


    while stream:
        updated = False
        # streamdata is constantly updated, make a copy to iterate through
        data = copy(streamdata)
        for key, adsb in data.items():
            if "category" in adsb:
                if adsb["category"] in MONITORED_CATEGORIES:
                    adsbhex = adsb["hex"]
                    if adsbhex in tracked_planes:
                        try:
                            update_tracked_plane_information(tracked_planes[adsbhex], adsb, oakland_coords)
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
        if not updated:
            logging.debug(f"no A5 aircraft currently tracked. monitor running for {time.time() - stream_start_time:.1f}s. A5 aircraft seen: {len(tracked_planes)}  ")
        time.sleep(2)

if __name__ == "__main__":
    monitor_adsb_radio_traffic()
