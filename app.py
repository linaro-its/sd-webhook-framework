#!/usr/bin/python3
"""
This can be used as a template to start developing a webhook service for
use with Jira Service Desk.

When testing, if not running on the same server as Service Desk, remember
to use:

flask run --host=0.0.0.0
"""

import os
import sys
import importlib

from flask import Flask, json, request
import shared.shared_sd as shared_sd


APP = Flask(__name__)
TICKET_DATA = None


@APP.route('/', methods=['GET'])
def hello_world():
    """ A simple test to confirm that the code is running properly. """
    return "Hello, world!"


@APP.route('/create', methods=['POST'])
def create():
    """ Triggered when a ticket is created. """
    handler = initialise()
    if handler is not None and "CREATE" in handler.CAPABILITIES:
        if handler.SAVE_TICKET_DATA:
            shared_sd.save_ticket_data_as_attachment(TICKET_DATA)
        handler.create(TICKET_DATA)
    return ""


@APP.route('/comment', methods=['POST'])
def comment():
    """ Triggered when a comment is added to a ticket. """
    handler = initialise()
    if handler is not None and "COMMENT" in handler.CAPABILITIES:
        if handler.SAVE_TICKET_DATA:
            shared_sd.save_ticket_data_as_attachment(TICKET_DATA)
        handler.comment(TICKET_DATA)
    return ""


@APP.route('/jira-hook', methods=['POST'])
def jira_hook():
    """ Triggered when Jira itself (not Service Desk) fires a webhook event. """
    handler = initialise()
    if handler is not None:
        # Jira hook can be triggered for any sort of update to a ticket
        # so we need to look at what has changed. In *theory*, it is
        # possible for both assignee and status to change so we need
        # to check and call for both.
        assignee_result, assignee_from, assignee_to = shared_sd.\
            trigger_is_assignment(TICKET_DATA)
        status_result, status_from, status_to = shared_sd.\
            trigger_is_transition(TICKET_DATA)
        if (handler.SAVE_TICKET_DATA and
                (("TRANSITION" in handler.CAPABILITIES and status_result) or
                 ("ASSIGNMENT" in handler.CAPABILITIES and assignee_result))):
            shared_sd.save_ticket_data_as_attachment(TICKET_DATA)
        if "TRANSITION" in handler.CAPABILITIES and status_result:
            handler.transition(status_from, status_to, TICKET_DATA)
        if "ASSIGNMENT" in handler.CAPABILITIES and assignee_result:
            handler.assignment(assignee_from, assignee_to, TICKET_DATA)
    return ""


def initialise():
    """ Initialise code and variables for this event. """
    global TICKET_DATA  # pylint: disable=global-statement
    TICKET_DATA = json.loads(request.data)
    shared_sd.initialise(TICKET_DATA)
    # Get the request type for this data
    reqtype = "rt%s" % shared_sd.ticket_request_type(TICKET_DATA)
    # See if there is a module for this request type. If there is,
    # import it.
    dir_path = os.path.dirname(os.path.abspath(__file__)) + "/rt_handlers"
    if os.path.isdir(dir_path):
        if dir_path not in sys.path:
            sys.path.insert(0, dir_path)
        if os.path.exists("%s/%s.py" % (dir_path, reqtype)):
            return importlib.import_module(reqtype)
    return None
