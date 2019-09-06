""" Provides a central function to send email. """

import smtplib
import ssl
import shared.globals

class SharedEmailError(Exception):
    """ Base exception class for the library. """

class MissingConfig(SharedEmailError):
    """ Critical configuration missing. """

class BadStartTls(SharedEmailError):
    """ starttls failed """


def send_email(msg):
    """ Send the email message. """
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
        # only TLSv1 or higher
        context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        if session.starttls(context=context)[0] != 220:
            raise BadStartTls()
    if user is not None:
        session.login(user, password)
    recipients = [msg['To']]
    if msg['Cc'] is not None:
        recipients = recipients + msg['Cc'].split(",")
    session.sendmail(
        msg["From"],
        recipients,
        msg.as_string())
    session.quit()
