import logging

from flask import Flask
from flask import request

import telegram
import tiny
from sorted_dict import SortedDictWithMaxSize

logging.basicConfig(filename='/opt/python/log/my.log',
                    level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%d/%m/%Y %I:%M:%S %p')

application = Flask(__name__)
application.debug = True

CONNECTION_TIMEOUT = 7  # in seconds

# Track the latest unique updates to prevent spamming users with multiple responses.
processed_updates = SortedDictWithMaxSize("tracker.processed_updates")
ignored_updates = SortedDictWithMaxSize("tracker.ignored_updates")


def send_message(chat_id, message_text, error_message):
    message = {"chat_id": chat_id, "text": message_text}
    response = telegram.post(telegram.api_send_message, message, error_message, connection_timeout=CONNECTION_TIMEOUT)
    return telegram.check_response(response)


def message_to_bot(update, update_id):
    message = update[telegram.Update.Field.MESSAGE.value]
    user_id = message[telegram.Update.Field.FROM.value][telegram.Update.Field.ID.value]
    message_id = message[telegram.Update.Field.MESSAGE_ID.value]
    message_date = message[telegram.Update.Field.DATE.value]
    message_text = message[telegram.Update.Field.TEXT.value]
    chat_id = message[telegram.Update.Field.CHAT.value][telegram.Update.Field.ID.value]

    logging.getLogger("user.message").debug("Message " + str(message_id) +
                                            " at " + str(message_date) +
                                            " by user " + str(user_id) +
                                            " in chat " + str(chat_id) +
                                            ": \"" + message_text + "\"")

    if message_text is "/start":
        return new_user(update_id, chat_id, user_id, message_id)

    instructions = "To use this bot, enter \"@tinytextbot\" followed by your desired message " \
                   "in the chat you want to send tiny text to. " \
                   "Tap on the message preview to select and send the converted message."
    response_success, response_text = send_message(chat_id,
                                                   instructions,
                                                   "Failed to send instructions to " + str(user_id) + ".")

    logging.getLogger("bot.response.message").debug("To " + str(message_id) +
                                                    " by " + str(user_id) +
                                                    " in " + str(chat_id) +
                                                    " was successful: " + str(response_success) +
                                                    ". " + response_text)

    if response_success:
        processed_updates.add(update_id)

    return ""


def new_user(update_id, chat_id, user_id, message_id):
    greeting = tiny.convert_string("hello")
    response_success, response_text = send_message(chat_id,
                                                   greeting,
                                                   "Failed to send greeting to " + str(user_id) + ".")

    logging.getLogger("bot.response.message").debug("To " + str(message_id) +
                                                    " by new user" + str(user_id) +
                                                    " in " + str(chat_id) +
                                                    " was successful: " + str(response_success) +
                                                    ". " + response_text)

    if response_success:
        processed_updates.add(update_id)

    return ""


def tinify(update, update_id):
    inline_query = update[telegram.Update.Field.INLINE_QUERY.value]
    query_id = inline_query[telegram.Update.Field.ID.value]
    query = inline_query[telegram.Update.Field.QUERY.value]

    result = telegram.Result(query)
    answer = {"inline_query_id": query_id, "results": [result.__dict__]}

    response = telegram.post(telegram.api_answer_inline_query,
                             answer,
                             "Failed to answer inline query id " + str(query_id) + ".",
                             connection_timeout=CONNECTION_TIMEOUT)
    response_success, response_text = telegram.check_response(response)

    logging.getLogger("bot.response.inline_query").debug("Answer: \"" + result.description +
                                                         "\" to " + str(query_id) +
                                                         " was successful: " + str(response_success) +
                                                         ". " + response_text)

    if response_success:
        processed_updates.add(update_id)

    return ""


routers = {telegram.Update.Type.MESSAGE: message_to_bot,
           telegram.Update.Type.INLINE_QUERY: tinify}


@application.route("/" + telegram.TOKEN, methods=['POST'])
def route_message():
    result = ""

    update = request.get_json()
    update_id = update[telegram.Update.Field.UPDATE_ID.value]
    if update_id in processed_updates.values() or update_id in ignored_updates.values():
        logging.getLogger("tracker").info("Ignoring update " + str(update_id) + ".")
        return result

    update_type = list(filter(lambda possible_type: possible_type.value in update,
                              telegram.Update.Type))[0]

    if update_type in routers:
        result = routers[update_type](update, update_id)
    else:
        ignored_updates.add(update_id)

    return result
