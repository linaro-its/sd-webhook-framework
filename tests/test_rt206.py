#!/usr/bin/python3

import os
import sys

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))) + "/rt_handlers")
import rt206  # noqa


def test_create(capsys):
    rt206.create(None)
    captured = capsys.readouterr()
    assert captured.out == "Create function has been called\n"


def test_comment(capsys):
    rt206.comment(None)
    captured = capsys.readouterr()
    assert captured.out == "Comment function has been called\n"


def test_transition(capsys):
    rt206.transition("status_from", "status_to", None)
    captured = capsys.readouterr()
    assert captured.out == "Transition from status_from to status_to\n"


def test_assignment(capsys):
    rt206.assignment("assign_from", "assign_to", None)
    captured = capsys.readouterr()
    assert captured.out == "Assigned from assign_from to assign_to\n"
