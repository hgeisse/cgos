#
# timeutils.py -- utility functions for handling date and time
#


import datetime
import time


def now_string() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S")


def now_seconds() -> int:
    return time.time_ns() // 1_000_000_000


def now_milliseconds() -> int:
    return time.time_ns() // 1_000_000
