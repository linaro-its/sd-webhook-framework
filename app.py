#!/usr/bin/python3
#
# This can be used as a template to start developing a webhook service for
# use with Jira Service Desk.
#
# When testing, if not running on the same server as Service Desk, remember
# to use:
#
# flask run --host=0.0.0.0


import os
import sys
import importlib

from flask import Flask, json, request
import sd_webhook_automation.shared_sd as shared_sd


app = Flask(__name__)
ticket_data = None


@app.route('/', methods=['GET'])
def hello_world():
    """A simple test to confirm that the code is running properly."""
    return "Hello, world!"


@app.route('/create', methods=['POST'])
def create():
    handler = initialise()
    if handler is not None and "CREATE" in handler.capabilities:
        if handler.save_ticket_data:
            shared_sd.save_ticket_data_as_attachment(ticket_data)
        handler.create(ticket_data)
    return ""


@app.route('/comment', methods=['POST'])
def comment():
    handler = initialise()
    if handler is not None and "COMMENT" in handler.capabilities:
        if handler.save_ticket_data:
            shared_sd.save_ticket_data_as_attachment(ticket_data)
        handler.comment(ticket_data)
    return ""


@app.route('/jira-hook', methods=['POST'])
def jira_hook():
    handler = initialise()
    if handler is not None:
        # Jira hook can be triggered for any sort of update to a ticket
        # so we need to look at what has changed. In *theory*, it is
        # possible for both assignee and status to change so we need
        # to check and call for both.
        assignee_result, assignee_from, assignee_to = shared_sd.\
            trigger_is_assignment(ticket_data)
        status_result, status_from, status_to = shared_sd.\
            trigger_is_transition(ticket_data)
        if (handler.save_ticket_data and
                (("TRANSITION" in handler.capabilities and status_result) or
                 ("ASSIGNMENT" in handler.capabilities and assignee_result))):
            shared_sd.save_ticket_data_as_attachment(ticket_data)
        if "TRANSITION" in handler.capabilities and status_result:
            handler.transition(status_from, status_to, ticket_data)
        if "ASSIGNMENT" in handler.capabilities and assignee_result:
            handler.assignment(assignee_from, assignee_to, ticket_data)
    return ""


def initialise():
    global ticket_data
    ticket_data = json.loads(request.data)
    shared_sd.initialise(ticket_data)
    # Get the request type for this data
    rt = "rt%s" % shared_sd.ticket_request_type(ticket_data)
    # See if there is a module for this request type. If there is,
    # import it.
    dir_path = os.path.dirname(os.path.abspath(__file__)) + "/rt_handlers"
    if os.path.isdir(dir_path):
        if dir_path not in sys.path:
            sys.path.insert(0, dir_path)
        if os.path.exists("%s/%s.py" % (dir_path, rt)):
            return importlib.import_module(rt)
    return None
