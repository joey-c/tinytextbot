import json
import logging
import os
from enum import Enum

import requests


class Result(object):
    def __init__(self, result):
        super().__init__()
        self.type = "article"
        self.id = "0"
        self.title = "Choose this to send your tiny text!"
        self.description = result
        self.input_message_content = {"message_text": result}

    def to_json(self):
        return json.dumps(self.__dict__, ensure_ascii=False)


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
        SUCCESSFUL = "ok"
        DESCRIPTION = "description"
        RESULT = "result"
        QUERY = "query"
        TEXT = "text"
        DATE = "date"
        MESSAGE_ID = "message_id"
        NAME = "first_name"
        TYPE = "type"
        CHAT_ID = "chat_id"
        START = "/start"


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
        response = requests.post(destination,
                                 json=json_data,
                                 timeout=connection_timeout)
        response.raise_for_status()
    except requests.Timeout:
        logger.info("Timed out after " + str(connection_timeout) +
                    " seconds. " + error_message)
    except requests.ConnectionError:
        logger.info("A network problem occurred. " + error_message)
    except requests.HTTPError:
        logger.info("HTTP request failed with error code " +
                    str(response.status_code) + ". " + error_message)
    finally:
        logger.debug(str(json_data))

    return response


def get_user_id(update, update_type):
    update_types = {
        Update.Type.MESSAGE: get_user_id_from_message,
        Update.Type.INLINE_QUERY: get_user_id_from_inline_query,
        Update.Type.CHOSEN_INLINE_RESULT: get_user_id_from_chosen_inline_result
    }
    return update_types[update_type](update)


def get_user_id_from_message(update):
    message = update[Update.Type.MESSAGE.value]
    return message[Update.Field.FROM.value][Update.Field.ID.value]


def get_user_id_from_inline_query(update):
    inline_query = update[Update.Type.INLINE_QUERY.value]
    return inline_query[Update.Field.FROM.value][Update.Field.ID.value]


def get_user_id_from_chosen_inline_result(update):
    chosen_result = update[Update.Type.CHOSEN_INLINE_RESULT.value]
    return chosen_result[Update.Field.FROM.value][Update.Field.ID.value]


def get_update_type(update):
    update_type = list(
        filter(lambda possible_type: possible_type.value in update,
               Update.Type))
    if len(update_type) == 1:
        return update_type[0]
