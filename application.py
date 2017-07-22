import json
import tiny
from enum import Enum
import os
import logging
import math
import time
from sortedcontainers import SortedDict
from flask import Flask
from flask import request
import requests as outgoing_requests


logging.basicConfig(filename='/opt/python/log/my.log',
                    level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%d/%m/%Y %I:%M:%S %p')


application = Flask(__name__)
application.debug = True

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
api_base = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/"
api_send_message = api_base + "sendMessage"
api_answer_inline_query = api_base + "answerInlineQuery"

TIMEOUT = 7  # in seconds


class Result(object):
    """docstring for Result"""
    def __init__(self, query):
        super(Result, self).__init__()
        self.type = "article"
        self.id = str(hash(query))
        self.title = "Choose this to send your tiny text!"
        self.description = tiny.convert_string(query)
        self.input_message_content = {"message_text": self.description}

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
        MESSAGE = "message"
        SUCCESSFUL = "ok"
        DESCRIPTION = "description"
        RESULT = "result"
        INLINE_QUERY = "inline_query"
        QUERY = "query"
        TEXT = "text"
        DATE = "date"
        MESSAGE_ID = "message_id"


# Track the latest unique updates to prevent spamming users with multiple responses.
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


processed_updates = SortedDictWithMaxSize("tracker.processed_updates")
ignored_updates = SortedDictWithMaxSize("tracker.ignored_updates")


def check_response(response):
    successful = False
    response_text = ""
    if response:
        response_json = response.json()
        successful = response_json[Update.Field.SUCCESSFUL.value]
        if not successful:
            response_text = response_json[Update.Field.DESCRIPTION.value]
    return successful, response_text


def post_to_telegram(destination, json_data, error_message):
    response = None

    try:
        response = outgoing_requests.post(destination, json=json_data, timeout=TIMEOUT)
        response.raise_for_status()
    except outgoing_requests.Timeout:
        logging.getLogger("connection").info("Timed out after " + str(TIMEOUT) + " seconds. " + error_message)
    except outgoing_requests.ConnectionError:
        logging.getLogger("connection").info("A network problem occurred. " + error_message)
    except outgoing_requests.HTTPError:
        logging.getLogger("connection").info("HTTP request failed with error code " + response.status_code + ". " +
                                             error_message)

    return response


def send_message(chat_id, message_text, error_message):
    message = {"chat_id": chat_id, "text": message_text}
    response = post_to_telegram(api_send_message, message, error_message)
    return check_response(response)


def message_to_bot(update, update_id):
    user_id = update[Update.Field.MESSAGE.value][Update.Field.FROM.value][Update.Field.ID.value]
    logging.getLogger("user").info("id: " + str(user_id))

    message = update[Update.Field.MESSAGE.value]
    message_id = message[Update.Field.MESSAGE_ID.value]
    message_date = message[Update.Field.DATE.value]
    message_text = message[Update.Field.TEXT.value]
    chat_id = message[Update.Field.CHAT.value][Update.Field.ID.value]
    logging.getLogger("user.message").debug(
        "Message " + str(message_id) +
        " at " + str(message_date) +
        " by user " + str(user_id) +
        " in chat " + str(chat_id) +
        ": \"" + message_text + "\""
    )

    if message_text is "/start":
        return new_user(update_id, chat_id, user_id, message_id)

    instructions = "To use this bot, enter \"@tinytextbot\" followed by your desired message " \
                   "in the chat you want to send tiny text to. " \
                   "Tap on the message preview to select and send the converted message."
    response_success, response_text = send_message(chat_id,
                                                   instructions,
                                                   "Failed to send instructions to " + user_id + ".")

    logging.getLogger("bot.response.message").debug(
        "To " + str(message_id) +
        " by " + str(user_id) +
        " in " + str(chat_id) +
        " was successful: " + str(response_success) +
        ". " + response_text
    )

    if response_success:
        processed_updates.add(update_id)

    return ""


def new_user(update_id, chat_id, user_id, message_id):
    greeting = tiny.convert_string("hello")
    response_success, response_text = send_message(chat_id,
                                                   greeting,
                                                   "Failed to send greeting to " + user_id + ".")

    logging.getLogger("bot.response.message").debug(
        "To " + str(message_id) +
        " by new user" + user_id +
        " in " + str(chat_id) +
        " was successful: " + str(response_success) +
        ". " + response_text
    )

    if response_success:
        processed_updates.add(update_id)


def tinify(update, update_id):
    inline_query = update[Update.Field.INLINE_QUERY.value]
    query_id = inline_query[Update.Field.ID.value]
    query = inline_query[Update.Field.QUERY.value]
    result = Result(query)
    answer = {"inline_query_id": query_id, "results": [result.__dict__]}

    response = post_to_telegram(api_answer_inline_query,
                                answer,
                                "Failed to answer inline query id " + str(query_id) + ".")
    response_success, response_text = check_response(response)

    logging.getLogger("bot.response.inline_query").debug(
        "answer: \"" + result.description +
        "\" to " + str(query_id) +
        " was successful: " + str(response_success) +
        ". " + response_text
    )

    if response_success:
        processed_updates.add(update_id)

    return ""


routers = {Update.Type.MESSAGE: message_to_bot,
           Update.Type.INLINE_QUERY: tinify}


@application.route("/" + TELEGRAM_TOKEN, methods=['POST'])
def route_message():
    result = ""

    update = request.get_json()
    update_id = update[Update.Field.UPDATE_ID.value]
    if update_id in processed_updates.values() or update_id in ignored_updates.values():
        logging.getLogger("tracker").info("Ignoring update " + str(update_id) + ".")
        return result

    update_type = list(filter(lambda possible_type: possible_type.value in update,
                              Update.Type))[0]

    if update_type in routers:
        result = routers[update_type](update, update_id)
    else:
        ignored_updates.add(update_id)

    return result
