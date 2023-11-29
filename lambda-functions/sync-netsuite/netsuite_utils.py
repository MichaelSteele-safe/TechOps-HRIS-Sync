import json
import time
import oauth2 as oauth
import requests
import strings

# For SHA256 local
from hashlib import sha256
import hmac
import binascii

def make_netsuite_request(http_method, obj, params):
    """
    This function is a helper used for all the GET / informational routes that interact with
    the NetSuite
    """
    # Assemble the URL
    # Populate Token and Consumer objects for OAuth1 Flow as well as Realm
    ns_token = oauth.Token(key=strings.NS_TOKEN_KEY, secret=strings.NS_TOKEN_SECRET)
    ns_consumer = oauth.Consumer(key=strings.NS_CONSUMER_KEY, secret=strings.NS_CONSUMER_SECRET)
    ns_realm= strings.NS_ACCOUNT
    # Dictionary holding our OAuth1 Flow Details
    auth_params = {
        'oauth_version': "1.0",
        'oauth_nonce': oauth.generate_nonce(),
        # Must typecast timestamp to String
        'oauth_timestamp': str(int(time.time())),
        'oauth_token': ns_token.key,
        'oauth_consumer_key': ns_consumer.key
    }
    if params != None:
        auth_params.update(params)
    # Start building our request object
    ns_request = oauth.Request(method=http_method, url=strings.NS_HOST, parameters=auth_params)
    # signature_method = oauth.SignatureMethod_HMAC_SHA256() # Original calling oauth2 library, commented out Oct 4 2021 by Steven
    signature_method = SignatureMethod_HMAC_SHA256_local()
    ns_request.sign_request(signature_method, ns_consumer, ns_token)
    # Adding headers to request
    header = ns_request.to_header(ns_realm)
    encoded_header = header['Authorization'].encode('ascii', 'ignore')
    header = {"Authorization": encoded_header, "Content-Type":"application/json"}
    # Make the request to NetSuite and return response as JSON Object
    if http_method == "POST":
        results = requests.post(strings.NS_HOST,headers=header,json=obj)
    if http_method == "PUT":
        results = requests.put(strings.NS_HOST,headers=header,json=obj)
    if http_method == "GET":
        results = requests.get(strings.NS_HOST,headers=header, params=params)

    if results.ok:
        result_json = results.json()
        result_json = result_json[0] if isinstance(result_json, list) else result_json
        if "error_message" in result_json or "error_name" in result_json:
            raise Exception("Error calling NetSuite: %s" % result_json["error_message"])
        if http_method == "POST" and len(result_json["failed_record_info"]) > 0:
            print("tried to process: %s" + json.dumps(obj, indent=4))
            raise Exception("Error creating record in NetSuite: %s" % result_json["failed_record_info"])
        return results.json()
    else:
        raise Exception("Error making request to NetSuite: %s" % results.text)

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