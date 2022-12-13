"""
utils.py
utility functions shared by modules
"""

import json
from pathlib import Path


DEFAULT_LOG_DIR = Path("/home/jared/data/planespotting/20221213")
DEFAULT_SIMPLE_LOG_NAME = Path(DEFAULT_LOG_DIR, "planespotting_msgs.txt")


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


if __name__ == "__main__":
    pass
