""" Handler for RT273: Developer Cloud Registration. """

# The fields in the form used by the automation are as follows:
RT273_IP_ADDRESSES = 11603
RT273_PROJECT_TYPE = 12319
RT273_FIRST_NAME = 12320
RT273_FAMILY_NAME = 12321
RT273_SPECIAL_REQUEST = 12324


# Define what this handler can handle :)
# Using strings avoids the need to access defines elsewhere.
CAPABILITIES = [
    "TRANSITION", "COMMENT"
]


SAVE_TICKET_DATA = True

def comment(ticket_data):
    """ Comment handler. """
    _ = ticket_data
    print("Comment function has been called")


def create_ldap_account(ticket_data):
    """ Create a LDAP account based off the ticket data. """
    # Start by retrieving and cleaning up the data from the ticket.
    email_address = ticket_data[
        "issue"]["fields"]["reporter"]["emailAddress"]


def send_welcome_email(ticket_data):
    """ Send a welcome email to the ticket requester. """
    return


def create_openstack_ticket(ticket_data):
    """ Create a ticket for a new OpenStack project. """
    return


def transition(status_from, status_to, ticket_data):
    """ Transition handler. """
    print("Transition from %s to %s" % (status_from, status_to))
    # When a DCR issue is created, it must be approved before the
    # automation does anything with the issue. Therefore, we wait
    # for the issue to transition appropriately.
    if (status_from != "Waiting for approval" or
            status_to != "Approved"):
        return
    #
    # Create an account on LDAP for this person.
    create_ldap_account(ticket_data)

    #
    # Send them an email telling them how to set their password
    # and upload SSH keys.
    send_welcome_email(ticket_data)

    #
    # Create a ticket in the DC project to request a new
    # OpenStack project.
    create_openstack_ticket(ticket_data)
