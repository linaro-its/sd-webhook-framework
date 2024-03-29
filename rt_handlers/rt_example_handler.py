""" Test handler """

# Define what this handler can handle :)
# Using strings avoids the need to access defines elsewhere.
CAPABILITIES = [
    "CREATE",
    "COMMENT",
    "ASSIGNMENT",
    "TRANSITION",
    "ORGCHANGE",
    "JIRAHOOK"
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


def transition(status_to, ticket_data):
    """ Transition handler. """
    _ = ticket_data
    print("Transition to %s" % status_to)


def assignment(assignee_to, ticket_data):
    """ Assignment handler. """
    _ = ticket_data
    print("Assigned to %s" % assignee_to)


def org_change(ticket_data):
    """ Org change handler. """
    _ = ticket_data
    print("Org change function has been called")


def jira_hook(ticket_data):
    """ General Jira hook handler. """
    _ = ticket_data
    print("Jira hook function has been called")
