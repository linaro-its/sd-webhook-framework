#!/usr/bin/python3
""" Test the shared email library. """

import pytest
import mock
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from moto import mock_ses

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
        assert msg == 'Subject: Mock Subject\nFrom: from@mock.mock\nTo: to@mock.mock, cc@mock.mock\n\n'


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

# @mock.patch(
#     'smtplib.SMTP',
#     side_effect=mock_smtp,
#     autospec=True
# )
# def test_send_email(mi1):
#     """ Test send_email """
#     shared.globals.CONFIGURATION = {}
#     with pytest.raises(shared.email.MissingConfig):
#         shared.email.send_email(None)
#     shared.globals.CONFIGURATION = {
#         "mail_host": "whatever",
#         "mail_ssl": "True",
#     }
#     with pytest.raises(shared.email.BadStartTls):
#         shared.email.send_email(None)
#     shared.globals.CONFIGURATION = {
#         "mail_host": "whatever",
#         "mail_user": "mock_user",
#         "mail_password": "mock_password",
#     }
#     msg = EmailMessage()
#     msg["From"] = "from@mock.mock"
#     msg["To"] = "to@mock.mock"
#     msg["Cc"] = "cc@mock.mock"
#     shared.email.send_email(msg)
#     assert mi1.called is True


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
    side_effect=mock_smtp_2,
    autospec=True
)
def test_send_email_parts_3(mock_send_email_parts_3):
    "Test when mail mechanism is SMTP"
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_ssl": "True",
        "mail_mechanism" : "smtp",
    }

    text = "Test subject!\Message body"
    html = """\
    <html>
        <head></head>
        <body>
            <p>Test subject!<br>
            Message body<br>
            </p>
        </body>
    </html>
    """
    text_body = MIMEText(text, 'plain')
    html_body = MIMEText(html, 'html')

    shared.email.send_email_parts("from@mock.mock", "to@mock.mock, cc@mock.mock ", "Mock Subject", html_body, text_body)
    assert mock_send_email_parts_3.called is True


def test_send_email_via_smtp_1():
    """ Test when server is None"""
    shared.globals.CONFIGURATION = {
    }
    with pytest.raises(shared.email.MissingConfig):
        shared.email.send_email_via_smtp(None)


@mock.patch(
    'smtplib.SMTP',
    side_effect=mock_smtp_1,
    autospec=True
)
def test_send_email_via_smtp_2(send_email_via_smtp_2):
    """ Test when user credentials"""
    shared.globals.CONFIGURATION = {
        "mail_host": "whatever",
        "mail_ssl": "True",
        "mail_mechanism" : "smtp",
        "mail_user": "mock_user",
        "mail_password": "mock_password",
    }
    msg = EmailMessage()
    msg["From"] = "from@mock.mock"
    msg["To"] = "to@mock.mock"
    msg["Cc"] = "cc@mock.mock"
    shared.email.send_email_via_smtp(msg)
    assert send_email_via_smtp_2.called is True


# @pytest.fixture(scope='module')
# def aws_credentials():
#     os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
#     os.environ['AWS_SECRET_ACCESS_ID'] = 'testing'
#     os.environ['AWS_SECURITY_TOKEN'] = 'testing'
#     os.environ['AWS_SESSION_TOKEN'] = 'testing'


# @mock_ses
# def test_send_email_via_ses_1(aws_credentials):
#     """ """
#     text = "Test subject!\Message body"
#     html = """\
#     <html>
#         <head></head>
#         <body>
#             <p>Test subject!<br>
#             Message body<br>
#             </p>
#         </body>
#     </html>
#     """
#     text_body = MIMEText(text, 'plain')
#     html_body = MIMEText(html, 'html')

#     shared.email.send_email_via_ses("from@mock.mock", "to@mock.mock", "Mock Subject", html_body, text_body)
