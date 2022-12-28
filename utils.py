"""
utils.py
utility functions shared by modules
"""
import datetime
import json
import os
from pathlib import Path
from threading import local, Thread
from multiprocessing import Process, Manager

from adsb_radio_listener import AdsbRadioStreamer, LOCAL_IP, EXTERNAL_IP, READSB_JSON_PORT


DEFAULT_LOG_DIR = Path(Path.home(), f"data/planespotting/ {str(datetime.date.today()).replace('-','')}")
DEFAULT_SIMPLE_LOG_NAME = Path(DEFAULT_LOG_DIR, "planespotting_msgs.txt")
DEFAULT_HEX_LOG_PATH = Path(os.getcwd(), "resources/known_adsb_hex_codes.json")


def write_simple_msg_to_log(msg, log_file=DEFAULT_SIMPLE_LOG_NAME):
    """
    conveinience function to appends simple strings to debugging log.
    creates the log and parent directories if they do not exist
    """

    if not log_file.parent.exists():
        log_file.parent.mkdir(parents=True)
        log_file.touch()
    if not msg.endswith("\n"):
        msg = msg + "\n"

    with log_file.open("at") as f:
        f.write(msg)


def write_single_adsb_response_to_log(plane, log_dir=DEFAULT_LOG_DIR):
    """
    conveinience function to append adsb response to log.
    creates the log and parent directories if they do not exist
    """
    outpath = Path(log_dir, plane.status["t"], plane.registry + ".txt")
    if not outpath.exists():
        if not outpath.parent.exists():
            outpath.parent.mkdir(parents=True)
        outpath.touch()
    with outpath.open("at") as f:
        writestr = json.dumps(plane.status)
        if not writestr.endswith("\n"):
            writestr += "\n"
        f.write(writestr)


def start_adsb_radio_listener(ip=LOCAL_IP, port=READSB_JSON_PORT):
    """
    start an AdsbRadioListener in a new thread and create a managed dict
    to share stream data outside of thread
    """

    manager = Manager()
    handled_dict = manager.dict()
    streamer = Thread(
        target=AdsbRadioStreamer,
        daemon=True,
        args=(
            handled_dict,
            ip,
            port,
        ),
    )

    streamer.start()
    return [streamer, handled_dict]


if __name__ == "__main__":
    pass
