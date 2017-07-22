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


class UpdateType(Enum):
    MESSAGE = 0
    EDITED_MESSAGE = 1
    CHANNEL_POST = 2
    EDITED_CHANNEL_POST = 3
    INLINE_QUERY = 4
    CHOSEN_INLINE_RESULT = 5
    CALLBACK_QUERY = 6
    SHIPPING_QUERY = 7
    PRE_CHECKOUT_QUERY = 8


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


update_types = {"message": UpdateType.MESSAGE,
                "edited_message": UpdateType.EDITED_MESSAGE,
                "channel_post": UpdateType.CHANNEL_POST,
                "edited_channel_post": UpdateType.EDITED_CHANNEL_POST,
                "inline_query": UpdateType.INLINE_QUERY,
                "chosen_inline_result": UpdateType.CHOSEN_INLINE_RESULT,
                "callback_query": UpdateType.CALLBACK_QUERY,
                "shipping_query": UpdateType.SHIPPING_QUERY,
                "pre_checkout_query": UpdateType.PRE_CHECKOUT_QUERY}


class Field(Enum):
    UPDATE_ID = 0
    FROM = 1
    ID = 2
    CHAT = 3
    MESSAGE = 4
    SUCCESSFUL = 5
    DESCRIPTION = 6
    RESULT = 7
    INLINE_QUERY = 8
    QUERY = 9
    TEXT = 10
    DATE = 11
    MESSAGE_ID = 12


fields = {Field.UPDATE_ID: "update_id",
          Field.FROM: "from",
          Field.ID: "id",
          Field.CHAT: "chat",
          Field.MESSAGE: "message",
          Field.SUCCESSFUL: "ok",
          Field.DESCRIPTION: "description",
          Field.RESULT: "result",
          Field.INLINE_QUERY: "inline_query",
          Field.QUERY: "query",
          Field.TEXT: "text",
          Field.DATE: "date",
          Field.MESSAGE_ID: "message_id"}


def check_response(response):
    response_json = response.json()
    successful = response_json[fields[Field.SUCCESSFUL]]
    response_text = ""
    if not successful:
        response_text = response_json[fields[Field.DESCRIPTION]]
    return successful, response_text


def send_message(chat_id, message_text):
    message = {"chat_id": chat_id, "text": message_text}
    response = outgoing_requests.post(api_send_message, json=message)
    return check_response(response)


def message_to_bot(update, update_id):
    user_id = update[fields[Field.MESSAGE]][fields[Field.FROM]][fields[Field.ID]]
    logging.getLogger("user").info("id: " + str(user_id))

    message = update[fields[Field.MESSAGE]]
    message_id = message[fields[Field.MESSAGE_ID]]
    message_date = message[fields[Field.DATE]]
    message_text = message[fields[Field.TEXT]]
    chat_id = message[fields[Field.CHAT]][fields[Field.ID]]
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
    response_success, response_text = send_message(chat_id, instructions)

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
    response_success, response_text = send_message(chat_id, greeting)
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
    inline_query = update[fields[Field.INLINE_QUERY]]
    query_id = inline_query[fields[Field.ID]]
    query = inline_query[fields[Field.QUERY]]
    result = Result(query)
    answer = {"inline_query_id": query_id, "results": [result.__dict__]}
    response = outgoing_requests.post(api_answer_inline_query, json=answer)

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


routers = {UpdateType.MESSAGE: message_to_bot,
           UpdateType.INLINE_QUERY: tinify}


@application.route("/" + TELEGRAM_TOKEN, methods=['POST'])
def route_message():
    result = ""

    update = request.get_json()
    update_id = update[fields[Field.UPDATE_ID]]
    if update_id in processed_updates.values() or update_id in ignored_updates.values():
        logging.getLogger("tracker").info("Ignoring update " + str(update_id) + ".")
        return result

    update_type = list(filter(
        lambda possible_update_type: possible_update_type in update,
        update_types.keys()))[0]

    if update_types[update_type] in routers:
        route = routers[update_types[update_type]]
        result = route(update, update_id)
    else:
        ignored_updates.add(update_id)

    return result
