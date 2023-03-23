
import os
import json
import time
from datetime import datetime
import oauth2 as oauth
import requests
import aws_functions

# For SHA256 local
from hashlib import sha256
import hmac
import binascii

NS_ENV = "Production"
""" Read in our credentials for accessing NetSuite """
NS_ACCOUNT = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/ACCOUNT')
NS_CONSUMER_KEY = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/CONSUMER_KEY')
NS_CONSUMER_SECRET = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/CONSUMER_SECRET')
NS_TOKEN_KEY = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/TOKEN_KEY')
NS_TOKEN_SECRET = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/TOKEN_SECRET')
NS_APPID = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/APPID')
NS_HOST = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/HOST')

def make_netsuite_request(obj, http_method):
    """
    This function is a helper used for all the GET / informational routes that interact with
    the NetSuite
    """
    try:
        # Assemble the URL
        # Populate Token and Consumer objects for OAuth1 Flow as well as Realm
        ns_token = oauth.Token(key=NS_TOKEN_KEY, secret=NS_TOKEN_SECRET)
        ns_consumer = oauth.Consumer(key=NS_CONSUMER_KEY, secret=NS_CONSUMER_SECRET)
        ns_realm= NS_ACCOUNT
        # Dictionary holding our OAuth1 Flow Details
        auth_params = {
            'oauth_version': "1.0",
            'oauth_nonce': oauth.generate_nonce(),
            # Must typecast timestamp to String
            'oauth_timestamp': str(int(time.time())),
            'oauth_token': ns_token.key,
            'oauth_consumer_key': ns_consumer.key
        }
        # Start building our request object
        ns_request = oauth.Request(method=http_method, url=NS_HOST, parameters=auth_params)
        # signature_method = oauth.SignatureMethod_HMAC_SHA256() # Original calling oauth2 library, commented out Oct 4 2021 by Steven
        signature_method = SignatureMethod_HMAC_SHA256_local()
        ns_request.sign_request(signature_method, ns_consumer, ns_token)
        # Adding headers to request
        header = ns_request.to_header(ns_realm)
        encoded_header = header['Authorization'].encode('ascii', 'ignore')
        header = {"Authorization": encoded_header, "Content-Type":"application/json"}
        print("NS_HOST: %s" % NS_HOST)
        # Make the request to NetSuite and return response as JSON Object
        results = requests.post(NS_HOST,headers=header,json=obj)
        if results.ok:
            return results.json()
        else: 
            return False
    except requests.exceptions.RequestException as e:
        print(e)

def lambda_handler(event, context):
    print(event)
    body = json.loads(event["body"])
    try:
        obj = None
        if body["type"] == "vendor":
            obj = [{
                        "type": "vendor",
                        "customform": 139,
                        "action":"add",
                        "custbody_acs_projtype": 5,
                        "isperson":"T",
                        "firstname": body["first"],
                        "lastname": body["last"],
                        "email": body["email"],
                        "title": body["title"]
                }]
        else:
            obj = [{
                "type": "employee",
                "action":"add",
                "custbody_acs_projtype": 5,
                "isperson":"T",
                "firstname": body["first"],
                "lastname": body["last"],
                "email": body["email"],
                 "title": body["title"]
            }]
            # obj[0]["department"] = body["department"] if body["department"] else None
            # obj[0]["custentity_safe_sw_team"] = body["team"] if body["team"] else None

        print(obj)
        response = make_netsuite_request(obj, "POST")
        print("create status %s" % response['status'])
        print(response["failed_record_info"])
        if response["status"] == "processed" and len(response["failed_record_info"]) == 0:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "*/*"
                }
            }
        else:
            return {
                "statusCode": 400
            }
    
    except requests.exceptions.RequestException as e:
        print(e)
        return {
                "statusCode": 400
            }

class SignatureMethod_HMAC_SHA256_local(oauth.SignatureMethod):
    name = 'HMAC-SHA256'

    def signing_base(self, request, consumer, token):
        if (not hasattr(request, 'normalized_url') or request.normalized_url is None):
            raise ValueError("Base URL for request is not set.")

        sig = (
            oauth.escape(request.method),
            oauth.escape(request.normalized_url),
            oauth.escape(request.get_normalized_parameters()),
        )

        key = '%s&' % oauth.escape(consumer.secret)
        if token:
            key += oauth.escape(token.secret)
        raw = '&'.join(sig)
        return key.encode('ascii'), raw.encode('ascii')

    def sign(self, request, consumer, token):
        """Builds the base signature string."""
        key, raw = self.signing_base(request, consumer, token)

        hashed = hmac.new(key, raw, sha256)

        # Calculate the digest base 64.
        return binascii.b2a_base64(hashed.digest())[:-1]

# if __name__ == '__main__':
#     event = {
#         "body": {
#             "first": "Test First",
#             "last": "Test Last",
#             "email": "test@safe.com",
#             "title": "title tester"
#         }
#     }
#     lambda_handler(event, None)