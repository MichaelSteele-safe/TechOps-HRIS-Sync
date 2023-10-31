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
    
    # ukg_teams = get_org(3)
    # ukg_departments = get_org(1)
    batch_process_employees()
    
    # netsuite_departments = get_netsuite_entities("department")
    # netsuite_teams = get_netsuite_entities("team") 

    # syncOrg(ukg_departments, netsuite_departments, "department")
    # syncOrg(ukg_teams, netsuite_teams, "team")


def batch_process_employees():
    employee_count = get_employee_count()
    netsuite_employees = get_netsuite_entities("employee")
    netsuite_vendors = get_netsuite_entities("vendor")
    batch_size = 25
    for i in range(0, employee_count, batch_size):
        employee_batch = get_employees(batch_size, i)
        # print ("processing batch %d" % i)
        for employee in employee_batch:
            syncEmployee(employee, netsuite_employees, "employee")
            syncEmployee(employee, netsuite_vendors, "vendor")
    
def syncOrg(ukg_orgs, netsuite_orgs, type):
    for org in ukg_orgs:
        id_match = find_dict_by_key_value(org, netsuite_orgs, DB_NS_ORG_COL, "internalid")
        active = is_active(org)
        if active:
            if id_match:
                netsuite_team = find_dict_by_key_value(org, netsuite_orgs, DB_NS_ORG_COL, "internalid")
                if org["name"] != netsuite_team["name"]:
                    print("UPDATING %s NAME FROM %s TO %s " % (type, netsuite_team["name"],org["name"]))
                    # netsuite_org_request(org[DB_NS_ORG_COL], org["name"], "update", type)
            else:
                name_match = find_dict_by_key_value(org, netsuite_orgs, "name", "name")
                if name_match:
                    print("ADDING NETSUITE_ID TO DATABASE FOR %s %s " % (type, org["name"]))
                    add_id_to_db(name_match["internalid"], org["name"], type)
                elif org[DB_NS_ORG_COL]:
                    print("activate org") #todo
                else:
                    print("CREATING %s %s TO NETSUITE" % (type, org["name"]))
                    try:
                        create_response = netsuite_org_request(None, org["name"], "add", type)
                        add_id_to_db(create_response["success_record_info"][0]["internalid"], org["name"], type)
                    except Exception as e:
                        print(e)
        if not active and id_match:
            print("DEACTIVATING %s %s" % (type, org["name"]))
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
            # print("update employee in db %s " % employee["email"])
            print("")
            # netsuite_employee_request(employee, account_type, "update")
        else:
            email_match = find_dict_by_key_value(employee, netsuite_employees, "email", "email")
            if email_match:
                print("insert %s id to db %s " % (account_type, employee["email"]))
                add_id_to_db(email_match["internalid"], employee["email"], account_type)
                employee[key] = email_match["internalid"]
                # netsuite_employee_request(employee, account_type, "update")
            elif employee[key]:
                # todo activate employee
                print("")
                # print("activate %s" % account_type)
            else:
                print("adding %s to: %s" % (account_type, employee["email"]))
                try:
                    netsuite_employee_request(employee, account_type, "add")
                except Exception as e:
                    print(e)

    if not active and id_match:
        # delete employee
        print("")
        # print("deactivate %s %s" % (account_type, employee["email"]))

def add_id_to_db(id, identifier, type):
    if type == "team" or type == "department":
        query = """
            UPDATE users.ukg_teams
            SET %s = %s
            WHERE name = \"%s\"
            and archived is null
            and org_level = %s
        """ % (DB_NS_ORG_COL, id, identifier, 3 if type == "team" else 1)
    if type == "employee":
        query = """
            UPDATE users.ukg_users
            SET %s = %s
            WHERE email = \"%s\"
        """ % (DB_NS_EMPLOYEE_COL, id, identifier)
    if type == "vendor":
        query = """
            UPDATE users.ukg_users
            SET %s = %s
            WHERE email = \"%s\"
        """ % (DB_NS_VENDOR_COL, id, identifier)

    db_cursor.execute(query)
    db.commit()
      
def get_org(org_level):
    db_cursor.execute("""
        select name, %s, archived
        from users.ukg_teams
        where org_level = %d
    """ % (DB_NS_ORG_COL,org_level))
    response = db_cursor.fetchall()
    for org in response: 
        org[DB_NS_ORG_COL] = int(org[DB_NS_ORG_COL]) if org[DB_NS_ORG_COL] else org[DB_NS_ORG_COL]
    return response

def get_employee_count():
    db_cursor.execute("""
        SELECT COUNT(*) FROM users.ukg_users
        WHERE netsuite_admin = 0
    """)
    response = db_cursor.fetchall()
    return response[0]["COUNT(*)"]

def get_employees(batch_size, offset):
    db_cursor.execute("""
        select u.netsuite_employee_id, 
            u.%s, 
            u.%s, 
            u.email, 
            u.title, 
            u.first, 
            u.last, 
            u.preferred_first_name, 
            u.deactivated, 
            t.%s as "team_id", 
            team_lead.%s as "team_lead", 
            dep.`%s` as "department_id", 
            department_lead.netsuite_employee_id as "department_lead", 
            division.%s as "division_id", 
            division_lead.netsuite_employee_id as "division_lead"
        from users.ukg_users as u
        left join (
            SELECT id, `name`, parent_id, lead_id, %s from users.ukg_teams 
            where org_level = 3) as t on u.team_id = t.id
        left join (
            SELECT id, `name`, parent_id, lead_id, %s from users.ukg_teams 
            where org_level = 2) as dep on t.parent_id = dep.id OR u.team_id = dep.id
        left join (
            SELECT id, `name`, lead_id, %s from users.ukg_teams 
            where org_level = 1) as division on dep.parent_id = division.id OR u.team_id = division.id
        left join users.ukg_users as team_lead on t.lead_id = team_lead.id
        left join users.ukg_users as department_lead on dep.lead_id = department_lead.id
        left join users.ukg_users as division_lead on division.lead_id = division_lead.id
        where u.netsuite_admin = 0
        # and u.email = \"dami.obasa\"
        order by u.last DESC
        LIMIT %s OFFSET %s
    """ % (DB_NS_EMPLOYEE_COL, DB_NS_VENDOR_COL,DB_NS_ORG_COL,DB_NS_EMPLOYEE_COL,DB_NS_ORG_COL,DB_NS_ORG_COL,DB_NS_ORG_COL,DB_NS_ORG_COL,DB_NS_ORG_COL, batch_size, offset))
    response = db_cursor.fetchall()
    for employee in response:
        employee[DB_NS_EMPLOYEE_COL] = int(employee[DB_NS_EMPLOYEE_COL]) if employee[DB_NS_EMPLOYEE_COL] else employee[DB_NS_EMPLOYEE_COL]
        employee[DB_NS_VENDOR_COL] = int(employee[DB_NS_VENDOR_COL]) if employee[DB_NS_VENDOR_COL] else employee[DB_NS_VENDOR_COL]
        employee["team_id"] = int(employee["team_id"]) if employee["team_id"] else employee["team_id"]
        employee["division_id"] = int(employee["division_id"]) if employee["division_id"] else employee["division_id"]
        employee["email"] = employee["email"].lower() if employee["email"] else None
    return response

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
    # obj = [{
    #     "type": type,
    #     "action": action,
    #     "custbody_acs_projtype": 5,
    #     "isperson":"T",
    #     "firstname": employee["first"],
    #     "lastname": employee["last"],
    #     "email": "%s@safe.com" % employee["email"],
    #     "title": employee["title"],
    #     "department": employee["division_id"],
    #     "custentity_safe_sw_team": employee["team_id"]
    # }]
    obj = [{
        "type": type,
        "action": action,
        "custbody_acs_projtype": 5,
        "isperson":"T",
        "firstname": employee["first"],
        "lastname": employee["last"] if type == "employee" else employee["last"]+" (Vendor)",
        "email": "%s@safe.com" % employee["email"],
        "title": employee["title"],
        "supervisor": employee["team_lead"]
    }]
    if action != "add":
        obj[0]["id"] = employee[DB_NS_EMPLOYEE_COL]
    make_netsuite_request("POST", obj, None)


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
    for item in lst:
        if obj[obj_key] == item[lst_key]:
            return item
    return None