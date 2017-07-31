import logging
import time

from sortedcontainers import SortedDict


class SortedDictWithMaxSize(SortedDict):
    def __init__(self, name, max_size=100):
        super().__init__()
        self.name = name
        self.max_size = max_size

    def add(self, value):
        current_size = len(self)
        logger = logging.getLogger(self.name)
        logger.debug("Current size is " + str(current_size) + ".")

        if current_size >= self.max_size:
            # Remove enough keys such that there is space for one new item.
            number_of_keys_to_remove = current_size - self.max_size + 1
            keys_to_remove = self.keys()[:number_of_keys_to_remove]
            logger.info("Removing " + str(number_of_keys_to_remove) + " keys.")
            for key in keys_to_remove:
                del self[key]
                logger.debug("Removed " + str(key) + ".")

        time_now = time.time()
        self[time_now] = value
        logger.info("Added " + str(time_now) + ":" + str(value) + ".")
