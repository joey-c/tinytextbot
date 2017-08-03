import os
import json
import urllib.parse
import copy
from enum import Enum

import pytest
import responses

import application
import analytics
import telegram

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANALYTICS_TOKEN = os.environ["ANALYTICS_TOKEN"]
UTF8 = "UTF-8"


def get_params(request):
    query = urllib.parse.urlparse(request.path_url).query
    params_in_lists = urllib.parse.parse_qs(query)
    params = {}
    for key, value in params_in_lists.items():
        val = value[0]
        try:
            params[key] = int(val)
        except ValueError:
            params[key] = val
    return params


def mock_analytics(valid=True):
    analytics_json_response = {"hitParsingResult": [{"valid": valid}]}
    responses.add(method=responses.POST,
                  url=analytics.analytics_debug,
                  status=200,
                  json=analytics_json_response)
    responses.add(method=responses.POST,
                  url=analytics.analytics_real,
                  status=200)


def mock_telegram(successful=True):
    telegram_json_response = {"ok": successful,
                              "description": "some error message"}
    responses.add(method=responses.POST,
                  url=telegram.api_send_message,
                  status=200,
                  json=telegram_json_response)
    responses.add(method=responses.POST,
                  url=telegram.api_answer_inline_query,
                  status=200,
                  json=telegram_json_response)


# Scoping test_client doesn't really work.
@pytest.fixture(scope="module")
def app():
    application.application.testing = True
    return application.application.test_client()


class BaseTest(object):
    update = None
    correct_number_of_calls = None
    correct_telegram_method = None
    correct_telegram_json = None
    correct_params_for_received = None
    correct_params_for_sent = None

    class CallType(Enum):
        TELEGRAM = 0
        ANALYTICS_RECEIVED = 1
        ANALYTICS_SENT = 2

    # Outgoing requests should be in the following order, where available:
    #   1. telegram – send message in reaction to message received
    #   2. analytics debug – validate hit to log message received
    #   3. analytics real – log message received
    #   4. analytics debug – validate hit to log message sent
    #   5. analytics real – log message sent
    # Note: telegram reply takes precedence for performance reasons.
    def get_call_position(self, call_type):
        position = 0
        if call_type == self.CallType.TELEGRAM:
            pass
        elif call_type == self.CallType.ANALYTICS_RECEIVED:
            if self.correct_telegram_method:
                position = 1
            else:
                position = 0
        elif call_type == self.CallType.ANALYTICS_SENT:
            if self.correct_telegram_method and \
                    self.correct_params_for_received:
                position = 3
            elif self.correct_telegram_method:
                position = 1
            elif self.correct_params_for_received:
                position = 2
        return position

    @responses.activate
    @pytest.fixture(scope="class")
    def calls(self, app):
        mock_telegram()
        mock_analytics()

        response = app.post("/" + TELEGRAM_TOKEN,
                            data=json.dumps(self.update),
                            content_type="application/json")
        assert response.status_code == 200

        # For reasons unknown, responses.calls doesn't persist
        calls_copy = copy.deepcopy(responses.calls)
        return calls_copy

    def test_calls(self, calls):
        assert len(calls) == self.correct_number_of_calls

    def test_telegram(self, calls):
        if not self.correct_telegram_method:
            return

        call_position = self.get_call_position(self.CallType.TELEGRAM)
        telegram_request = calls[call_position].request
        assert self.correct_telegram_method in telegram_request.url

        correct_telegram_json = json.dumps(self.correct_telegram_json)
        assert telegram_request.body.decode(UTF8) == correct_telegram_json

    def test_analytics_message_received(self, calls):
        if not self.correct_params_for_received:
            return

        call_position = self.get_call_position(
            self.CallType.ANALYTICS_RECEIVED)
        debug_received_request = calls[call_position].request
        assert analytics.analytics_debug in debug_received_request.url
        debug_received_params = get_params(debug_received_request)
        assert debug_received_params == self.correct_params_for_received

        log_received_request = calls[call_position + 1].request
        assert analytics.analytics_real in log_received_request.url
        log_received_params = get_params(log_received_request)
        assert log_received_params == self.correct_params_for_received

    def test_analytics_message_sent(self, calls):
        if not self.correct_params_for_sent:
            return

        call_position = self.get_call_position(self.CallType.ANALYTICS_SENT)
        debug_sent_request = calls[call_position].request
        assert analytics.analytics_debug in debug_sent_request.url
        debug_sent_params = get_params(debug_sent_request)
        assert debug_sent_params == self.correct_params_for_sent

        log_sent_request = calls[call_position + 1].request
        assert analytics.analytics_real in log_sent_request.url
        log_sent_params = get_params(log_sent_request)
        assert log_sent_params == self.correct_params_for_sent


class TestMessage(BaseTest):
    correct_number_of_calls = 5

    correct_telegram_method = telegram.api_send_message

    update = {"update_id": 0,
              "message": {"message_id": 1,
                          "from": {"id": 2,
                                   "first_name": "name"},
                          "date": 3,
                          "chat": {"id": 4,
                                   "type": "private"},
                          "text": "sample message"}}

    correct_telegram_json = {"chat_id": update["message"]["chat"]["id"],
                             "text": application.INSTRUCTIONS}

    correct_params_for_received = {"v": 1,
                                   "tid": ANALYTICS_TOKEN,
                                   "t": "event",
                                   "ea": "Message",
                                   "ec": "User",
                                   "el": update["message"]["text"],
                                   "uid": update["message"]["from"]["id"]}

    correct_params_for_sent = {"v": 1,
                               "tid": ANALYTICS_TOKEN,
                               "t": "event",
                               "ea": "Instructions",
                               "ec": "Bot",
                               "el": update["update_id"],
                               "uid": update["message"]["from"]["id"]}


class TestStartMessage(BaseTest):
    correct_number_of_calls = 5

    correct_telegram_method = telegram.api_send_message

    update = {"update_id": 1,
              "message": {"message_id": 1,
                          "from": {"id": 2,
                                   "first_name": "name"},
                          "date": 3,
                          "chat": {"id": 4,
                                   "type": "private"},
                          "text": "/start"}}

    correct_telegram_json = {"chat_id": update["message"]["chat"]["id"],
                             "text": application.HELLO}

    correct_params_for_received = {"v": 1,
                                   "tid": ANALYTICS_TOKEN,
                                   "t": "event",
                                   "ea": "Start",
                                   "ec": "User",
                                   "el": update["message"]["chat"]["id"],
                                   "uid": update["message"]["from"]["id"]}

    correct_params_for_sent = {"v": 1,
                               "tid": ANALYTICS_TOKEN,
                               "t": "event",
                               "ea": "Greetings",
                               "ec": "Bot",
                               "el": update["update_id"],
                               "uid": update["message"]["from"]["id"]}


class TestInlineQuery(BaseTest):
    correct_number_of_calls = 3

    correct_telegram_method = telegram.api_answer_inline_query

    update = {"update_id": 2,
              "inline_query": {"id": 1,
                               "from": {"id": 2,
                                        "first_name": "name"},
                               "query": "text to make tiny"}}

    correct_telegram_json = {
        "inline_query_id": update["inline_query"]["id"],
        "results": [{"type": "article",
                     "id": "0",
                     "title": "Choose this to send your tiny text!",
                     "description": "ᵗᵉˣᵗ ᵗᵒ ᵐᵃᵏᵉ ᵗᶦⁿʸ",
                     "input_message_content": {
                         "message_text": "ᵗᵉˣᵗ ᵗᵒ ᵐᵃᵏᵉ ᵗᶦⁿʸ"}}]}

    correct_params_for_received = {"v": 1,
                                   "tid": ANALYTICS_TOKEN,
                                   "t": "event",
                                   "ea": "Preview",
                                   "ec": "User",
                                   "el": update["update_id"],
                                   "uid": update["inline_query"]["from"]["id"]}


class TestChosenInlineQuery(BaseTest):
    correct_number_of_calls = 2

    update = {"update_id": 3,
              "chosen_inline_result": {"result_id": "0",
                                       "from": {"id": 2,
                                                "first_name": "name"},
                                       "query": "query"}}

    correct_params_for_received = {
        "v": 1,
        "tid": ANALYTICS_TOKEN,
        "t": "event",
        "ea": "Sent",
        "ec": "User",
        "uid": update["chosen_inline_result"]["from"]["id"]}
