import json
import tiny
from flask import Flask


app = Flask(__name__)
app.debug = True


@app.route("/<string:input_string>")
def tinify(input_string):
    return Result(input_string).to_json()


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
