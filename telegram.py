import json
import logging
import os
from enum import Enum

import requests as outgoing_requests

import tiny


class Result(object):
    def __init__(self, result_type, id):
        super().__init__()
        self.type = result_type
        self.id = id

    def to_json(self):
        return json.dumps(self.__dict__, ensure_ascii=False)


class ArticleResult(Result):
    def __init__(self, query):
        super().__init__("article", str(hash(query)))
        self.title = "Choose this to send your tiny text!"
        self.description = tiny.convert_string(query)
        self.input_message_content = {"message_text": self.description}



class Update(object):
    class Type(Enum):
        MESSAGE = "message"
        EDITED_MESSAGE = "edited_message"
        CHANNEL_POST = "channel_post"
        EDITED_CHANNEL_POST = "edited_channel_post"
        INLINE_QUERY = "inline_query"
        CHOSEN_INLINE_RESULT = "chosen_inline_result"
        CALLBACK_QUERY = "callback_query"
        SHIPPING_QUERY = "shipping_query"
        PRE_CHECKOUT_QUERY = "pre_checkout_query"

    class Field(Enum):
        UPDATE_ID = "update_id"
        FROM = "from"
        ID = "id"
        CHAT = "chat"
        MESSAGE = "message"
        SUCCESSFUL = "ok"
        DESCRIPTION = "description"
        RESULT = "result"
        INLINE_QUERY = "inline_query"
        QUERY = "query"
        TEXT = "text"
        DATE = "date"
        MESSAGE_ID = "message_id"


TOKEN = os.environ["TELEGRAM_TOKEN"]
api_base = "https://api.telegram.org/bot" + TOKEN + "/"
api_send_message = api_base + "sendMessage"
api_answer_inline_query = api_base + "answerInlineQuery"


# Unwraps Telegrams's response and returns a boolean successful and
# the accompanying reasons.
def check_response(response):
    successful = False
    response_text = ""
    if response:
        response_json = response.json()
        successful = response_json[Update.Field.SUCCESSFUL.value]
        if not successful:
            response_text = response_json[Update.Field.DESCRIPTION.value]
    return successful, response_text


# Sends json_data to the destination with a connection_timeout.
# Catches common possible connection errors and logs them with error_message.
def post(destination, json_data, error_message, connection_timeout=7):
    response = None
    logger = logging.getLogger("connection")

    try:
        response = outgoing_requests.post(destination,
                                          json=json_data,
                                          timeout=connection_timeout)
        response.raise_for_status()
    except outgoing_requests.Timeout:
        logger.info("Timed out after " + str(connection_timeout) +
                    " seconds. " + error_message)
    except outgoing_requests.ConnectionError:
        logger.info("A network problem occurred. " + error_message)
    except outgoing_requests.HTTPError:
        logger.info("HTTP request failed with error code " +
                    str(response.status_code) + ". " + error_message)

    return response
