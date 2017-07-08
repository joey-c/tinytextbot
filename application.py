import json
import tiny
import os
from flask import Flask
from flask import request


application = Flask(__name__)
application.debug = True
TOKEN = os.environ["TELEGRAM_TOKEN"]
api_base = "https://api.telegram.org/bot" + TOKEN + "/"
api_send_message = api_base + "sendMessage"


@application.route("/", methods=['POST'])
def post_tinify():
    update = request.get_json()
    inline_query = update["inline_query"]
    query = inline_query["query"]
    return Result(query).to_json()


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
