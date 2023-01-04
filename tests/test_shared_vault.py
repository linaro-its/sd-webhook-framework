#!/usr/bin/python3
""" Test the shared vault library. """
import shared.globals
import shared.shared_vault as shared_vault
import mock

@mock.patch(
    'vault_auth.get_secret',
    return_value= {
        "data" : {
            "password" : "my secret"
        }
    },
    autospec=True
)

def test_get_secret_1(mock_get_secret):
    """Test to retrieve a secret """
    secret_path = "/tmp/path/"
    shared.globals.CONFIGURATION = {
        "vault_iam_role" : "test_role",
        "vault_server_url" : "https://mock-server/"
    }
    result = shared_vault.get_secret(secret_path, key="password")
    assert mock_get_secret.called is True
    assert result == "my secret"
