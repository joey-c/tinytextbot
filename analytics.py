import logging
import os
from enum import Enum

import requests as outgoing_requests

from application import CONNECTION_TIMEOUT

ANALYTICS_TOKEN = os.environ["ANALYTICS_TOKEN"]
analytics = "https://www.google-analytics.com/"
analytics_debug = analytics + "debug/collect"
analytics_real = analytics + "collect"
base_payload = {"v": "1",
                "tid": ANALYTICS_TOKEN,
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
def update(params):
    params.update(base_payload)
    response = send_to_analytics(analytics_debug, params)
    logger = logging.getLogger("Analytics")

    successful = False
    if response:
        result = response.json()["hitParsingResult"][0]
        successful = result["valid"]
        if not successful:
            logger.info("Invalid update occurred.")
            logger.debug(str(result["parserMessage"]))

    if successful:
        response = send_to_analytics(analytics_real, params)
        if response:
            logger.info("Successfully updated with " + str(params))

    return successful


# Sends params to destination via url-encoding.
# Catches common connection errors.
def send_to_analytics(destination, params):
    response = None
    logger = logging.getLogger("connection.analytics")
    try:
        response = outgoing_requests.post(destination,
                                          params=params,
                                          timeout=CONNECTION_TIMEOUT)
    except outgoing_requests.Timeout:
        logger.info("Timed out after " + str(CONNECTION_TIMEOUT) +
                    " seconds. ")
    except outgoing_requests.ConnectionError:
        logger.info("A network problem occurred. ")
    except outgoing_requests.HTTPError:
        logger.info("HTTP request failed with error code " +
                    str(response.status_code) + ". ")
    return response


def build_params(user_id, event_category, event_action, event_label=None):
    params = {"uid": user_id,
              "ec": event_category.value,
              "ea": event_action.value}

    if event_label:
        params.update(el=event_label)

    return params
