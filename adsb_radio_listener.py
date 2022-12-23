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

STREAM_TIMEOUT_SEC = 30  # [s]


class AdsbRadioStreamer(Thread):
    def __init__(
        self, handled_dict: dict, ip: str = EXTERNAL_IP, port: int = READSB_JSON_PORT, verbosity: Literal = logging.DEBUG
    ) -> None:

        super().__init__()
        logging.set_verbosity(verbosity)
        self.data = handled_dict
        self.sock = socket.create_connection((ip, port))
        self.stream_adsb_json_data()
        self.run()

    def clear_stale_data_entries(self) -> int:

        stale = [msg["hex"] for msg in self.data.values() if (self.now - msg["now"]) > STREAM_TIMEOUT_SEC]
        for msg in stale:
            logging.info(f"{msg} has gone stale, deleting entry")
            del self.data[msg]
        return len(stale)

    def process_incoming_data(self, incoming):

        data = incoming.splitlines()
        for msg in data:
            if b"flight" in msg:
                try:
                    jsonmsg = json.loads(msg, parse_float=float, parse_int=int)
                    self.data[jsonmsg["hex"]] = jsonmsg
                    self.now = jsonmsg["now"]
                except json.JSONDecodeError:
                    logging.info(f"couldnt decode {msg}")
                except Exception as e:
                    logging.info(e)
                    logging.info(f"couldnt decode {msg}")

    def stream_adsb_json_data(self, blksize=DEFAULT_RCV_BYTES):
        i = 0
        loop_start = time.monotonic()
        while self.sock:
            data = self.sock.recv(blksize)
            self.process_incoming_data(data)
            i += 1

            if i > 100:
                cleared = self.clear_stale_data_entries()
                logging.info(
                    f"adsb streamerreceived 100 msgs in {time.monotonic() - loop_start} sec. receving {len(self.data)} aircraft. {cleared} just timed out."
                )
                i = 0
                loop_start = time.monotonic()


if __name__ == "__main__":
    pass
