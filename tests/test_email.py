#!/usr/bin/python3
""" Test the shared email library. """

import pytest
import mock

from email.message import EmailMessage
import shared.globals
import shared.email

class MockSession:
    """ A simple class to mock what SMTP returns. """
    def sendmail(self, from_list, to_list, msg):
        """ A simple function to test what send_email does. """
        _ = self
        assert from_list == "from@mock.mock"
        assert to_list == ["to@mock.mock", "cc@mock.mock"]
        assert msg == 'From: from@mock.mock\nTo: to@mock.mock\nCc: cc@mock.mock\n\n'

    def starttls(self, context):
        """
        Mock the starttls function.

        We'll always return a value to indicate that we've failed.
        That then tests *that* code. We then finish the testing by
        not enabling TLS.
        """
        _ = self
        _ = context
        return [404]

    def login(self, user, password):
        """ Mock the login function. """
        _ = self
        assert user == "mock_user"
        assert password == "mock_password"

    def quit(self):
        """ Mock the quit function. """
        _ = self


def mock_smtp(server, port):
    """ Test that send_email is passing the correct values. """
    assert server == "whatever"
    assert port == 25
    return MockSession()

@mock.patch(
    'smtplib.SMTP',
    side_effect=mock_smtp,
    autospec=True
)
def test_send_email(mi1):
    """ Test send_email """
    shared.globals.CONFIGURATION = {}
    with pytest.raises(shared.email.MissingConfig):
        shared.email.send_email(None)
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_ssl": "True"
    }
    with pytest.raises(shared.email.BadStartTls):
        shared.email.send_email(None)
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_user": "mock_user",
        "mail_password": "mock_password"
    }
    msg = EmailMessage()
    msg["From"] = "from@mock.mock"
    msg["To"] = "to@mock.mock"
    msg["Cc"] = "cc@mock.mock"
    shared.email.send_email(msg)
    assert mi1.called is True
