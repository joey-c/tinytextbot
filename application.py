import json
import tiny
from enum import Enum
import os
from flask import Flask
from flask import request
import requests as outgoing_requests

application = Flask(__name__)
application.debug = True
TOKEN = os.environ["TELEGRAM_TOKEN"]
api_base = "https://api.telegram.org/bot" + TOKEN + "/"
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


fields = {Field.UPDATE_ID: "update_id",
          Field.FROM: "from",
          Field.ID: "id",
          Field.CHAT: "chat",
          Field.MESSAGE: "message",
          Field.SUCCESSFUL: "ok",
          Field.DESCRIPTION: "description",
          Field.RESULT: "result",
          Field.INLINE_QUERY: "inline_query",
          Field.QUERY: "query"}


def check_response(response):
    response_json = response.json()
    successful = response_json[fields[Field.SUCCESSFUL]]
    response_text = None
    if successful:
        response_text = response_json[fields[Field.RESULT]]
    else:
        response_text = response_json[fields[Field.DESCRIPTION]]
    return successful, response_text


def send_message(chat_id, message_text):
    message = {"chat_id": chat_id, "text": message_text}
    response = outgoing_requests.post(api_send_message, json=message)
    return check_response(response)


def new_user(update):
    # To-do: store
    # user_id = update[fields[Field.MESSAGE]][fields[Field.FROM]][fields[Field.ID]]
    chat_id = update[fields[Field.MESSAGE]][fields[Field.CHAT]][fields[Field.ID]]
    greeting = tiny.convert_string("hello")
    response = send_message(chat_id, greeting)
    return ""


def tinify(update):
    inline_query = update[fields[Field.INLINE_QUERY]]
    query_id = inline_query[fields[Field.ID]]
    result = Result(inline_query[fields[Field.QUERY]])
    answer = {"inline_query_id": query_id, "results": [result.__dict__]}
    response = outgoing_requests.post(api_answer_inline_query, json=answer)
    response_result = check_response(response)
    return ""


routers = {UpdateType.MESSAGE: new_user,
           UpdateType.INLINE_QUERY: tinify}


@application.route("/" + TOKEN, methods=['POST'])
def route_message():
    update = request.get_json()
    update_type = list(filter(
        lambda possible_update_type: possible_update_type in update,
        update_types.keys()))[0]
    route = routers[update_types[update_type]]
    return route(update)
