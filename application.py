import logging

import flask

import analytics
import telegram
import tiny
from sorted_dict_with_max_size import SortedDictWithMaxSize

logging.basicConfig(filename='/opt/python/log/my.log',
                    level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - '
                           '%(message)s',
                    datefmt='%d/%m/%Y %I:%M:%S %p')

application = flask.Flask(__name__)
application.debug = True

CONNECTION_TIMEOUT = 7  # in seconds
HELLO = tiny.convert_string("hello")
INSTRUCTIONS = "To use this bot, enter \"@tinytextbot\" followed by " \
               "your desired message in the chat you want to send " \
               "tiny text to. Tap on the message preview to select and " \
               "send the converted message."

# Track the latest unique updates to prevent spamming users with multiple
# responses to the same update.
processed_updates = SortedDictWithMaxSize("tracker.processed_updates")
ignored_updates = SortedDictWithMaxSize("tracker.ignored_updates")


# Sends a Telegram message
def send_message(chat_id, message_text, error_message):
    message = {"chat_id": chat_id, "text": message_text}
    response = telegram.post(telegram.api_send_message,
                             message,
                             error_message,
                             connection_timeout=CONNECTION_TIMEOUT)
    return telegram.check_response(response)


# Sends a Telegram message after receiving a message.
# If the received message is "/start", which is automatically sent when a user
# begins interacting with the bot, the bot will reply with a standard greeting.
# Else, the bot will reply with usage instructions.
def message_to_bot_handler(update, update_id):
    fields = telegram.Update.Field
    user_id = telegram.get_user_id(update, telegram.Update.Type.MESSAGE)
    message = update[fields.MESSAGE.value]
    message_id = message[fields.MESSAGE_ID.value]
    message_date = message[fields.DATE.value]
    message_text = message[fields.TEXT.value]
    chat_id = message[fields.CHAT.value][fields.ID.value]

    logging.getLogger("user.message").debug("Message " + str(message_id) +
                                            " at " + str(message_date) +
                                            " by user " + str(user_id) +
                                            " in chat " + str(chat_id) +
                                            ": \"" + message_text + "\"")

    if message_text is "/start":
        return greet_new_user(update_id, chat_id, user_id, message_id)

    response_success, response_text = send_message(
        chat_id,
        INSTRUCTIONS,
        "Failed to send instructions to " + str(user_id) + ".")

    logging.getLogger("bot.response.message").debug(
        "To " + str(message_id) +
        " by " + str(user_id) +
        " in " + str(chat_id) +
        " was successful: " + str(response_success) + ". " +
        response_text)

    if response_success:
        processed_updates.add(update_id)

        analytics.update(user_id,
                         analytics.Event.Category.USER,
                         analytics.Event.Action.MESSAGE,
                         event_label=message_text)

        analytics.update(user_id,
                         analytics.Event.Category.BOT,
                         analytics.Event.Action.INSTRUCTIONS)

    return ""


# Sends a greeting
def greet_new_user(update_id, chat_id, user_id, message_id):
    greeting = HELLO
    response_success, response_text = send_message(
        chat_id,
        greeting,
        "Failed to send greeting to " + str(user_id) + ".")

    logging.getLogger("bot.response.message").debug(
        "To " + str(message_id) +
        " by new user" + str(user_id) +
        " in " + str(chat_id) +
        " was successful: " + str(response_success) +
        ". " + response_text)

    if response_success:
        processed_updates.add(update_id)

    analytics.update(user_id,
                     analytics.Event.Category.USER,
                     analytics.Event.Action.START,
                     event_label=chat_id)

    return ""


# Unwraps a query and responds with the query in tiny text.
def inline_query_handler(update, update_id):
    fields = telegram.Update.Field
    inline_query = update[fields.INLINE_QUERY.value]
    query = inline_query[fields.QUERY.value]
    if not query:
        ignored_updates.add(update_id)
        return ""

    user_id = telegram.get_user_id(update, telegram.Update.Type.INLINE_QUERY)
    query_id = inline_query[fields.ID.value]

    analytics.update(user_id,
                     analytics.Event.Category.USER,
                     analytics.Event.Action.PREVIEW)

    result = telegram.Result(tiny.convert_string(query))
    answer = {"inline_query_id": query_id, "results": [result.__dict__]}

    response = telegram.post(
        telegram.api_answer_inline_query,
        answer,
        "Failed to answer inline query id " + str(query_id) + ".",
        connection_timeout=CONNECTION_TIMEOUT)
    response_success, response_text = telegram.check_response(response)

    logging.getLogger("bot.response.inline_query").debug(
        "Answer: \"" + result.description +
        "\" to " + str(query_id) +
        " was successful: " + str(response_success) + ". " +
        response_text)

    if response_success:
        processed_updates.add(update_id)

    return ""


# Updates analytics that a query result was chosen, and hence sent.
def result_chosen_handler(update, update_id):
    logging.getLogger("user.sent").info("Confirmation received.")
    user_id = telegram.get_user_id(update,
                                   telegram.Update.Type.CHOSEN_INLINE_RESULT)
    update_result = analytics.update(user_id,
                                     analytics.Event.Category.USER,
                                     analytics.Event.Action.SENT)
    if update_result:
        processed_updates.add(update_id)

    return ""


routes = {telegram.Update.Type.MESSAGE: message_to_bot_handler,
          telegram.Update.Type.INLINE_QUERY: inline_query_handler,
          telegram.Update.Type.CHOSEN_INLINE_RESULT: result_chosen_handler}


# Route the incoming update to the relevant handlers.
# If the update is a previously processed update (i.e. Telegram repeated it),
# or if the update is not a supported type as defined in routers,
# ignore the update, and return a 200.
@application.route("/" + telegram.TOKEN, methods=['POST'])
def route_update():
    result = ""

    update = flask.request.get_json()
    update_id = update[telegram.Update.Field.UPDATE_ID.value]
    user_id = telegram.get_user_id(update, update_id)
    if update_id in processed_updates.values() or \
       update_id in ignored_updates.values():
        logger = logging.getLogger("tracker")
        logger.info("Ignoring update " + str(update_id) + ".")
        return result

    update_type = list(
        filter(lambda possible_type: possible_type.value in update,
               telegram.Update.Type))

    if update_type:
        update_type = update_type[0]
    else:
        logger = logging.getLogger("telegram.update")
        logger.info("Unknown update type received. " + str(update))
        return result

    if update_type in routes:
        result = routes[update_type](update, update_id)
    else:
        logging.getLogger("telegram.update").info("Ignoring update: " +
                                                  str(update))
        ignored_updates.add(update_id)

    return result
