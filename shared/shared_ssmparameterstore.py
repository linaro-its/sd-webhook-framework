
""" Script to retrieve parameter value from AWS Systems Manager Parameter Store"""
import json
import boto3

ROLE_ARN = "arn:aws:iam::487149096843:role/ssm-parameter-store-access-role"

def assume_role(session_name="CrossAccountSession"):
    """Assume a role in Account 487149096843 and return temporary credentials"""
    sts_client = boto3.client("sts")
    assumed_role = sts_client.assume_role(
        RoleArn=ROLE_ARN,
        RoleSessionName=session_name
    )
    return assumed_role["Credentials"]

def get_secret_from_ssm_parameter_store(parameter_name, key=None, with_decryption=True):
    """Retrieve a parameter value from AWS Systems Manager Parameter Store"""
    credentials = assume_role()
    ssm_client = boto3.client(
        "ssm",
        region_name="us-east-1",
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"]
    )

    # Get the parameter
    response = ssm_client.get_parameter(
        Name=parameter_name,
        WithDecryption=with_decryption
    )
    parameter_value = response["Parameter"]["Value"]
    data = json.loads(parameter_value)

    # Return the "key" if passed, otherwise return "pw"
    if key:
        return data.get(key, None)
    else:
        return data.get("pw", None)