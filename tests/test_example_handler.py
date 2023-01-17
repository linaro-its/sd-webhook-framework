#!/usr/bin/python3
""" Test framework for the sample request type handler. """

import rt_handlers.rt_example_handler as handler


def test_create(capsys):
    """ Test the create function. """
    handler.create(None)
    captured = capsys.readouterr()
    assert captured.out == "Create function has been called\n"


def test_comment(capsys):
    """ Test the comment function. """
    handler.comment(None)
    captured = capsys.readouterr()
    assert captured.out == "Comment function has been called\n"


def test_transition(capsys):
    """ Test the transition function. """
    handler.transition("status_to", None)
    captured = capsys.readouterr()
    assert captured.out == "Transition to status_to\n"


def test_assignment(capsys):
    """ Test the assignment function. """
    handler.assignment("assignee_to", None)
    captured = capsys.readouterr()
    assert captured.out == "Assigned to assignee_to\n"


def test_org_change(capsys):
    """ Test Org change function. """
    handler.org_change(None)
    captured = capsys.readouterr()
    assert captured.out == "Org change function has been called\n"


def test_jira_hook(capsys):
    """ Test jira hook function. """
    handler.jira_hook(None)
    captured = capsys.readouterr()
    assert captured.out == "Jira hook function has been called\n"