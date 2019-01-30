# Handler for RT206: test request type

# Define what this handler can handle :)
# Using strings avoids the need to access defines elsewhere.
capabilities = [
    "CREATE",
    "COMMENT",
    "ASSIGNMENT",
    "TRANSITION"
]


save_ticket_data = True


def create(ticket_data):
    print("Create function has been called")


def comment(ticket_data):
    print("Comment function has been called")


def transition(status_from, status_to, ticket_data):
    print("Transition from %s to %s" % (status_from, status_to))


def assignment(assignee_from, assignee_to, ticket_data):
    print("Assigned from %s to %s" % (assignee_from, assignee_to))
