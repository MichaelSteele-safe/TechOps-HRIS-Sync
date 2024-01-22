import boto3

def get_access_token(path):
    """ Return a token from Parameter Store """
    try:
        ssm = boto3.client('ssm', region_name='us-west-2')
        access_token = ssm.get_parameter(Name=path, WithDecryption=True)
        token = access_token['Parameter']['Value']
        return token

    except Exception as e:
        print(str(e))
        raise