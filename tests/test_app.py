#!/usr/bin/python3
""" Test the app code. """

import os
import sys
from unittest.mock import patch
import mock

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
    'app.os.path.exists',
    return_value=False,
    autospec=True
)
def test_handler_filename(mi1):
    """ Test handler_filename. """
    shared.globals.CONFIGURATION = {
        "handlers": {
            "mockreqtype": "mockhandler.py",
            "*": "mockfallback.py"
        }
    }
    assert app.handler_filename(None, "mockreqtype") == "mockhandler.py"
    assert app.handler_filename(None, "mockreqtype2") == "mockfallback.py"
    shared.globals.CONFIGURATION = {}
    assert app.handler_filename(None, "mockreqtype") is None
    assert mi1.called is True


@mock.patch(
    'app.os.path.exists',
    return_value=True,
    autospec=True
)
def test_handler_filename2(mi1):
    """ Test handler_filename. """
    shared.globals.CONFIGURATION = {}
    assert app.handler_filename(None, "42") == "rt42"
    assert mi1.called is True


@mock.patch(
    'app.os.path.isdir',
    return_value=False,
    autospec=True
)
def test_initialise_handler(mi1):
    """ Test initialise_handler. """
    # If the directory doesn't exist, we get None back.
    assert app.initialise_handler() is None
    assert mi1.called is True


@mock.patch(
    'app.os.path.isdir',
    return_value=True,
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="_example_handler",
    autospec=True
)
def test_initialise_handler2(mi1, mi2):
    """ Test initialise_handler. """
    # Note that the repo only ships with an example handler ...
    shared.globals.CONFIGURATION = {}
    test_result = app.initialise_handler()
    assert test_result is not None
    assert mi1.called is True
    assert mi2.called is True


@mock.patch(
    'app.os.path.isdir',
    return_value=True,
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="_example_handler",
    autospec=True
)
@mock.patch(
    'app.handler_filename',
    return_value="py_example_handler",
    autospec=True
)
@mock.patch(
    'app.os.path.exists',
    return_value=False,
    autospec=True
)
def test_initialise_handler3(mi1, mi2, mi3, mi4):
    """ Test initialise_handler. """
    shared.globals.CONFIGURATION = {}
    test_result = app.initialise_handler()
    assert test_result is None
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert mi4.called is True


@mock.patch(
    'app.shared_sd.post_comment',
    autospec=True
)
def test_initialise_handler_bad_config(mi1):
    """ Test initialise_handler. """
    shared.globals.CONFIGURATION = {
        "cf_cachefile": "non_existent_file",
        "cf_use_server_api": False,
        "cf_use_cloud_api": False
    }
    shared.globals.TICKET_DATA = {}
    test_result = app.initialise_handler()
    assert test_result is None
    assert mi1.called is True


@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value=None,
    autospec=True
)
def test_initialise_handler_missing_handler(mi1):
    """ Test initialise_handler. """
    test_result = app.initialise_handler()
    assert test_result is None
    assert mi1.called is True


@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="-1",
    autospec=True
)
def test_initialise_missing_path(mi1):
    """ Test the code that adds the path to the handlers. """
    # Build the path to rt_handlers. Note that we need to go two levels
    # up ...
    dir_path = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )) + "/rt_handlers"
    # pytest will have loaded at least one RT test, causing that path
    # to be added to sys.path, so we have to remove it to ensure full
    # coverage of app.initialise.
    if dir_path in sys.path:
        sys.path.remove(dir_path)
    test_result = app.initialise_handler()
    assert mi1.called is True
    assert test_result is None


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
    'app.initialise_handler',
    return_value="mock_handler",
    autospec=True
)
def test_intialise(mi1, mi2, mi3, mi4, mi5):
    """ Test initialise. """
    # The app code includes a variable called APP, so reference that
    # as flask_app to make the code clearer.
    flask_app = app.APP
    # We don't care what data we set up in the context because we're just
    # checking that app.initialise calls all the right mocks and returns
    # the right values. The actual functions that app.initialise calls
    # are tested elsewhere.
    with flask_app.test_request_context('/', method="POST", json={'name': 'test'}):
        test_result = app.initialise()
    assert test_result == "mock_handler"
    assert mi1.called is True
    assert mi2.called is True
    assert mi3.called is True
    assert mi4.called is True
    assert mi5.called is True


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
    def assignment(assignee_to, ticket_data):
        """ Assignment handler. """
        _ = ticket_data
        print("Assigned to %s" % assignee_to)


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
    def transition(status_to, ticket_data):
        """ Transition handler. """
        _ = ticket_data
        print("Transition to %s" % (status_to))

    @staticmethod
    def assignment(assignee_to, ticket_data):
        """ Assignment handler. """
        _ = ticket_data
        print("Assigned to %s" % assignee_to)


def test_jira_hook_assignment(capsys):
    """ Test jira_hook assignment handling. """
    # We use patch.object here instead of @mock.patch because it is very
    # tricky to use features (capsys) in conjunction with mock params.
    mock_request = mock.MagicMock()
    mock_request.json = {}
    with patch.object(
            app,
            'initialise',
            return_value=MockHandlerWithSaveTicketData()):
        with mock.patch('app.request', mock_request):
            with patch.object(
                    app.shared_sd,
                    'trigger_is_assignment',
                    return_value=(True, "assignee_to")
                    ):
                with patch.object(
                        app.shared_sd,
                        'trigger_is_transition',
                        return_value=(False, None)
                    ):
                    with patch.object(
                            app.shared_sd,
                            'save_ticket_data_as_attachment',
                            return_value=None) as mock_save_ticket:
                        app.jira_hook()
                        assert mock_save_ticket.called is True
                        captured = capsys.readouterr()
                        assert captured.out == (
                            "/jira-hook: ['TRANSITION', 'ASSIGNMENT', 'CREATE', 'COMMENT']\n"
                            "Assigned to assignee_to\n")


def test_jira_hook_transition(capsys):
    """ Test jira_hook transition handling. """
    mock_request = mock.MagicMock()
    mock_request.json = {}
    with patch.object(
            app,
            'initialise',
            return_value=MockHandlerWithoutSaveTicketData()):
        with mock.patch('app.request', mock_request):
            with patch.object(
                    app.shared_sd,
                    'trigger_is_assignment',
                    return_value=(False, None)
                    ):
                with patch.object(
                        app.shared_sd,
                        'trigger_is_transition',
                        return_value=(True, "status_to")
                    ):
                    with patch.object(
                            app.shared_sd,
                            'save_ticket_data_as_attachment',
                            return_value=None) as mock_save_ticket:
                        app.jira_hook()
                        assert mock_save_ticket.called is False
                        captured = capsys.readouterr()
                        assert captured.out == (
                            "/jira-hook: ['TRANSITION', 'ASSIGNMENT', 'CREATE', 'COMMENT']\n"
                            "Transition to status_to\n")


def test_comment(capsys):
    """ Test comment handling. """
    shared.globals.TICKET_DATA = {
        "fields" : "ticket data"
    }
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
            assert captured.out == (
                "/comment: ['TRANSITION', 'ASSIGNMENT', 'CREATE', 'COMMENT']\n"
                "Comment function called with {'fields': 'ticket data'}\n"
            )


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
            assert captured.out == (
                "/create: ['TRANSITION', 'ASSIGNMENT', 'CREATE', 'COMMENT']\n"
                "Create function called with ticket data\n"
            )


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
    mock_request = mock.MagicMock()
    mock_request.json = {}
    with patch.object(
            app,
            'initialise',
            return_value=ExceptionMockHandler()):
        with mock.patch('app.request', mock_request):
            with patch.object(
                    app.shared_sd,
                    'trigger_is_assignment',
                    return_value=(False, None)
                    ):
                with patch.object(
                        app.shared_sd,
                        'trigger_is_transition',
                        return_value=(True, None)
                    ):
                    app.jira_hook()
    assert mi1.called is True
    assert mi2.called is True
