#!/usr/bin/python3

import os
import sys

import json
from unittest.mock import patch, mock_open
import pytest

# Tell Python where to find the webhook automation code.
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))) + "/sd_webhook_automation")
import config  # noqa


def test_config_initialise():
    with patch("builtins.open", mock_open(
        read_data='{"bot_name": "name", "bot_password": "password"}\n'
    )):
        config.initialise()
        assert config.configuration["bot_name"] == "name"
        assert config.configuration["bot_password"] == "password"


# This one raises an exception because there is no data (the file is empty)
def test_missing_credentials_1():
    with patch("builtins.open", mock_open(
        read_data=''
    )):
        with pytest.raises(json.decoder.JSONDecodeError):
            config.initialise()


# This one doesn't raise an exception because it is a valid empty JSON block.
def test_missing_credentials_2():
    with patch("builtins.open", mock_open(
        read_data='{}\n'
    )):
        config.initialise()
