""" Shared code to retrieve secrets from Hashicorp Vault. """
import vault_auth
import shared.globals

# This code assumes that the secret being retrieved stores the
# sensitive information under the key "pw".

def get_secret(secret_path):
    secret = vault_auth.get_secret(
        secret_path,
        iam_role=shared.globals.CONFIGURATION["vault_iam_role"],
        url=shared.globals.CONFIGURATION["vault_server_url"]
    )
    return secret["data"]["pw"]
