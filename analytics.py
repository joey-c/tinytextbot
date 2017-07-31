import logging
import os
from enum import Enum

import requests


TOKEN = os.environ["ANALYTICS_TOKEN"]
analytics = "https://www.google-analytics.com/"
analytics_debug = analytics + "debug/collect"
analytics_real = analytics + "collect"
base_payload = {"v": "1",
                "tid": TOKEN,
                "t": "event"}


class Event(object):
    class Category(Enum):
        USER = "User"
        BOT = "Bot"

    class Action(Enum):
        PREVIEW = "Preview"
        SENT = "Sent"
        START = "Start"
        MESSAGE = "Message"
        INSTRUCTIONS = "Instructions"


# Sends a payload containing base_payload and params to Google Analytics.
# If the hit is valid as verified by sending it to analytics_debug,
# then the hit will be sent to analytics_real.
def update(user_id, event_category, event_action, event_label=None, timeout=7):
    logger = logging.getLogger("Analytics")
    params = build_params(user_id, event_category, event_action, event_label)
    valid = validate_hit(params, timeout)
    if valid:
        response = send(analytics_real, params, timeout)
        if response:
            logger.info("Successfully updated with " + str(params))
    return valid


# Sends params to analytics_debug to check if the hit is valid.
def validate_hit(params, timeout):
    logger = logging.getLogger("Analytics")
    response = send(analytics_debug, params, timeout=timeout)
    valid = False
    if response:
        result = response.json()["hitParsingResult"][0]
        valid = result["valid"]
        if not valid:
            logger.info("Invalid update occurred.")
            logger.debug(str(result["parserMessage"]))
    return valid


# Sends params to destination via url-encoding.
# Catches common connection errors.
def send(destination, params, timeout):
    response = None
    logger = logging.getLogger("connection.analytics")
    try:
        response = requests.post(destination,
                                 params=params,
                                 timeout=timeout)
    except requests.Timeout:
        logger.info("Timed out after " + str(timeout) + " seconds. ")
    except requests.ConnectionError:
        logger.info("A network problem occurred. ")
    except requests.HTTPError:
        logger.info("HTTP request failed with error code " +
                    str(response.status_code) + ". ")
    return response


def build_params(user_id, event_category, event_action, event_label):
    params = {"uid": user_id,
              "ec": event_category.value,
              "ea": event_action.value}

    if event_label:
        params.update(el=event_label)

    params.update(base_payload)
    return params
