"""
get_adsb_data.py
python script for interacting with adsbexchange API.
"""
import json
import requests
import sys
import time

from absl import logging

from plane import Plane
from utils import write_simple_msg_to_log, write_single_adsb_response_to_log

# constants
ADSB_CATEGORY_HEAVY = "A5"  # string
ADSB_UPDATE_WAIT_SEC = 20  # [s]
URL_SFO_25_MILES = "https://adsbexchange-com1.p.rapidapi.com/v2/lat/37.5690174407/lon/-122.27613102/dist/25/"  # string


def get_request_and_filter_by_category(url, headers, category=ADSB_CATEGORY_HEAVY):
    """
    send http request to ADSBexchange API host and filter by ADSB category
    """

    print("getting heavy data")
    category_filter = f'"category":"{category}"'
    response = requests.request("GET", url, headers=headers)
    heavies = [x.rstrip(",") for x in response.text.splitlines() if category_filter in x]
    heavies = [json.loads(x) for x in heavies]
    return heavies


def get_adsb_data(key):

    """
    main loop for retrieving and filtering adsb data
    """

    url = URL_SFO_25_MILES

    headers = {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": "adsbexchange-com1.p.rapidapi.com",
    }

    ignored_planes = set()
    timed_out_registries = set()
    watched_plane_registries = set()
    watched_type_prefixes = ("B74", "B77", "A38", "A35", "A34")
    watched_planes = {}
    cnt = 0

    while True:

        start_time = time.monotonic()
        ignored = 0
        timed_out = 0
        currently_watching = 0
        heavies = get_request_and_filter_by_category(url, headers, ADSB_CATEGORY_HEAVY)

        for planedict in heavies:
            registry = planedict["r"]
            type = planedict["t"]
            if registry in ignored_planes:
                ignored += 1
                continue
            elif registry in timed_out_registries:
                timed_out += 1
                continue

            elif registry in watched_plane_registries:
                plane = watched_planes[registry]
                plane.update_status(planedict)
                if plane.position_updated:
                    write_single_adsb_response_to_log(plane)
                    watched_planes[registry] = plane
                    currently_watching += 1
                    continue

                if plane.stale_count > 10:
                    timed_out_registries.add(registry)
                    watched_plane_registries.remove(registry)
                    watched_planes[registry].pop()
                    continue

            if type[0:3] in watched_type_prefixes and registry not in timed_out_registries:
                try:
                    plane = Plane(registry, planedict["flight"], planedict)
                    watched_plane_registries.add(registry)
                    watched_planes[registry] = plane
                    write_single_adsb_response_to_log(plane)
                    printstr = f"NEW PLANE! (watched) local time: {time.asctime()}, type: {planedict['t']}, flight: {planedict['flight']}, lat: {planedict['lat']}, lon: {planedict['lon']}, alt: {planedict['alt_baro']}"
                    write_simple_msg_to_log(printstr)
                except Exception as e:
                    logging.error(f"{time.asctime()} couldn't add {planedict}, exception: {e}")
            else:
                try:
                    ignored_planes.add(planedict["r"])
                    printstr = f"NEW PLANE! (ignored) local time: {time.asctime()}, type: {planedict['t']}, flight: {planedict['flight']}, lat: {planedict['lat']}, lon: {planedict['lon']}, alt: {planedict['alt_baro']}"
                    print(printstr)
                    write_simple_msg_to_log(printstr)
                    ignored += 1

                except Exception as e:
                    print(f"exception:{e}, planedict: {planedict}")

        printstr = f"{time.asctime()} iteration: {cnt}. saw {len(heavies)} heavy aircraft. watched: {currently_watching}. currently ignoring: {ignored + timed_out}.  total ignored: {len(ignored_planes)} timed_out: {len(timed_out_registries)}, iteration time: {time.monotonic()-start_time}"
        print(printstr)
        write_simple_msg_to_log(printstr)
        cnt += 1
        print(f"sleeping {ADSB_UPDATE_WAIT_SEC - (time.monotonic() - start_time)} seconds.. ")
        while time.monotonic() - start_time < ADSB_UPDATE_WAIT_SEC:
            time.sleep(0.2)


def main():
    """
    entry point for script.
    """
    key = sys.argv[-1]
    if len(key) != 50:
        logging.error(f"{sys.argv[-1]} not valid adsbexchange rapidapi key. exiting.")
        exit(1)

    get_adsb_data(key)


main()
