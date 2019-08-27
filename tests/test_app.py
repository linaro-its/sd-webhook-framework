#!/usr/bin/python3
""" Test the app code. """

import os
import sys
from unittest.mock import patch
import mock
import pytest

# Tell Python where to find the webhook automation code otherwise
# the test code isn't able to import it.
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
# pylint: disable=wrong-import-position
import app
import shared.globals
import shared.shared_sd


def test_hello_world():
    """ Test the hello_world route. """
    test_result = app.hello_world()
    assert test_result == "Hello, world!"


@mock.patch(
    'app.shared.globals.initialise_config',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_ticket_data',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_shared_sd',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_sd_auth',
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="206",
    autospec=True
)
def test_initialise(mock_rt, mi1, mi2, mi3, mi4):
    """ Test the app initialisation. """
    # The app code includes a variable called APP, so reference that
    # as flask_app to make the code clearer.
    flask_app = app.APP
    with flask_app.test_request_context('/'):
        test_result = app.initialise()
        assert mock_rt.called is True
        assert mi1.called is True
        assert mi2.called is True
        assert mi3.called is True
        assert mi4.called is True
        assert test_result is not None


@mock.patch(
    'app.shared.globals.initialise_config',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_ticket_data',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_shared_sd',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_sd_auth',
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="-1",
    autospec=True
)
def test_initialise_missing_handler(mock_rt, mi1, mi2, mi3, mi4):
    """ Test handling of a handler that needs to be loaded. """
    # The app code includes a variable called app, so reference that
    # as flask_app to make the code clearer.
    flask_app = app.APP
    with flask_app.test_request_context('/'):
        test_result = app.initialise()
        assert mock_rt.called is True
        assert mi1.called is True
        assert mi2.called is True
        assert mi3.called is True
        assert mi4.called is True
        assert test_result is None


@mock.patch(
    'app.shared.shared_sd.ticket_request_type',
    side_effect=shared.shared_sd.CustomFieldLookupFailure(),
    autospec=True
)
@mock.patch(
    'app.shared.shared_sd.post_comment',
    autospec=True
)
def test_initialise_handler_exception(mi1, mi2):
    """ Test handling of custom field lookup error. """
    handler = app.initialise_handler()
    assert mi1.called is True
    assert mi2.called is True
    assert handler is None


@mock.patch(
    'app.shared.globals.initialise_config',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_ticket_data',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_shared_sd',
    autospec=True
)
@mock.patch(
    'app.shared.globals.initialise_sd_auth',
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="-1",
    autospec=True
)
def test_initialise_missing_path(mock_rt, mi1, mi2, mi3, mi4):
    """ Test the code that adds the path to the handlers. """
    # The app code includes a variable called app, so reference that
    # as flask_app to make the code clearer.
    flask_app = app.APP
    with flask_app.test_request_context('/'):
        # Build the path to rt_handlers. Note that we need to go two levels
        # up ...
        dir_path = os.path.dirname(
            os.path.dirname(
                os.path.abspath(__file__)
            )) + "/rt_handlers"
        # pytest will have loaded at least one RT test, causing that path
        # to be added to sys.path, so we have to remove it to ensure full
        # coverage of app.initialise.
        sys.path.remove(dir_path)
        test_result = app.initialise()
        assert mock_rt.called is True
        assert mi1.called is True
        assert mi2.called is True
        assert mi3.called is True
        assert mi4.called is True
        assert test_result is None


# Need to have some mock handlers for testing the rest of the app code.
# For the purposes of mocking, ticket_data for create and comment will
# be strings.
#
# The functions use @staticmethod in order to avoid Python complaining
# that the methods could be functions (since they don't refer to the
# class, and the normal handlers aren't classes.)
class MockHandlerWithSaveTicketData:
    """ A mock handler class. """
    SAVE_TICKET_DATA = True

    CAPABILITIES = ["TRANSITION", "ASSIGNMENT", "CREATE", "COMMENT"]

    @staticmethod
    def create(ticket_data):
        """ Create handler. """
        print("Create function called with %s" % ticket_data)

    @staticmethod
    def comment(ticket_data):
        """ Comment handler. """
        print("Comment function called with %s" % ticket_data)

    @staticmethod
    def transition(status_from, status_to, ticket_data):
        """ Transition handler. """
        _ = ticket_data
        print("Transition from %s to %s" % (status_from, status_to))

    @staticmethod
    def assignment(assignee_from, assignee_to, ticket_data):
        """ Assignment handler. """
        _ = ticket_data
        print("Assigned from %s to %s" % (assignee_from, assignee_to))


class MockHandlerWithoutSaveTicketData:
    """ A mock handler class. """
    SAVE_TICKET_DATA = False

    CAPABILITIES = ["TRANSITION", "ASSIGNMENT", "CREATE", "COMMENT"]

    @staticmethod
    def create(ticket_data):
        """ Create handler. """
        print("Create function called with %s" % ticket_data)

    @staticmethod
    def comment(ticket_data):
        """ Comment handler. """
        print("Comment function called with %s" % ticket_data)

    @staticmethod
    def transition(status_from, status_to, ticket_data):
        """ Transition handler. """
        _ = ticket_data
        print("Transition from %s to %s" % (status_from, status_to))

    @staticmethod
    def assignment(assignee_from, assignee_to, ticket_data):
        """ Assignment handler. """
        _ = ticket_data
        print("Assigned from %s to %s" % (assignee_from, assignee_to))


def test_jira_hook_assignment(capsys):
    """ Test jira_hook assignment handling. """
    # We use patch.object here instead of @mock.patch because it is very
    # tricky to use features (capsys) in conjunction with mock params.
    with patch.object(
            app,
            'initialise',
            return_value=MockHandlerWithSaveTicketData()):
        with patch.object(
                app.shared_sd,
                'trigger_is_assignment',
                return_value=(True, "assignee_from", "assignee_to")
                ):
            with patch.object(
                    app.shared_sd,
                    'trigger_is_transition',
                    return_value=(False, None, None)
                ):
                with patch.object(
                        app.shared_sd,
                        'save_ticket_data_as_attachment',
                        return_value=None) as mock_save_ticket:
                    app.jira_hook()
                    assert mock_save_ticket.called is True
                    captured = capsys.readouterr()
                    assert captured.out == (
                        "Assigned from assignee_from to assignee_to\n")


def test_jira_hook_transition(capsys):
    """ Test jira_hook transition handling. """
    with patch.object(
            app,
            'initialise',
            return_value=MockHandlerWithoutSaveTicketData()):
        with patch.object(
                app.shared_sd,
                'trigger_is_assignment',
                return_value=(False, None, None)
                ):
            with patch.object(
                    app.shared_sd,
                    'trigger_is_transition',
                    return_value=(True, "status_from", "status_to")
                ):
                with patch.object(
                        app.shared_sd,
                        'save_ticket_data_as_attachment',
                        return_value=None) as mock_save_ticket:
                    app.jira_hook()
                    assert mock_save_ticket.called is False
                    captured = capsys.readouterr()
                    assert captured.out == (
                        "Transition from status_from to status_to\n")


def test_comment(capsys):
    """ Test comment handling. """
    shared.globals.TICKET_DATA = "ticket data"
    with patch.object(
            app,
            'initialise',
            return_value=MockHandlerWithSaveTicketData()):
        with patch.object(
                app.shared_sd,
                'save_ticket_data_as_attachment',
                return_value=None) as mock_save_ticket:
            app.comment()
            assert mock_save_ticket.called is True
            captured = capsys.readouterr()
            assert captured.out == "Comment function called with ticket data\n"


def test_create(capsys):
    """ Test create handling. """
    shared.globals.TICKET_DATA = "ticket data"
    with patch.object(
            app,
            'initialise',
            return_value=MockHandlerWithSaveTicketData()):
        with patch.object(
                app.shared_sd,
                'save_ticket_data_as_attachment',
                return_value=None) as mock_save_ticket:
            app.create()
            assert mock_save_ticket.called is True
            captured = capsys.readouterr()
            assert captured.out == "Create function called with ticket data\n"

class ExceptionMockHandler:
    """ A mock handler class. """
    SAVE_TICKET_DATA = True
    CAPABILITIES = ["TRANSITION", "ASSIGNMENT", "CREATE", "COMMENT"]

    @staticmethod
    def create(ticket_data):
        """ Create handler. """
        raise shared.globals.MalformedIssueError("Fake exception")

    @staticmethod
    def comment(ticket_data):
        """ Comment handler. """
        raise shared.globals.MalformedIssueError("Fake exception")

    @staticmethod
    def transition(status_from, status_to, ticket_data):
        """ Transition handler. """
        raise shared.globals.MalformedIssueError("Fake exception")

    @staticmethod
    def assignment(assignee_from, assignee_to, ticket_data):
        """ Assignment handler. """
        raise shared.globals.MalformedIssueError("Fake exception")

@mock.patch(
    'app.shared_sd.save_ticket_data_as_attachment',
    autospec=True
)
@mock.patch(
    'app.shared_sd.post_comment',
    autospec=True
)
def test_create_exception_handling(mi1, mi2):
    """ Test handling of exceptions in create event. """
    with patch.object(
            app,
            'initialise',
            return_value=ExceptionMockHandler()):
        app.create()
    assert mi1.called is True
    assert mi2.called is True


@mock.patch(
    'app.shared_sd.automation_triggered_comment',
    return_value=False,
    autospec=True
)
@mock.patch(
    'app.shared_sd.save_ticket_data_as_attachment',
    autospec=True
)
@mock.patch(
    'app.shared_sd.post_comment',
    autospec=True
)
def test_comment_exception_handling(mi1, mi2, mi3):
    """ Test handling of exceptions in comment event. """
    with patch.object(
            app,
            'initialise',
            return_value=ExceptionMockHandler()):
        app.comment()
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True

@mock.patch(
    'app.shared_sd.save_ticket_data_as_attachment',
    autospec=True
)
@mock.patch(
    'app.shared_sd.post_comment',
    autospec=True
)
def test_jira_hook_exception_handling(mi1, mi2):
    """ Test handling of exceptions in jira_hook event. """
    with patch.object(
            app,
            'initialise',
            return_value=ExceptionMockHandler()):
        with patch.object(
                app.shared_sd,
                'trigger_is_assignment',
                return_value=(False, None, None)
                ):
            with patch.object(
                    app.shared_sd,
                    'trigger_is_transition',
                    return_value=(True, "status_from", "status_to")
                ):
                app.jira_hook()
    assert mi1.called is True
    assert mi2.called is True
