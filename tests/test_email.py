#!/usr/bin/python3
""" Test the shared email library. """

import pytest
import mock
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import EmailMessage
import shared.globals
import shared.email

class BaseMockSMTPSession:
    """ A simple class to mock what SMTP returns. """
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

class MockSMTP1(BaseMockSMTPSession):
    def sendmail(self, from_list, to_list, msg):
        """ A simple function to test what send_email does. """
        _ = self
        assert from_list == "from@mock.mock"
        assert to_list == ["to@mock.mock", "cc@mock.mock"]
        assert msg == 'From: from@mock.mock\nTo: to@mock.mock\nCc: cc@mock.mock\n\n'

class MockSMTP2(BaseMockSMTPSession):
    def sendmail(self, from_list, to_list, msg):
        """ A simple function to test what send_email does. """
        _ = self
        assert from_list == "from@mock.mock"
        assert to_list == ["to@mock.mock", "cc@mock.mock"]
        assert msg == 'Subject: Mock Subject\nFrom: from@mock.mock\nTo: to@mock.mock, cc@mock.mock\nContent-Type: text/plain; charset="utf-8"\nContent-Transfer-Encoding: 7bit\nMIME-Version: 1.0\n\n\n'

class MockSMTP3(BaseMockSMTPSession):
    def sendmail(self, from_list, to_list, msg):
        """ A simple function to test what send_email does. """
        _ = self
        assert from_list == "from@mock.mock"
        assert to_list == ["to@mock.mock"]

class MockBoto3:
    """ Mock boto3 client"""
    @staticmethod
    def send_email(Destination,
                   Message,
                   Source,
                   ConfigurationSetName=None):
        return {
            "MessageId": "something"
        }

def mock_smtp_1(server, port):
    """ Test that send_email is passing the correct values. """
    assert server == "whatever"
    assert port == 25
    return MockSMTP1()

def mock_smtp_2(server, port):
    """ Test that send_email is passing the correct values. """
    assert server == "whatever"
    assert port == 25
    return MockSMTP2()

def mock_smtp_3(server, port):
    """ Test that send_email is passing the correct values. """
    assert server == "whatever"
    assert port == 25
    return MockSMTP3()

@mock.patch(
    'smtplib.SMTP',
    side_effect=mock_smtp_1,
    autospec=True,
)
def test_send_email_1(mi1):
    """ Test send_email when mail mechanism is smtp """
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_ssl": "True",
        "mail_mechanism" : "smtp",
        "mail_user": "mock_user",
        "mail_password": "mock_password"
    }
    
    msg = EmailMessage()
    msg["From"] = "from@mock.mock"
    msg["To"] = "to@mock.mock"
    msg["Cc"] = "cc@mock.mock"
    shared.email.send_email(msg)
    assert mi1.called is True

def test_send_email_2():
    """ Test send_email when config is missing """
    shared.globals.CONFIGURATION = {
    }
    with pytest.raises(shared.email.MissingConfig):
        shared.email.send_email(None)

def test_send_email_3():
    """ Test send_email when mail_mechanism is non smtp"""
    shared.globals.CONFIGURATION = {
        "mail_mechanism" : "ses"
    }
    with pytest.raises(shared.email.InvalidConfig):
        shared.email.send_email(None)

def test_send_email_parts_1():
    "Test when config is missing"
    shared.globals.CONFIGURATION = {}

    with pytest.raises(shared.email.MissingConfig):
        shared.email.send_email_parts(None, None, None, None, None)

@mock.patch(
    'smtplib.SMTP',
    side_effect=mock_smtp_2,
    autospec=True
)
def test_send_email_parts_2(mock_send_email_parts_2):
    """Test when HTML body and Text body are NONE"""
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_ssl": "True",
        "mail_mechanism" : "smtp",
    }
    shared.email.send_email_parts("from@mock.mock", "to@mock.mock, cc@mock.mock", "Mock Subject", None, None)
    assert mock_send_email_parts_2.called is True

@mock.patch(
    'smtplib.SMTP',
    side_effect=mock_smtp_3,
    autospec=True
)
def test_send_email_parts_3(mock_send_email_parts_3):
    "Test when mail mechanism is SMTP"
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_ssl": "True",
        "mail_mechanism" : "smtp",
    }

    text = "This is the plain text body"
    html = "This is the HTML body"
    text_body = MIMEText(text, 'plain')
    html_body = MIMEText(html, 'html')

    shared.email.send_email_parts("from@mock.mock", "to@mock.mock", "Mock Subject", html_body, text_body)
    assert mock_send_email_parts_3.called is True

@mock.patch(
    'smtplib.SMTP',
    side_effect=mock_smtp_3,
    autospec=True
)
def test_send_email_parts_4(mock_send_email_parts_4):
    "Test when mail mechanism is SMTP and text body is None"
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_ssl": "True",
        "mail_mechanism" : "smtp",
    }

    html = "This is the plain text body"
    html_body = MIMEText(html, 'html')

    shared.email.send_email_parts("from@mock.mock", "to@mock.mock", "Mock Subject", html_body, None)
    assert mock_send_email_parts_4.called is True

def test_send_email_parts_5():
    "Test when mail mechanism is neither SMTP nor SES"
    shared.globals.CONFIGURATION = {
        "mail_mechanism" : "something",
    }
    with pytest.raises(shared.email.InvalidConfig):
        shared.email.send_email_parts("from@mock.mock", "to@mock.mock", "Mock Subject", None, None)

@mock.patch(
    'shared.email.boto3.client',
    return_value=MockBoto3,
    autospec=True,
)
def test_send_email_parts_6(mock_send_email_parts_6, capsys):
    "Test when mail mechanism is SES"
    shared.globals.CONFIGURATION = {
        "mail_mechanism" : "ses",
    }
    text = "This is the plain text body"
    html = "This is the HTML body"
    text_body = MIMEText(text, 'plain')
    html_body = MIMEText(html, 'html')

    shared.email.send_email_parts("from@mock.mock", "to@mock.mock", "Mock Subject", html_body, text_body)
    assert mock_send_email_parts_6.called is True
    captured = capsys.readouterr()
    assert captured.out == "Email sent via SES to to@mock.mock; message ID is something\n"

def test_send_email_via_smtp_1():
    """ Test when server is None"""
    shared.globals.CONFIGURATION = {
    }
    with pytest.raises(shared.email.MissingConfig):
        shared.email.send_email_via_smtp(None)

@mock.patch(
    'shared.email.boto3.client',
    return_value=MockBoto3,
    autospec=True,
)
def test_send_email_via_ses_1(mi1, capsys):
    """Test when both ses_config_set and ses_region are specified"""
    shared.globals.CONFIGURATION = {
        "ses_config_set": "something",
        "ses_region": "us-east-1",
    }
    shared.email.send_email_via_ses("from@mock.mock", "to@mock.mock", "Mock Subject", "html_body", "text_body")
    assert mi1.called is True
    captured = capsys.readouterr()
    assert captured.out == "Email sent via SES to to@mock.mock; message ID is something\n"

@mock.patch(
    'shared.email.boto3.client',
    return_value=MockBoto3,
    autospec=True,
)
def test_send_email_via_ses_2(mi1, capsys):
    """Test when ses_config_set is None"""
    shared.globals.CONFIGURATION = {
        "ses_region": "us-east-1",
    }
    shared.email.send_email_via_ses("from@mock.mock", "to@mock.mock", "Mock Subject", "html_body", "text_body")
    assert mi1.called is True
    captured = capsys.readouterr()
    assert captured.out == "Email sent via SES to to@mock.mock; message ID is something\n"
