"""
"""
import os
import requests

from absl import logging

logging.set_verbosity(logging.DEBUG)

AEROAPI_BASE_URL = "https://aeroapi.flightaware.com/aeroapi"
AEROAPI_KEY = os.environ["AEROAPI_KEY"]
AEROAPI = requests.Session()
AEROAPI.headers.update({"x-apikey": AEROAPI_KEY})


def main():
    headers = {"x-apikey": AEROAPI_KEY}

    while True:
        api_resource = "/flights/search"
        payload = {"max_pages": 1, "query": '-latlong "37.0 -122.0 38.0 -121.0"'}
        logging.info(f"Making AeroAPI request to GET {api_resource}")
        url = AEROAPI_BASE_URL + api_resource
        response = requests.request("GET", url, headers=headers, params=payload)
        # result = AEROAPI.get(f"{AEROAPI_BASE_URL}{api_resource}")
        print(response)


def example_2():
    # apiKey = parser.get(‘flightaware’, ‘fa_api_key’)
    apiUrl = "https://aeroapi.flightaware.com/aeroapi/"

    airport = "KSFO"
    payload = {"max_pages": 1}
    auth_header = {"x-apikey": AEROAPI_KEY}

    response = requests.get(apiUrl + f"airports/{airport}/flights", params=payload, headers=auth_header)

    if response.status_code == 200:
        print(response.json())
    else:
        print("Error executing request")


main()
# example_2()
