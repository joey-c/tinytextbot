import json
import tiny
from enum import Enum
import os
from flask import Flask
from flask import request


application = Flask(__name__)
application.debug = True
TOKEN = os.environ["TELEGRAM_TOKEN"]
api_base = "https://api.telegram.org/bot" + TOKEN + "/"
api_send_message = api_base + "sendMessage"




class Result(object):
    """docstring for Result"""
    def __init__(self, query):
        super(Result, self).__init__()
        self.type = "article"
        self.id = str(hash(query))
        self.title = query
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


fields = {Field.UPDATE_ID: "update_id",
          Field.FROM: "from",
          Field.ID: "id",
          Field.CHAT: "chat"}


def tinify(update):
    inline_query = update["inline_query"]
    query = inline_query["query"]
    return Result(query).to_json()


routers = {UpdateType.INLINE_QUERY: tinify}


@application.route("/", methods=['POST'])
def route_message():
    update = request.get_json()
    update_type = list(filter(
        lambda possible_update_type: possible_update_type in update,
        update_types.keys()))[0]
    route = routers[update_types[update_type]]
    return route(update)
