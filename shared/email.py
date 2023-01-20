""" Provides a central function to send email. """

import smtplib
import ssl
from email.message import EmailMessage

import boto3

import shared.globals


class SharedEmailError(Exception):
    """ Base exception class for the library. """

class MissingConfig(SharedEmailError):
    """ Critical configuration missing. """

class BadStartTls(SharedEmailError):
    """ starttls failed """

class InvalidConfig(SharedEmailError):
    """ Configuration is invalid for operation. """

def send_email_parts(sender, recipient, subject, html_body, text_body):
    """ Send the email message in parts. """
    protocol = shared.globals.config("mail_mechanism")
    if protocol is None:
        raise MissingConfig("mail_mechanism has not been defined")
    if html_body is None and text_body is None:
        text_body = "" # Make sure we have *something* to send
    if protocol == "smtp":
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        if text_body is None:
            msg.set_content(html_body, subtype="html")
        else:
            msg.set_content(text_body)
            if html_body is not None:
                msg.add_alternative(html_body, subtype="html")
        send_email_via_smtp(msg)
    elif protocol == "ses":
        send_email_via_ses(sender, recipient, subject, html_body, text_body)
    else:
        raise InvalidConfig("mail_mechanism must be smtp or ses")

def send_email(msg):
    """ Send the email message. """
    protocol = shared.globals.config("mail_mechanism")
    if protocol is None:
        raise MissingConfig("mail_mechanism has not been defined")
    if protocol != "smtp":
        raise InvalidConfig("%s cannot be used with a prepared message body" % protocol)
    send_email_via_smtp(msg)

def send_email_via_smtp(msg):
    """ Send the email via SMTP. """
    # Start by retrieving the configuration.
    server = shared.globals.config("mail_host")
    if server is None:
        raise MissingConfig("No mail_host defined")
    port = shared.globals.config("mail_port")
    if port is None:
        port = 25
    user, password = shared.globals.get_email_credentials()
    ssl_required = shared.globals.config("mail_ssl")
    #
    session = smtplib.SMTP(server, port=port)
    if ssl_required:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # starttls now raises an exception itself if the
        # response code is not 220
        session.starttls(context=context)
    if user is not None:
        session.login(user, password)
    recipients = [x.strip() for x in msg['To'].split(',')]
    if msg['Cc'] is not None:
        recipients = recipients + [x.strip() for x in msg['Cc'].split(',')]
    session.sendmail(
        msg["From"],
        recipients,
        msg.as_string())
    session.quit()

def send_email_via_ses(sender, recipient, subject, html_body, text_body):
    """ Sent the message via AWS SES. """
    configuration_set = shared.globals.config("ses_config_set")
    aws_region = shared.globals.config("ses_region")
    char_set = "UTF-8"
    client = boto3.client('ses', region_name=aws_region)
    message = {
        "Body": {},
        "Subject": {
            "Charset": char_set,
            "Data": subject
        }
    }
    if html_body is not None:
        message["Body"]["Html"] = {
            "Charset": char_set,
            "Data": html_body
        }
    if text_body is not None:
        message["Body"]["Text"] = {
            "Charset": char_set,
            "Data": text_body
        }
    if configuration_set is None:
        response = client.send_email(
            Destination={
                "ToAddresses": [recipient]
            },
            Message=message,
            Source=sender
        )
    else:
        response = client.send_email(
            Destination={
                "ToAddresses": [recipient]
            },
            Message=message,
            Source=sender,
            ConfigurationSetName=configuration_set
        )
    print("Email sent via SES to %s; message ID is %s" % (recipient, response["MessageId"]))