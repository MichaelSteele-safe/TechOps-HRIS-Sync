import os
import boto3
import json
import time
from datetime import datetime
import pymysql
import sqlalchemy as db
import oauth2 as oauth
import requests

# For SHA256 local
from hashlib import sha256
import hmac
import binascii

def execute_query(query):
    DB_USER = get_access_token('/REL/Database/set_rds_username')
    DB_PASS = get_access_token('/REL/Database/set_rds_password')
    DB_HOST = get_access_token('/REL/Database/set_rds_host')
    engine = db.create_engine("mysql+pymysql://%s:%s@%s:%s/release" %(DB_USER, DB_PASS, DB_HOST, 3306))
    connection = engine.connect()

    return connection.execute(query).fetchall()

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

NS_ENV = "Sandbox"
""" Read in our credentials for accessing NetSuite """
NS_ACCOUNT = get_access_token('/REL/Netsuite/' + NS_ENV + '/ACCOUNT')
NS_CONSUMER_KEY = get_access_token('/REL/Netsuite/' + NS_ENV + '/CONSUMER_KEY')
NS_CONSUMER_SECRET = get_access_token('/REL/Netsuite/' + NS_ENV + '/NS_CONSUMER_SECRET')
NS_TOKEN_KEY = get_access_token('/REL/Netsuite/' + NS_ENV + '/NS_TOKEN_KEY')
NS_TOKEN_SECRET = get_access_token('/REL/Netsuite/' + NS_ENV + '/NS_TOKEN_SECRET')
NS_HOST = "https://436874-sb1.restlets.api.netsuite.com/app/site/hosting/restlet.nl?script=582&deploy=1"

def make_netsuite_request(obj, params, http_method):
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
        ns_url = NS_HOST + params
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
        ns_request = oauth.Request(method=http_method, url=ns_url, parameters=auth_params)
        # signature_method = oauth.SignatureMethod_HMAC_SHA256() # Original calling oauth2 library, commented out Oct 4 2021 by Steven
        signature_method = SignatureMethod_HMAC_SHA256_local()
        ns_request.sign_request(signature_method, ns_consumer, ns_token)
        # Adding headers to request
        header = ns_request.to_header(ns_realm)
        encoded_header = header['Authorization'].encode('ascii', 'ignore')
        header = {"Authorization": encoded_header, "Content-Type":"application/json"}
        # print("NS_HOST: %s" % ns_url)
        # Make the request to NetSuite and return response as JSON Object
        if http_method == "GET":
            results = requests.get(ns_url,headers=header)
        elif http_method == "POST":
            results = requests.post(ns_url,headers=header,json=obj)
        elif http_method == "PUT":
            results = requests.put(ns_url,headers=header,json=obj)

        #error handling
        if results.status_code == 200:
            return results.json()
        else:
            print("Error: %s" % results.status_code)
            print(results.text)
            print(results.json())
            return results.json()
    except requests.exceptions.RequestException as e:
        print(e)

def get_netsuite_list(type):
    response = make_netsuite_request(None, "&type=%s" % type, "GET")
    return response["search_details"]

def add_employee(employee, team_lead_id, team_id, department_id):
    obj = [{
                "type": "employee",
                "action":"add",
                "custbody_acs_projtype": 5,
                "isperson":"T",
                "firstname": employee["first"],
                "lastname": employee["last"],
                "email": employee["email"] + "@safe.com",
                "title": employee["title"],
                "supervisor": team_lead_id,
                "department": department_id,
                "custentity_safe_sw_team": team_id
            }]
    response = make_netsuite_request(obj, "", "POST")
    print(response)

def add_vendor(vendor):
    obj = [{
                "type": "vendor",
                "customform": 139,
                "action":"add",
                "custbody_acs_projtype": 5,
                "isperson":"T",
                "firstname": vendor["first"],
                "lastname": vendor["last"] + "(Vendor)",
                "email": vendor["email"]
            }]
    make_netsuite_request(obj, "", "POST")

def add_team(team):
    obj = [{
        "action": "add",
        "type": "team",
        "name": team,
        "parent": 114,
        "custbody_acs_projtype": ""
    }]
    make_netsuite_request(obj, "", "POST")

def add_department(department):
    obj = [{
        "action": "add",
        "type": "department",
        "name": department,
        "parent": 15,
        "custbody_acs_projtype": ""
    }]
    make_netsuite_request(obj, "", "POST")

def main():

    try:
        db_employees = execute_query("""
            SELECT email, first, last, title, tt.team_name, tt.team_lead, tt.department
            FROM users.ukg_users as uu
            LEFT JOIN (
                SELECT ut.id, ut.name as 'team_name', email as 'team_lead', parent.name as 'department'
                FROM users.ukg_teams as ut 
                LEFT JOIN users.ukg_users as uu on ut.lead_id = uu.id
                LEFT JOIN users.ukg_teams as parent on parent.id = ut.parent_id
            ) as tt on tt.id = uu.team_id
            WHERE uu.deactivated IS NULL and uu.id = 1458;
        """)
        netsuite_employees = get_netsuite_list("employee")
        netsuite_vendors = get_netsuite_list("vendor")
        netsuite_teams = get_netsuite_list("team")
        netsuite_departments = get_netsuite_list("department")

        #get list of distinct team_names from db_employees
        distinct_teams = list(set([employee["team_name"] for employee in db_employees]))

        #get list of distinct departments from db_employees
        distinct_departments = list(set([employee["department"] for employee in db_employees]))

        #if any distinct_teams are not in netsuite_teams add to netsuite
        for team in distinct_teams:
            if not any(t['name'] == team for t in netsuite_teams):
                print("adding team %s" % team)
                add_team(team)

        #if any distinct_departments are not in netsuite_departments add to netsuite
        for department in distinct_departments:
            if not any(d['name'] == department for d in netsuite_departments):
                print("adding department %s" % department)
                add_department(department)

        for employee in db_employees:
            #add @safe.com to each employee email to match netsuite
            employee_email = employee["email"].lower() + "@safe.com"
            team_lead_email = employee["team_lead"].lower() + "@safe.com"
            #if employee email is not in netsuite_employees add to netsuite 
            if not any(e['email'].lower() == employee_email for e in netsuite_employees):
                #find id of team lead in netsuite_employees match on employee_email
                team_lead = next((e for e in netsuite_employees if e["email"].lower() == team_lead_email), None)
                #find id of team in netsuite_teams match on team_name
                ns_team = next((t for t in netsuite_teams if t["name"].lower() == employee["team_name"].lower()), None)
                #find id of department in netsuite_departments match on department
                ns_department = next((t for t in netsuite_departments if t["name"].lower() == employee["department"].lower()), None)

                print("adding employee %s" % employee["email"])
                add_employee(employee, team_lead["internalid"], ns_team["internalid"], ns_department["internalid"])

            #if employee email is not in netsuite_employees add to netsuite ignore case
            if not any(v['email'].lower() == employee_email for v in netsuite_vendors):
                print("adding vendor %s" % employee["email"])
                add_vendor(employee)
    
    except requests.exceptions.RequestException as e:
        print(e)

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

if __name__ == '__main__':
    main()