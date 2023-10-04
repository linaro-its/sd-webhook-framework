#!/usr/bin/python3
"""
This can be used as a template to start developing a webhook service for
use with Jira Service Desk.

When testing, if not running on the same server as Service Desk, remember
to use:

flask run --host=0.0.0.0

Note that the CSRF protection is not supported or used because there isn't
a mechanism available to get Jira/Service Desk to generate the necessary
headers.
"""

import importlib
import os
import sys
import traceback

import sentry_sdk
from flask import Flask, request
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
    handler = initialise(False)
    if handler is None:
        print("/create: no handler")
    else:
        print("/create: %s" % handler.CAPABILITIES)
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
    handler = initialise(True)
    if handler is None:
        print("/comment: no handler")
    else:
        print("/comment: %s" % handler.CAPABILITIES)
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
    handler = initialise(False)
    if handler is None:
        print("/org-change: no handler")
    else:
        print("/org-change: %s" % handler.CAPABILITIES)
    if handler is not None and "ORGCHANGE" in handler.CAPABILITIES:
        try:
            print("Calling org change handler for %s" % shared.globals.TICKET, file=sys.stderr)
            save_ticket_data(handler)
            handler.org_change(shared.globals.TICKET_DATA)
        except Exception:  # pylint: disable=broad-except
            shared_sd.post_comment(UNEXPECTED % traceback.format_exc(), False)
    return ""


@APP.route('/transition', methods=['POST'])
def ticket_transition():
    """ Triggered by SD Automation on transition. """
    handler = initialise(False)
    if handler is None:
        print("/transition: no handler")
    else:
        print("/transition: %s" % handler.CAPABILITIES)
    if handler is not None and "TRANSITION" in handler.CAPABILITIES:
        try:
            print("Calling transition handler for %s" % shared.globals.TICKET, file=sys.stderr)
            save_ticket_data(handler)
            new_status = shared.globals.TICKET_DATA["fields"]["status"]["name"]
            handler.transition(new_status, shared.globals.TICKET_DATA)
        except Exception:  # pylint: disable=broad-except
            shared_sd.post_comment(UNEXPECTED % traceback.format_exc(), False)
    return ""


@APP.route('/jira-hook', methods=['POST'])
def jira_hook():
    """ Triggered when Jira itself (not Service Desk) fires a webhook event. """
    handler = initialise(False)
    if handler is None:
        print("/jira-hook: no handler")
    else:
        print("/jira-hook: %s" % handler.CAPABILITIES)
    if handler is not None:
        # Jira hook can be triggered for any sort of update to a ticket
        # so we need to look at what has changed. In *theory*, it is
        # possible for both assignee and status to change so we need
        # to check and call for both.
        #
        # Note that we pass request.json and not TICKET_DATA because the
        # latter is literally just the ticket data but trigger_is_X needs
        # the original body in order to decide what triggered the webhook.
        assignee_result, assignee_to = shared_sd.\
            trigger_is_assignment(request.json)
        status_result, status_to = shared_sd.\
            trigger_is_transition(request.json)
        try:
            if got_handled_jira_event(handler.CAPABILITIES, status_result, assignee_result):
                save_ticket_data(handler)
            if is_transition(handler.CAPABILITIES, status_result):
                print("Calling transition handler for %s" % shared.globals.TICKET, file=sys.stderr)
                handler.transition(status_to, shared.globals.TICKET_DATA)
            if is_assignment(handler.CAPABILITIES, assignee_result):
                print("Calling assignment handler for %s" % shared.globals.TICKET, file=sys.stderr)
                handler.assignment(assignee_to, shared.globals.TICKET_DATA)
            if is_generic_jira(handler.CAPABILITIES, status_result, assignee_result):
                print("Calling Jira hook handler for %s" % shared.globals.TICKET, file=sys.stderr)
                # A generic handler might need to know what has changed so extract the change log
                # if there is one.
                changelog = request.json["changelog"] if "changelog" in request.json else None
                handler.jira_hook(shared.globals.TICKET_DATA, changelog)
        except Exception:  # pylint: disable=broad-except
            shared_sd.post_comment(UNEXPECTED % traceback.format_exc(), False)
    return ""


def got_handled_jira_event(capabilities, status_result, assignee_result):
    """ Central checker for Jira webhook handling """
    return is_transition(capabilities, status_result) or \
        is_assignment(capabilities, assignee_result) or \
            is_generic_jira(capabilities, status_result, assignee_result)


def is_transition(capabilities, status_result):
    """ Check that we're handling a transition """
    return "TRANSITION" in capabilities and status_result


def is_assignment(capabilities, assignee_result):
    """ Check that we're handling an assignment """
    return "ASSIGNMENT" in capabilities and assignee_result


def is_generic_jira(capabilities, status_result, assignee_result):
    """ Check that we're handling a generic Jira trigger """
    return "JIRAHOOK" in capabilities and not status_result and not assignee_result


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
            f"{str(caught_error)}. Please check the configuration and logs.",
            False
        )
        return None
    if reqtype is None:
        print("Unable to determine request type")
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


def initialise(action_is_comment: bool):
    """ Initialise code and variables for this event. """
    try:
        shared.globals.initialise_config()
        shared.globals.initialise_ticket_data(request.json)
        shared.globals.initialise_sd_auth()
        shared.globals.initialise_shared_sd()
        if shared.globals.REPORTER is None:
            # Need to ensure that we don't react to ourselves posting the comment below.
            if action_is_comment:
                latest_comment = shared_sd.get_latest_comment()
                if shared_sd.user_is_bot(latest_comment["author"]):
                    print("Anonymously submitted ticket but ignoring automation-posted comment")
                    return None
            print("Anonymously submitted ticket - aborting")
            shared_sd.post_comment(
                "It is not possible to action this request. It has been submitted anonymously. "
                "Please sign in to Service Desk and try again.",
                True
            )
            shared_sd.resolve_ticket("Declined")
            return None
    except Exception as exc:  # pylint: disable=broad-except
        print(exc)
        return None
    return initialise_handler()
