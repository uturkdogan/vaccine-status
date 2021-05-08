import os

import logging

LOGGING_LEVEL = int(os.getenv('LOGGING_LEVEL', 20))
logging.basicConfig(
    level=LOGGING_LEVEL)

from vaccine_status import tweeter

if __name__ == '__main__':
    tweeter.main()
