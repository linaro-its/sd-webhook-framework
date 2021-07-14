""" Shared code to retrieve secrets from Hashicorp Vault. """
import vault_auth
import shared.globals


def get_secret(secret_path, key="pw"):
    """ Retrieve a secret from Hashicorp Vault service """
    secret = vault_auth.get_secret(
        secret_path,
        iam_role=shared.globals.CONFIGURATION["vault_iam_role"],
        url=shared.globals.CONFIGURATION["vault_server_url"]
    )
    return secret["data"][key]
