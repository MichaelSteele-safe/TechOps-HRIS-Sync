import json
import time
import oauth2 as oauth
import requests
import aws_functions
import mysql.connector

# For SHA256 local
from hashlib import sha256
import hmac
import binascii

from db_queries import add_id_to_db, get_org, get_employee_count, get_employees

NS_ENV = "Production"
""" Read in our credentials for accessing NetSuite """
NS_ACCOUNT = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/ACCOUNT')
NS_CONSUMER_KEY = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/CONSUMER_KEY')
NS_CONSUMER_SECRET = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/CONSUMER_SECRET')
NS_TOKEN_KEY = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/TOKEN_KEY')
NS_TOKEN_SECRET = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/TOKEN_SECRET')
NS_APPID = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/APPID')
NS_HOST = aws_functions.get_access_token('/TechOps/Netsuite/' + NS_ENV + '/HOST')
DB_HOST = aws_functions.get_access_token("/REL/Database/set_rds_host")
DB_USER = aws_functions.get_access_token("/REL/Database/set_rds_username")
DB_PASSWORD = aws_functions.get_access_token("/REL/Database/set_rds_password")

db = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        passwd=DB_PASSWORD,
        database="users",
        port=3306
    )
db_cursor = db.cursor(dictionary=True)

DB_NS_EMPLOYEE_COL = "netsuite_employee_id_sb" if NS_ENV == "Sandbox" else "netsuite_employee_id"
DB_NS_VENDOR_COL = "netsuite_vendor_id_sb" if NS_ENV == "Sandbox" else "netsuite_vendor_id"
DB_NS_ORG_COL = "netsuite_id_sb" if NS_ENV == "Sandbox" else "netsuite_id"

def lambda_handler(event, context):
    # get data from db
    
    # ukg_teams = get_org(db,3)
    # ukg_departments = get_org(db, 1)
    batch_process_employees()
    
    # netsuite_departments = get_netsuite_entities("department")
    # netsuite_teams = get_netsuite_entities("team") 

    # syncOrg(ukg_departments, netsuite_departments, "department")
    # syncOrg(ukg_teams, netsuite_teams, "team")


def batch_process_employees():
    employee_count = get_employee_count(db)
    netsuite_employees = get_netsuite_entities("employee")
    netsuite_vendors = get_netsuite_entities("vendor")
    batch_size = 25 
    for i in range(0, employee_count, batch_size):
        employee_batch = get_employees(db, batch_size, i)
        # print ("processing batch %d" % i)
        for employee in employee_batch:
            syncEmployee(employee, netsuite_employees, "employee")
            syncEmployee(employee, netsuite_vendors, "vendor")
    
def syncOrg(ukg_orgs, netsuite_orgs, type):
    for org in ukg_orgs:
        id_match = find_dict_by_key_value(org, netsuite_orgs, DB_NS_ORG_COL, "internalid")
        # print("id match:")
        # print(id_match)
        active = is_active(org)
        name_match = find_dict_by_key_value(org, netsuite_orgs, "name", "name")
        if active:
            if id_match:
                netsuite_team = find_dict_by_key_value(org, netsuite_orgs, DB_NS_ORG_COL, "internalid")
                if org["name"] != netsuite_team["name"]:
                    print("update %s name from %s to %s " % (type, netsuite_team["name"],org["name"]))
                    # netsuite_org_request(org[DB_NS_ORG_COL], org["name"], "update", type)
            else:
                name_match = find_dict_by_key_value(org, netsuite_orgs, "name", "name")
                if name_match:
                    print("ADDING NETSUITE_ID TO DATABASE FOR %s %s " % (type, org["name"]))
                    # add_id_to_db(db, name_match["internalid"], org["name"], type)
                # elif org[DB_NS_ORG_COL]:
                #     print("activate org") 
                else:
                    print("create %s %s" % (type, org["name"]))
                    try:
                        create_response = netsuite_org_request(None, org["name"], "add", type)
                        add_id_to_db(db, create_response["success_record_info"][0]["internalid"], org["name"], type)
                    except Exception as e:
                        print(e)

        if not active and id_match:
            print("deactivate %s %s" % (type, org["name"]))
            # create_response = netsuite_org_request(None, org["name"], "inactive", type)

def syncEmployee(employee, netsuite_employees, account_type):
    if account_type == "employee":
        key = DB_NS_EMPLOYEE_COL
    else:
        key = DB_NS_VENDOR_COL

    # print("processing %s: %s" % (account_type, employee["email"]))
    id_match = find_dict_by_key_value(employee, netsuite_employees, key, "internalid")

    active = is_active(employee)
    if active:
        if id_match:
            print("update %s in db %s " % (account_type,employee["email"]))
            netsuite_employee_request(employee, account_type, "update")
        else:
            email_match = find_dict_by_key_value(employee, netsuite_employees, "email", "email")
            if email_match:
                print("insert and update %s %s id to db " % (account_type, employee["email"]))
                add_id_to_db(db, email_match["internalid"], employee["email"], account_type)
                employee[key] = email_match["internalid"]
                netsuite_employee_request(employee, account_type, "update")
            elif employee[key]:
                # todo activate employee
                print("activate %s %s" % (account_type, employee["email"]))
                netsuite_employee_request(employee, account_type, "active")
            else:
                try:
                    print("adding %s to: %s" % (account_type, employee["email"]))
                    netsuite_employee_request(employee, account_type, "add")
                except Exception as e:
                    print(e)

    if not active and id_match:
        # delete employee
        print("deactivate %s %s" % (account_type, employee["email"]))
        netsuite_employee_request(employee, account_type, "inactive")

def get_netsuite_entities(type):
    netsuite_entities = (make_netsuite_request("GET", None, {"type":type}))["search_details"]
    for entity in netsuite_entities:
        entity["email"] = entity["email"].split("@")[0].lower() if "email" in entity else None
        entity["internalid"] = int(entity["internalid"])
    return netsuite_entities

def netsuite_org_request(id, name, action, type):
    parent = "15" if type == "department" else "114"
    if action == "create":
        body = [
            {
                "action": action,
                "type": type,
                "name": name,
                "parent": parent,
                "custbody_acs_projtype": ""
            }
        ]
    else:
        body = [
            {
                "action": action,
                "type": type,
                "name": name,
                "id": id,
                "parent": parent,
                "custbody_acs_projtype": ""
            }
        ]
    return make_netsuite_request("POST", body, None)

def netsuite_employee_request(employee, type, action):
    key = DB_NS_EMPLOYEE_COL if type == "employee" else DB_NS_VENDOR_COL
    request_type = "POST"
    obj = [{
        "type": type,
        "action": action,
        "isperson":"T",
        "firstname": employee["first"],
        "lastname": employee["last"],
        "email": "%s@safe.com" % employee["email"],
        "title": employee["title"],
        "custbody_acs_projtype":  5
    }]
    if type == "employee":
        obj[0]["issalesrep"] = employee["issalesrep"]
        obj[0]["supervisor"] = employee["team_lead"]
        # obj[0]["department"] = employee["division_id"]
        # obj[0]["custentity_safe_sw_team"] = employee["team_id"]

    if type == "vendor":
        obj[0]["category"] = 5
        
    if action != "add":
        request_type = "PUT"
        obj[0]["id"] = employee[key]
    make_netsuite_request(request_type, obj, None)


def make_netsuite_request(http_method, obj, params):
    """
    This function is a helper used for all the GET / informational routes that interact with
    the NetSuite
    """
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
    if params != None:
        auth_params.update(params)
    # Start building our request object
    ns_request = oauth.Request(method=http_method, url=NS_HOST, parameters=auth_params)
    # signature_method = oauth.SignatureMethod_HMAC_SHA256() # Original calling oauth2 library, commented out Oct 4 2021 by Steven
    signature_method = SignatureMethod_HMAC_SHA256_local()
    ns_request.sign_request(signature_method, ns_consumer, ns_token)
    # Adding headers to request
    header = ns_request.to_header(ns_realm)
    encoded_header = header['Authorization'].encode('ascii', 'ignore')
    header = {"Authorization": encoded_header, "Content-Type":"application/json"}
    # Make the request to NetSuite and return response as JSON Object
    if http_method == "POST":
        results = requests.post(NS_HOST,headers=header,json=obj)
    if http_method == "PUT":
        results = requests.put(NS_HOST,headers=header,json=obj)
    if http_method == "GET":
        results = requests.get(NS_HOST,headers=header, params=params)

    if results.ok:
        result_json = results.json()
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

def is_active(item):
    if "deactivated" in item:
        return item["deactivated"] == None
    else:
        return item["archived"] == None

def find_dict_by_key_value(obj, lst, obj_key, lst_key):
    # print("==find_dict_by_key_value")
    # print("lst key: %s, obj_key: %s" % (lst_key, obj_key))
    # print(obj[obj_key])
    for item in lst:
        if obj[obj_key] == item[lst_key]:
            return item
    return None