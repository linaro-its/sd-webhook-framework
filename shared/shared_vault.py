""" Shared code to retrieve secrets from Hashicorp Vault. """
import boto3
import hvac
import requests

import shared.globals

def get_vault_secret(secret_path: str, iam_role: str, url: str) -> str:
    """ Retrieve a secret from Hashicorp Vault """
    # Assume the desired IAM role
    sts_client = boto3.client('sts')
    print(f"get_vault_secret: assuming role {iam_role}")
    assumed_role_object = sts_client.assume_role(
        RoleArn=iam_role,
        RoleSessionName="AssumeRoleSession1"
    )
    assumed_credentials = assumed_role_object['Credentials']
    # Authenticate to Vault and get a Vault token back
    client = hvac.Client(url=url)
    token = client.auth.aws.iam_login(
        assumed_credentials['AccessKeyId'],
        assumed_credentials['SecretAccessKey'],
        assumed_credentials['SessionToken'])
    # Now request the secret with that token
    header = {
        "X-Vault-Token": token["auth"]["client_token"]
    }
    response = requests.get(
        f"{url}/v1/{secret_path}",
        headers=header,
        timeout=60)
    secret = response.json()
    # Revoke the Vault token now that we're done with it.
    requests.post(
        f"{url}/v1/auth/token/revoke-self",
        headers=header,
        timeout=60)
    response.raise_for_status()
    return secret["data"]

def get_secret(secret_path, key="pw"):
    """ Retrieve a secret from Hashicorp Vault service """
    secret = get_vault_secret(
        secret_path,
        iam_role=shared.globals.CONFIGURATION["vault_iam_role"],
        url=shared.globals.CONFIGURATION["vault_server_url"]
    )
    if key in secret:
        return secret[key]
    return None
