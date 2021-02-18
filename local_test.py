""" Simple example to test functionality """
import app
import json

with open("comment.json", "r") as handle:
    data = json.load(handle)

app.APP.testing = True
with app.APP.test_client() as c:
    c.post(
        "/comment",
        json=data)
