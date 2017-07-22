import logging
import math
import time

from sortedcontainers import SortedDict


class SortedDictWithMaxSize(SortedDict):
    def __init__(self, name, max_size=100, buffer=0.1):
        super(SortedDictWithMaxSize, self).__init__()
        self.name = name
        self.max_size = max_size
        self.buffer = math.ceil(buffer * max_size)

    def add(self, value):
        current_size = len(self)
        logger = logging.getLogger(self.name)
        logger.debug("Current size is " + str(current_size) + ".")

        if current_size >= self.max_size:
            keys_to_remove = self.keys()[:self.buffer]
            logger.info("Removing " + str(len(keys_to_remove)) + " keys.")
            for key in keys_to_remove:
                del self[key]
                logger.debug("Removed " + str(key) + ".")

        time_now = time.time()
        self[time_now] = value
        logger.info("Added " + str(time_now) + ":" + str(value) + ".")
