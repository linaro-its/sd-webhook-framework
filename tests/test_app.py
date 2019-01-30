#!/usr/bin/python3

import os
import sys

import mock
from unittest.mock import patch

# Tell Python where to find the webhook automation code.
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
import app  # noqa


def test_hello_world():
    foo = app.hello_world()
    assert foo == "Hello, world!"


@mock.patch(
    'app.json.loads',
    return_value={},
    autospec=True
)
@mock.patch(
    'app.shared_sd.initialise',
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="206",
    autospec=True
)
def test_initialise(mock_rt, mock_init, mock_jloads):
    # The app code includes a variable called app, so reference that
    # as flask_app to make the code clearer.
    flask_app = app.app
    with flask_app.test_request_context('/'):
        test_result = app.initialise()
        assert mock_rt.called is True
        assert mock_init.called is True
        assert mock_jloads.called is True
        assert test_result is not None


@mock.patch(
    'app.json.loads',
    return_value={},
    autospec=True
)
@mock.patch(
    'app.shared_sd.initialise',
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="-1",
    autospec=True
)
def test_initialise_missing_handler(mock_rt, mock_init, mock_jloads):
    # The app code includes a variable called app, so reference that
    # as flask_app to make the code clearer.
    flask_app = app.app
    with flask_app.test_request_context('/'):
        test_result = app.initialise()
        assert mock_rt.called is True
        assert mock_init.called is True
        assert mock_jloads.called is True
        assert test_result is None


@mock.patch(
    'app.json.loads',
    return_value={},
    autospec=True
)
@mock.patch(
    'app.shared_sd.initialise',
    autospec=True
)
@mock.patch(
    'app.shared_sd.ticket_request_type',
    return_value="-1",
    autospec=True
)
def test_initialise_missing_path(mock_rt, mock_init, mock_jloads):
    # The app code includes a variable called app, so reference that
    # as flask_app to make the code clearer.
    flask_app = app.app
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
        assert mock_init.called is True
        assert mock_jloads.called is True
        assert test_result is None


# Need to have some mock handlers for testing the rest of the app code.
# For the purposes of mocking, ticket_data for create and comment will
# be strings.
class mock_handler_with_save_ticket_data:
    save_ticket_data = True

    capabilities = ["TRANSITION", "ASSIGNMENT", "CREATE", "COMMENT"]

    def create(self, ticket_data):
        print("Create function called with %s" % ticket_data)

    def comment(self, ticket_data):
        print("Comment function called with %s" % ticket_data)

    def transition(self, status_from, status_to, ticket_data):
        print("Transition from %s to %s" % (status_from, status_to))

    def assignment(self, assignee_from, assignee_to, ticket_data):
        print("Assigned from %s to %s" % (assignee_from, assignee_to))


class mock_handler_without_save_ticket_data:
    save_ticket_data = False

    capabilities = ["TRANSITION", "ASSIGNMENT", "CREATE", "COMMENT"]

    def create(self, ticket_data):
        print("Create function called with %s" % ticket_data)

    def comment(self, ticket_data):
        print("Comment function called with %s" % ticket_data)

    def transition(self, status_from, status_to, ticket_data):
        print("Transition from %s to %s" % (status_from, status_to))

    def assignment(self, assignee_from, assignee_to, ticket_data):
        print("Assigned from %s to %s" % (assignee_from, assignee_to))


def test_jira_hook_assignment(capsys):
    # We use patch.object here instead of @mock.patch because it is very
    # tricky to use features (capsys) in conjunction with mock params.
    with patch.object(
            app,
            'initialise',
            return_value=mock_handler_with_save_ticket_data()):
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
    with patch.object(
            app,
            'initialise',
            return_value=mock_handler_without_save_ticket_data()):
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
    app.ticket_data = "ticket data"
    with patch.object(
            app,
            'initialise',
            return_value=mock_handler_with_save_ticket_data()):
        with patch.object(
                app.shared_sd,
                'save_ticket_data_as_attachment',
                return_value=None) as mock_save_ticket:
            app.comment()
            assert mock_save_ticket.called is True
            captured = capsys.readouterr()
            assert captured.out == "Comment function called with ticket data\n"


def test_create(capsys):
    app.ticket_data = "ticket data"
    with patch.object(
            app,
            'initialise',
            return_value=mock_handler_with_save_ticket_data()):
        with patch.object(
                app.shared_sd,
                'save_ticket_data_as_attachment',
                return_value=None) as mock_save_ticket:
            app.create()
            assert mock_save_ticket.called is True
            captured = capsys.readouterr()
            assert captured.out == "Create function called with ticket data\n"
