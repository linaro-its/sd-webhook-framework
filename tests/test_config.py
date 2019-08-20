#!/usr/bin/python3
""" Test sd_webhook_automation/config functionality """

import json
from unittest.mock import patch, mock_open
import pytest

import shared.config as config


def test_config_initialise():
    """ Test config_initialise """
    with patch("builtins.open", mock_open(
            read_data='{"bot_name": "name", "bot_password": "password"}\n'
    )):
        config.initialise()
        assert config.CONFIGURATION["bot_name"] == "name"
        assert config.CONFIGURATION["bot_password"] == "password"


# This one raises an exception because there is no data (the file is empty)
def test_missing_credentials_1():
    """ Test that an exception is raised. """
    with patch("builtins.open", mock_open(
            read_data=''
    )):
        with pytest.raises(json.decoder.JSONDecodeError):
            config.initialise()


# This one doesn't raise an exception because it is a valid empty JSON block.
def test_missing_credentials_2():
    """ Test that this doesn't raise an exception. """
    with patch("builtins.open", mock_open(
            read_data='{}\n'
    )):
        config.initialise()
