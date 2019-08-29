""" Handler for RT206: test request type """

# Define what this handler can handle :)
# Using strings avoids the need to access defines elsewhere.
CAPABILITIES = [
    "CREATE",
    "COMMENT",
    "ASSIGNMENT",
    "TRANSITION"
]


SAVE_TICKET_DATA = True


def create(ticket_data):
    """ Create handler. """
    _ = ticket_data
    print("Create function has been called")


def comment(ticket_data):
    """ Comment handler. """
    _ = ticket_data
    print("Comment function has been called")


def transition(status_from, status_to, ticket_data):
    """ Transition handler. """
    _ = ticket_data
    print("Transition from %s to %s" % (status_from, status_to))


def assignment(assignee_from, assignee_to, ticket_data):
    """ Assignment handler. """
    _ = ticket_data
    print("Assigned from %s to %s" % (assignee_from, assignee_to))
