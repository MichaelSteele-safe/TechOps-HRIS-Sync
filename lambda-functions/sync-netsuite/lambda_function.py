import mysql.connector
import requests
import strings
from netsuite_utils import make_netsuite_request
from db_queries import add_id_to_db, get_orgs_from_db, get_employees_from_db

db = mysql.connector.connect(
        host=strings.DB_HOST,
        user=strings.DB_USER,
        passwd=strings.DB_PASSWORD,
        database="users",
        port=3306
    )
db_cursor = db.cursor(dictionary=True)

def lambda_handler(event, context):
    ukg_teams = get_orgs(db,3)
    ukg_departments = get_orgs(db, 1)
    ukg_employees = get_employees(db)

    netsuite_departments = get_netsuite_entities("department")
    netsuite_teams = get_netsuite_entities("team") 
    netsuite_employees = get_netsuite_entities("employee")
    netsuite_vendors = get_netsuite_entities("vendor")

    syncOrg(ukg_departments, netsuite_departments, "department")
    syncOrg(ukg_teams, netsuite_teams, "team")

    for employee in ukg_employees:
        syncEmployee(employee, netsuite_employees, "employee")
        syncEmployee(employee, netsuite_vendors, "vendor")

def syncOrg(ukg_orgs, netsuite_orgs, type):
    for org in ukg_orgs:
        print("processing %s: %s" % (type, org["name"]))
        id_match = find_dict_by_key_value(org, netsuite_orgs, strings.DB_NS_ORG_COL, "internalid")
        active = is_active(org)
        name_match = find_dict_by_key_value(org, netsuite_orgs, "name", "name")
        if active:
            if id_match:
                netsuite_team = find_dict_by_key_value(org, netsuite_orgs, strings.DB_NS_ORG_COL, "internalid")
                if type != "department" and org["name"] != netsuite_team["name"]:
                    print("update %s name from %s to %s " % (type, netsuite_team["name"],org["name"]))
                    netsuite_org_request(org, "update", type)
                    notifyTechOpsChannel("HRIS - Netsuite %s name updated" % type, "%s -> %s" % (netsuite_team["name"], org["name"]), "good")
                else:
                    print("Nothing to do, up to date")
            else:
                name_match = find_dict_by_key_value(org, netsuite_orgs, "name", "name")
                if name_match:
                    print("ADDING NETSUITE_ID TO DATABASE FOR %s %s " % (type, org["name"]))
                    add_id_to_db(db, name_match["internalid"], org["name"], type)
                elif org[strings.DB_NS_ORG_COL]:
                    print("activate org") 
                    netsuite_org_request(org, org["name"], "active", type)
                    notifyTechOpsChannel("HRIS - Netsuite %s reactivated" % type, org["name"], "good")
                else:
                    try:
                        print("create %s %s" % (type, org["name"]))
                        create_response = netsuite_org_request(org, "add", type)
                        add_id_to_db(db, create_response["success_record_info"][0]["internalid"], org["name"], type)
                        notifyTechOpsChannel("HRIS - Netsuite %s created" % type, org["name"], "good")
                    except Exception as e:
                        print(e)

        if not active and id_match:
            print("deactivate %s %s" % (type, org["name"]))
            create_response = netsuite_org_request(org, "inactive", type)
            notifyTechOpsChannel("HRIS - Netsuite team deactivated", org["name"], "danger")

def syncEmployee(employee, netsuite_employees, account_type):
    if account_type == "employee":
        key = strings.DB_NS_EMPLOYEE_COL
    else:
        key = strings.DB_NS_VENDOR_COL

    id_match = find_dict_by_key_value(employee, netsuite_employees, key, "internalid")

    active = is_active(employee)
    if active:
        if id_match:
            print("Updating %s %s" % (account_type, employee["email"]))
            netsuite_employee_request(employee, account_type, "update")
        else:
            email_match = find_dict_by_key_value(employee, netsuite_employees, "email", "email")
            if email_match:
                print("insert and update %s %s id to db " % (account_type, employee["email"]))
                add_id_to_db(db, email_match["internalid"], employee["email"], account_type)
                employee[key] = email_match["internalid"]
                netsuite_employee_request(employee, account_type, "update")
            elif employee[key]:
                print("activate %s %s" % (account_type, employee["email"]))
                netsuite_employee_request(employee, account_type, "active")
                notifyTechOpsChannel("HRIS - Netsuite %s reactivated" % type, employee["email"], "good")
            else:
                try:
                    print("adding %s to: %s" % (account_type, employee["email"]))
                    netsuite_employee_request(employee, account_type, "add")
                    notifyTechOpsChannel("HRIS - Netsuite %s create" % type, employee["email"], "good")
                except Exception as e:
                    print(e)

    if not active and id_match:
        # delete employee
        print("deactivate %s %s" % (account_type, employee["email"]))
        netsuite_employee_request(employee, account_type, "inactive")
        notifyTechOpsChannel("HRIS - Netsuite %s deactivated" % type, employee["email"], "danger")

def get_netsuite_entities(type):
    netsuite_entities = (make_netsuite_request("GET", None, {"type":type}))["search_details"]
    for entity in netsuite_entities:
        entity["email"] = entity["email"].split("@")[0].lower() if "email" in entity else None
        entity["internalid"] = int(entity["internalid"])
    return netsuite_entities

def netsuite_org_request(org, action, type):
    parent = "15" if type == "department" else "114"
    requestType = None
    if action == "add":
        requestType = "POST"
        body = [
            {
                "action": action,
                "type": type,
                "name": org["name"],
                "parent": parent,
                "custbody_acs_projtype": ""
            }
        ]
    else:
        requestType = "PUT"
        body = [
            {
                "action": action,
                "type": type,
                "name": org["name"],
                "id": org[strings.DB_NS_ORG_COL],
                "parent": parent,
                "custbody_acs_projtype": ""
            }
        ]
    return make_netsuite_request(requestType, body, None)

def netsuite_employee_request(employee, type, action):
    key = strings.DB_NS_EMPLOYEE_COL if type == "employee" else strings.DB_NS_VENDOR_COL
    request_type = "POST"
    email = employee["email"] if "@" in employee["email"] else "%s@safe.com" % employee["email"]
    obj = [{
        "type": type,
        "action": action,
        "isperson":"T",
        "firstname": employee["first"],
        "lastname": employee["last"],
        "email": email,
        "title": employee["title"],
        "custbody_acs_projtype":  5
    }]
    if type == "employee":
        obj[0]["issalesrep"] = employee["issalesrep"]
        # obj[0]["supervisor"] = employee["supervisor"]
        obj[0]["department"] = employee["division_id"]
        obj[0]["custentity_safe_sw_team"] = employee["team_id"]

    if type == "vendor":
        obj[0]["category"] = 5
        
    if action != "add":
        request_type = "PUT"
        obj[0]["id"] = employee[key]
    make_netsuite_request(request_type, obj, None)

def get_orgs(db, level):
    orgs = get_orgs_from_db(db, level)
    for org in orgs: 
        org["name"] = org["alt_name"] if org["alt_name"] else org["name"]
        org[strings.DB_NS_ORG_COL] = int(org[strings.DB_NS_ORG_COL]) if org[strings.DB_NS_ORG_COL] else org[strings.DB_NS_ORG_COL]
    return orgs

def get_employees(db):
    employees = get_employees_from_db(db)

    for employee in employees:
        employee["issalesrep"] = True if "sales" in employee["division_name"].lower() else False
        employee[strings.DB_NS_EMPLOYEE_COL] = int(employee[strings.DB_NS_EMPLOYEE_COL]) if employee[strings.DB_NS_EMPLOYEE_COL] else employee[strings.DB_NS_EMPLOYEE_COL]
        employee[strings.DB_NS_VENDOR_COL] = int(employee[strings.DB_NS_VENDOR_COL]) if employee[strings.DB_NS_VENDOR_COL] else employee[strings.DB_NS_VENDOR_COL]
        employee["team_id"] = int(employee["team_id"]) if employee["team_id"] else employee["team_id"]
        employee["division_id"] = int(employee["division_id"]) if employee["division_id"] else employee["division_id"]
        # we don't want legal department in netsuite, should map to corporate
        if "Legal" in employee["division_name"]:
            employee["division_id"] = 2
        employee["email"] = employee["email"].lower() if employee["email"] else None
        employee["supervisor"] = get_supervisor(employee)


    return employees

def get_supervisor(employee):
    employee["supervisor"] = None
    if employee["team_lead"] != employee[strings.DB_NS_EMPLOYEE_COL]:
        employee["supervisor"] = employee["team_lead"]

    if employee["supervisor"] == None and employee["department_lead"] != employee[strings.DB_NS_EMPLOYEE_COL]:
        employee["supervisor"] = employee["department_lead"]

    if employee["supervisor"] == None and employee["division_lead"] != employee[strings.DB_NS_EMPLOYEE_COL]:
        employee["supervisor"] = employee["division_lead"]

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

def notifyTechOpsChannel(title, message, type):
    obj = {
        "attachments": [{
            "title": title,
            "text": message,
            "color": type
        }]
    }

    requests.post(strings.TECHOPS_AUTOMATION_SLACK_WEBHOOK,json=obj)