#!/usr/bin/python3
"""
This can be used as a template to start developing a webhook service for
use with Jira Service Desk.

When testing, if not running on the same server as Service Desk, remember
to use:

flask run --host=0.0.0.0
"""

import importlib
import os
import sys
import traceback

import sentry_sdk
from flask import Flask, request
from flask_wtf.csrf import CSRFProtect
from sentry_sdk.integrations.flask import FlaskIntegration

import shared.globals
import shared.sentry_config
import shared.shared_sd as shared_sd

UNEXPECTED = "An unexpected error occurred in the automation:\n%s"

# This must stay before the Flask initialisation.
if shared.sentry_config.SENTRY_DSN is not None:
    sentry_sdk.init(
        dsn=shared.sentry_config.SENTRY_DSN,
        integrations=[FlaskIntegration()],
        release="sd-webhook-framework@1.0.0"
    )


APP = Flask(__name__)
APP.secret_key = os.environ.get("secret_key")
csrf = CSRFProtect(APP)


@APP.route('/', methods=['GET'])
def hello_world():
    """ A simple test to confirm that the code is running properly. """
    return "Hello, world!"


@APP.route('/test-sentry', methods=['GET'])
def test_sentry():
    """ A simple test to provoke reporting back to Sentry. """
    _ = 1/0


@APP.route('/create', methods=['POST'])
def create():
    """ Triggered when a ticket is created. """
    handler = initialise()
    if handler is not None and "CREATE" in handler.CAPABILITIES:
        try:
            print("Calling create handler for %s" % shared.globals.TICKET, file=sys.stderr)
            save_ticket_data(handler)
            handler.create(shared.globals.TICKET_DATA)
        except Exception:  # pylint: disable=broad-except
            shared_sd.post_comment(UNEXPECTED % traceback.format_exc(), False)
    return ""


@APP.route('/comment', methods=['POST'])
def comment():
    """ Triggered when a non-automation comment is added to a ticket. """
    handler = initialise()
    if (handler is not None and
            "COMMENT" in handler.CAPABILITIES and
            not shared_sd.automation_triggered_comment(shared.globals.TICKET_DATA)):
        try:
            print("Calling comment handler for %s" % shared.globals.TICKET, file=sys.stderr)
            save_ticket_data(handler)
            handler.comment(shared.globals.TICKET_DATA)
        except Exception:  # pylint: disable=broad-except
            shared_sd.post_comment(UNEXPECTED % traceback.format_exc(), False)
    return ""


@APP.route('/org-change', methods=['POST'])
def org_change():
    """ Triggered when the organizations change for a ticket. """
    handler = initialise()
    if handler is not None and "ORGCHANGE" in handler.CAPABILITIES:
        try:
            print("Calling org change handler for %s" % shared.globals.TICKET, file=sys.stderr)
            save_ticket_data(handler)
            handler.org_change(shared.globals.TICKET_DATA)
        except Exception:  # pylint: disable=broad-except
            shared_sd.post_comment(UNEXPECTED % traceback.format_exc(), False)
    return ""


@APP.route('/jira-hook', methods=['POST'])
@csrf.exempt
def jira_hook():
    """ Triggered when Jira itself (not Service Desk) fires a webhook event. """
    handler = initialise()
    if handler is not None:
        # Jira hook can be triggered for any sort of update to a ticket
        # so we need to look at what has changed. In *theory*, it is
        # possible for both assignee and status to change so we need
        # to check and call for both.
        assignee_result, assignee_from, assignee_to = shared_sd.\
            trigger_is_assignment(shared.globals.TICKET_DATA)
        status_result, status_from, status_to = shared_sd.\
            trigger_is_transition(shared.globals.TICKET_DATA)
        try:
            if (("TRANSITION" in handler.CAPABILITIES and status_result) or
                    ("ASSIGNMENT" in handler.CAPABILITIES and assignee_result)):
                save_ticket_data(handler)
            if "TRANSITION" in handler.CAPABILITIES and status_result:
                print("Calling transition handler for %s" % shared.globals.TICKET, file=sys.stderr)
                handler.transition(status_from, status_to, shared.globals.TICKET_DATA)
            if "ASSIGNMENT" in handler.CAPABILITIES and assignee_result:
                print("Calling assignment handler for %s" % shared.globals.TICKET, file=sys.stderr)
                handler.assignment(assignee_from, assignee_to, shared.globals.TICKET_DATA)
        except Exception:  # pylint: disable=broad-except
            shared_sd.post_comment(UNEXPECTED % traceback.format_exc(), False)
    return ""


def save_ticket_data(handler):
    """ Save the ticket data to the ticket. """
    save_data = False
    try:
        save_data = handler.SAVE_TICKET_DATA
    except Exception:  # pylint: disable=broad-except
        pass

    if save_data:
        shared_sd.save_ticket_data_as_attachment(shared.globals.TICKET_DATA)


def handler_filename(dir_path, reqtype):
    """ Determine the handler filename for this request type. """
    if reqtype is not None:
        #
        # Is there a handler in the configuration for this request type?
        if ("handlers" in shared.globals.CONFIGURATION and
                reqtype in shared.globals.CONFIGURATION["handlers"]):
            return shared.globals.CONFIGURATION["handlers"][reqtype]
        #
        # Is there a file with the right format name?
        filename = "rt%s" % reqtype
        if os.path.exists("%s/%s.py" % (dir_path, filename)):
            return filename
    #
    # Is there a wildcard?
    if ("handlers" in shared.globals.CONFIGURATION and
            "*" in shared.globals.CONFIGURATION["handlers"]):
        return shared.globals.CONFIGURATION["handlers"]["*"]
    #
    # Nothing doing.
    return None


def initialise_handler():
    """ Load the Python code handling this request type if possible. """
    #
    # Check that the handler directory exists.
    dir_path = os.path.dirname(os.path.abspath(__file__)) + "/rt_handlers"
    if not os.path.isdir(dir_path):
        print("ERROR! Missing rt_handlers directory", file=sys.stderr)
        return None
    #
    # Work out what the request type number is.
    try:
        reqtype = shared_sd.ticket_request_type(shared.globals.TICKET_DATA)
    except shared_sd.CustomFieldLookupFailure as caught_error:
        shared_sd.post_comment(
            "%s. Please check the configuration and logs." % str(caught_error),
            False
        )
        return None
    #
    # Work out which handler to use, if there is one.
    filename = handler_filename(dir_path, reqtype)
    if filename is not None:
        if dir_path not in sys.path:
            sys.path.insert(0, dir_path)
        if os.path.exists("%s/%s.py" % (dir_path, filename)):
            return import_handler(dir_path, filename)
        print(
            "ERROR! Cannot find '%s/%s.py'" % (dir_path, filename),
            file=sys.stderr)
        return None

    print(
        "Called to handle %s but no handler found." % reqtype,
        file=sys.stderr)
    return None


def import_handler(dir_path, filename):
    """ Load the desired handler. """
    print("Loading '%s/%s.py' as handler for %s" % (dir_path, filename, shared.globals.TICKET),
          file=sys.stderr)
    handler = importlib.import_module(filename)
    # Make sure that the handler has a CAPABILITIES block
    try:
        _ = handler.CAPABILITIES
    except Exception:  # pylint: disable=broad-except
        print(
            "Handler is missing CAPABILITIES definition",
            file=sys.stderr)
        handler = None
    return handler


def initialise():
    """ Initialise code and variables for this event. """
    try:
        shared.globals.initialise_config()
        shared.globals.initialise_ticket_data(request.json)
        shared.globals.initialise_sd_auth()
        shared.globals.initialise_shared_sd()
    except Exception as exc:  # pylint: disable=broad-except
        print(exc)
        return None
    return initialise_handler()
