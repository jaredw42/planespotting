"""
adsb_radio_listener.py
thread class that connects to a readsb net-json port and stores messages by adsb hex in a managed dict
"""
import json
import socket
import time
from threading import Thread
from typing import Literal

from absl import logging

# constants
DEFAULT_RCV_BYTES = 4096  # [int]
LOCAL_IP = "192.168.0.151"
EXTERNAL_IP = "23.93.23.15"
READSB_JSON_PORT = 8181

DEBUG_MSG_OUTPUT_SEC = 20  # [s]
STREAM_TIMEOUT_SEC = 60  # [s]

LOG_DATETIME_FORMAT = "%Y%M%D - %H%M%S,uuu"


class AdsbRadioStreamer(Thread):
    def __init__(
        self, handled_dict: dict, ip: str = EXTERNAL_IP, port: int = READSB_JSON_PORT, verbosity: Literal = logging.DEBUG
    ) -> None:

        super().__init__()

        self.data = handled_dict
        self.sock = socket.create_connection((ip, port))
        self.stream_adsb_json_data()
        self.run()

    def clear_stale_data_entries(self) -> int:

        """
        check data dict for entries with a last message older than time threshold
        and remove if necessary.
        """

        stale = [msg["hex"] for msg in self.data.values() if (self.now - msg["now"]) > STREAM_TIMEOUT_SEC]
        for msg in stale:
            logging.info(f"{msg} has gone stale, deleting entry")
            del self.data[msg]
        return len(stale)

    def process_incoming_data(self, incoming):
        """
        attempt to parse JSON object from incoming socket data
        """

        data = incoming.splitlines()
        for msg in data:
            if b"flight" in msg:
                try:
                    jsonmsg = json.loads(msg, parse_float=float, parse_int=int)
                    self.data[jsonmsg["hex"]] = jsonmsg
                    # store last decoded timestamp for timeout checking
                    self.now = jsonmsg["now"]
                except json.JSONDecodeError:
                    logging.info(f"couldnt decode {msg}")
                    #
                except Exception as e:
                    # TODO - remove this general case
                    logging.info(e)
                    logging.info(f"couldnt decode {msg}")

    def stream_adsb_json_data(self, blksize=DEFAULT_RCV_BYTES):
        """
        stream data from readsb net-json socket.
        """
        i = 0
        logging.info(f"start streaming ADSB json data.")
        log_update_t = 0
        while self.sock:
            data = self.sock.recv(blksize)
            self.process_incoming_data(data)
            i += 1
            if time.monotonic() - log_update_t > DEBUG_MSG_OUTPUT_SEC:

                cleared = self.clear_stale_data_entries()
                logging.info(
                    f"adsb streamer decoded {i} msgs in {DEBUG_MSG_OUTPUT_SEC} sec. receving {len(self.data)} aircraft. {cleared} just timed out."
                )
                log_update_t = time.monotonic()
                i = 0


if __name__ == "__main__":
    pass
