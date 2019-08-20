#!/usr/bin/python3
""" Test framework for the sample request type handler. """

import rt_handlers.rt206 as rt206


def test_create(capsys):
    """ Test the create function. """
    rt206.create(None)
    captured = capsys.readouterr()
    assert captured.out == "Create function has been called\n"


def test_comment(capsys):
    """ Test the comment function. """
    rt206.comment(None)
    captured = capsys.readouterr()
    assert captured.out == "Comment function has been called\n"


def test_transition(capsys):
    """ Test the transition function. """
    rt206.transition("status_from", "status_to", None)
    captured = capsys.readouterr()
    assert captured.out == "Transition from status_from to status_to\n"


def test_assignment(capsys):
    """ Test the assignment function. """
    rt206.assignment("assign_from", "assign_to", None)
    captured = capsys.readouterr()
    assert captured.out == "Assigned from assign_from to assign_to\n"
