import os
import urllib.parse

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


class TestMessage(object):
    pass


class TestStartMessage(object):
    pass


class TestInlineQuery(object):
    pass


class TestChosenInlineQuery(object):
    pass
