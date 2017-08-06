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
Update = telegram.Update
Params = analytics.Event.Params


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
    telegram_successful = True
    analytics_successful = True
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
        mock_telegram(self.telegram_successful)
        mock_analytics(self.analytics_successful)

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

    update = {
        Update.Field.UPDATE_ID.value: 1,
        Update.Type.MESSAGE.value: {
            Update.Field.MESSAGE_ID.value: 1,
            Update.Field.FROM.value: {Update.Field.ID.value: 2,
                                      Update.Field.NAME.value: "name"},
            Update.Field.DATE.value: 3,
            Update.Field.CHAT.value: {Update.Field.ID.value: 4,
                                      Update.Field.TYPE.value: "private"},
            Update.Field.TEXT.value: "sample message"}}

    correct_telegram_json = {
        Update.Field.CHAT_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.CHAT.value][
                Update.Field.ID.value],
        Update.Field.TEXT.value: application.INSTRUCTIONS}

    correct_params_for_received = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.MESSAGE.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.USER.value,
        Params.EVENT_LABEL.value:
            update[Update.Type.MESSAGE.value][Update.Field.TEXT.value],
        Params.USER_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.FROM.value][
                Update.Field.ID.value]}

    correct_params_for_sent = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.INSTRUCTIONS.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.BOT.value,
        Params.EVENT_LABEL.value: update[Update.Field.UPDATE_ID.value],
        Params.USER_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.FROM.value][
                Update.Field.ID.value]}


class TestUnsuccessfulReplyToMessage(BaseTest):
    telegram_successful = False

    correct_number_of_calls = 3

    correct_telegram_method = telegram.api_send_message

    update = copy.copy(TestMessage.update)
    update[Update.Field.UPDATE_ID.value] = 11

    correct_telegram_json = {
        Update.Field.CHAT_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.CHAT.value][
                Update.Field.ID.value],
        Update.Field.TEXT.value: application.INSTRUCTIONS}

    correct_params_for_sent = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.FAILED.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.BOT.value,
        Params.EVENT_LABEL.value: update[Update.Field.UPDATE_ID.value],
        Params.USER_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.FROM.value][
                Update.Field.ID.value]}


class TestStartMessage(BaseTest):
    correct_number_of_calls = 5

    correct_telegram_method = telegram.api_send_message

    update = {Update.Field.UPDATE_ID.value: 2,
              Update.Type.MESSAGE.value: {
                  Update.Field.MESSAGE_ID.value: 1,
                  Update.Field.FROM.value: {Update.Field.ID.value: 2,
                                            Update.Field.NAME.value: "name"},
                  Update.Field.DATE.value: 3,
                  Update.Field.CHAT.value: {Update.Field.ID.value: 4,
                                            Update.Field.TYPE.value: "private"},
                  Update.Field.TEXT.value: Update.Field.START.value}}

    correct_telegram_json = {
        Update.Field.CHAT_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.CHAT.value][
                Update.Field.ID.value],
        Update.Field.TEXT.value: application.HELLO}

    correct_params_for_received = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.START.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.USER.value,
        Params.EVENT_LABEL.value:
            update[Update.Type.MESSAGE.value][Update.Field.CHAT.value][
                Update.Field.ID.value],
        Params.USER_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.FROM.value][
                Update.Field.ID.value]}

    correct_params_for_sent = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.GREETINGS.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.BOT.value,
        Params.EVENT_LABEL.value: update[Update.Field.UPDATE_ID.value],
        Params.USER_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.FROM.value][
                Update.Field.ID.value]}


class TestUnsuccessfulReplyToStartMessage(BaseTest):
    telegram_successful = False

    correct_number_of_calls = 3

    correct_telegram_method = telegram.api_send_message

    update = copy.copy(TestStartMessage.update)
    update[Update.Field.UPDATE_ID.value] = 21

    correct_telegram_json = {
        Update.Field.CHAT_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.CHAT.value][
                Update.Field.ID.value],
        Update.Field.TEXT.value: application.HELLO}

    correct_params_for_sent = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.FAILED.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.BOT.value,
        Params.EVENT_LABEL.value: update[Update.Field.UPDATE_ID.value],
        Params.USER_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.FROM.value][
                Update.Field.ID.value]}


class TestInlineQuery(BaseTest):
    correct_number_of_calls = 3

    correct_telegram_method = telegram.api_answer_inline_query

    update = {Update.Field.UPDATE_ID.value: 3,
              Update.Type.INLINE_QUERY.value: {
                  Update.Field.ID.value: 1,
                  Update.Field.FROM.value: {
                      Update.Field.ID.value: 2,
                      Update.Field.NAME.value: "name"},
                  Update.Field.QUERY.value: "text to make tiny"}}

    correct_telegram_json = {
        "inline_query_id": update[Update.Type.INLINE_QUERY.value][
            Update.Field.ID.value],
        "results": [{Update.Field.TYPE.value: "article",
                     Update.Field.ID.value: "0",
                     "title": "Choose this to send your tiny text!",
                     "description": "ᵗᵉˣᵗ ᵗᵒ ᵐᵃᵏᵉ ᵗᶦⁿʸ",
                     "input_message_content": {
                         "message_text": "ᵗᵉˣᵗ ᵗᵒ ᵐᵃᵏᵉ ᵗᶦⁿʸ"}}]}

    correct_params_for_received = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.PREVIEW.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.USER.value,
        Params.EVENT_LABEL.value: update[Update.Field.UPDATE_ID.value],
        Params.USER_ID.value:
            update[Update.Type.INLINE_QUERY.value][Update.Field.FROM.value][
                Update.Field.ID.value]}


class TestUnsuccessfulReplyToInlineQuery(BaseTest):
    telegram_successful = False

    correct_number_of_calls = 3

    correct_telegram_method = telegram.api_answer_inline_query

    update = copy.copy(TestInlineQuery.update)
    update[Update.Field.UPDATE_ID.value] = 31

    correct_telegram_json = {
        "inline_query_id": update[Update.Type.INLINE_QUERY.value][
            Update.Field.ID.value],
        "results": [{Update.Field.TYPE.value: "article",
                     Update.Field.ID.value: "0",
                     "title": "Choose this to send your tiny text!",
                     "description": "ᵗᵉˣᵗ ᵗᵒ ᵐᵃᵏᵉ ᵗᶦⁿʸ",
                     "input_message_content": {
                         "message_text": "ᵗᵉˣᵗ ᵗᵒ ᵐᵃᵏᵉ ᵗᶦⁿʸ"}}]}

    correct_params_for_sent = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.FAILED.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.BOT.value,
        Params.EVENT_LABEL.value: update[Update.Field.UPDATE_ID.value],
        Params.USER_ID.value:
            update[Update.Type.INLINE_QUERY.value][Update.Field.FROM.value][
                Update.Field.ID.value]}


class TestChosenInlineQuery(BaseTest):
    correct_number_of_calls = 2

    update = {Update.Field.UPDATE_ID.value: 4,
              Update.Type.CHOSEN_INLINE_RESULT.value: {
                  "result_id": "0",
                  Update.Field.FROM.value: {Update.Field.ID.value: 2,
                                            Update.Field.NAME.value: "name"},
                  Update.Field.QUERY.value: Update.Field.QUERY.value}}

    correct_params_for_received = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.EVENT_ACTION.value: analytics.Event.Action.SENT.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.USER.value,
        Params.USER_ID.value: update[Update.Type.CHOSEN_INLINE_RESULT.value][
            Update.Field.FROM.value][
            Update.Field.ID.value]}


# Does not inherit from BaseTest as there will be two sets of outgoing
# requests – one set for the first time the update is received, and another
# for handling the duplicate.
class TestDuplicates(object):
    # 5 for the first update, and 2 for the duplicate
    correct_number_of_calls = 5 + 2

    update = copy.copy(TestMessage.update)
    update[Update.Field.UPDATE_ID.value] = 5

    correct_params_for_duplicate = {
        Params.VERSION.value: 1,
        Params.TOKEN_ID.value: ANALYTICS_TOKEN,
        Params.TYPE.value: Params.EVENT.value,
        Params.USER_ID.value:
            update[Update.Type.MESSAGE.value][Update.Field.FROM.value][
                Update.Field.ID.value],
        Params.EVENT_ACTION.value: analytics.Event.Action.DUPLICATE.value,
        Params.EVENT_CATEGORY.value: analytics.Event.Category.USER.value,
        Params.EVENT_LABEL.value: update[Update.Field.UPDATE_ID.value]}

    @responses.activate
    @pytest.fixture(scope="class")
    def calls(self, app):
        mock_telegram()
        mock_analytics()

        application.processed_updates.clear()

        app.post("/" + TELEGRAM_TOKEN,
                 data=json.dumps(self.update),
                 content_type="application/json")
        response = app.post("/" + TELEGRAM_TOKEN,
                            data=json.dumps(self.update),
                            content_type="application/json")
        assert response.status_code == 200

        # For reasons unknown, responses.calls doesn't persist
        calls_copy = copy.deepcopy(responses.calls)
        return calls_copy

    def test_calls(self, calls):
        assert len(calls) == self.correct_number_of_calls

    def test_analytics_duplicate_message(self, calls):
        debug_duplicate_request = calls[5].request
        assert analytics.analytics_debug in debug_duplicate_request.url
        debug_received_params = get_params(debug_duplicate_request)
        assert debug_received_params == self.correct_params_for_duplicate

        log_duplicate_request = calls[6].request
        assert analytics.analytics_real in log_duplicate_request.url
        log_received_params = get_params(log_duplicate_request)
        assert log_received_params == self.correct_params_for_duplicate

    def test_tracker(self):
        assert len(application.processed_updates) == 1
