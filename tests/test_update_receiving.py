import os
import json
import urllib.parse
import copy

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


@pytest.fixture(scope="module")
def app():
    application.application.testing = True
    return application.application.test_client()


 # Outgoing requests should be:
    #   1. telegram – send message in reaction to message received
    #   2. analytics debug – validate hit to log message received
    #   3. analytics real – log message received
    #   4. analytics debug – validate hit to log message sent
    #   5. analytics real – log message sent
# Note: telegram reply takes precedence for performance reasons.
class TestMessage(object):
    message = {"update_id": 0,
               "message": {"message_id": 1,
                           "from": {"id": 2,
                                    "first_name": "name"},
                           "date": 3,
                           "chat": {"id": 4,
                                    "type": "private"},
                           "text": "sample message"}}

    correct_params_for_received = {"v": 1,
                                   "tid": ANALYTICS_TOKEN,
                                   "t": "event",
                                   "ea": "Message",
                                   "ec": "User",
                                   "el": message["message"]["text"],
                                   "uid": message["message"]["from"]["id"]}

    correct_params_for_sent = {"v": 1,
                               "tid": ANALYTICS_TOKEN,
                               "t": "event",
                               "ea": "Instructions",
                               "ec": "Bot",
                               "uid": message["message"]["from"]["id"]}

    correct_telegram_json = {"chat_id": message["message"]["chat"]["id"],
                             "text": application.INSTRUCTIONS}

    @responses.activate
    @pytest.fixture(scope="class")
    def calls(self, app):
        mock_telegram()
        mock_analytics()

        response = app.post("/" + TELEGRAM_TOKEN,
                            data=json.dumps(TestMessage.message),
                            content_type="application/json")
        assert response.status_code == 200

        # For reasons unknown, responses.calls doesn't persist
        calls_copy = copy.deepcopy(responses.calls)
        return calls_copy

    def test_calls(self, calls):
        assert len(calls) == 5

    def test_telegram(self, calls):
        telegram_request = calls[0].request
        assert telegram.api_send_message in telegram_request.url

        correct_telegram_json = json.dumps(TestMessage.correct_telegram_json)
        assert telegram_request.body.decode(UTF8) == correct_telegram_json

    def test_analytics_message_received(self, calls):
        debug_received_request = calls[1].request
        assert analytics.analytics_debug in debug_received_request.url
        debug_received_params = get_params(debug_received_request)
        assert debug_received_params == TestMessage.correct_params_for_received

        log_received_request = calls[2].request
        assert analytics.analytics_real in log_received_request.url
        log_received_params = get_params(log_received_request)
        assert log_received_params == TestMessage.correct_params_for_received

    def test_analytics_message_sent(self, calls):
        debug_sent_request = calls[3].request
        assert analytics.analytics_debug in debug_sent_request.url
        debug_sent_params = get_params(debug_sent_request)
        assert debug_sent_params == TestMessage.correct_params_for_sent

        log_sent_request = calls[4].request
        assert analytics.analytics_real in log_sent_request.url
        log_sent_params = get_params(log_sent_request)
        assert log_sent_params == TestMessage.correct_params_for_sent


class TestStartMessage(object):
    pass


class TestInlineQuery(object):
    pass


class TestChosenInlineQuery(object):
    pass
