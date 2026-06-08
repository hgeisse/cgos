#
# server.py -- main program of the server
#


import sys
import traceback

from app.cgos import runServer


if __name__ == "__main__":
    try:
        runServer()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
