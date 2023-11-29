NS_ENV = "Production"
DB_NS_EMPLOYEE_COL = "netsuite_employee_id_sb" if NS_ENV == "Sandbox" else "netsuite_employee_id"
DB_NS_VENDOR_COL = "netsuite_vendor_id_sb" if NS_ENV == "Sandbox" else "netsuite_vendor_id"
DB_NS_ORG_COL = "netsuite_id_sb" if NS_ENV == "Sandbox" else "netsuite_id"

def add_id_to_db(db, id, identifier, type):
    db_cursor = db.cursor(dictionary=True)
    if type == "team" or type == "department":
        query = """
            UPDATE users.ukg_teams
            SET %s = %s
            WHERE name = "%s"
            and archived is null
            and org_level = %s
        """ % (DB_NS_ORG_COL, id, identifier, 3 if type == "team" else 1)
    if type == "employee":
        query = """
            UPDATE users.ukg_users
            SET %s = %s
            WHERE email ="%s"
        """ % (DB_NS_EMPLOYEE_COL, id, identifier)
    if type == "vendor":
        query = """
            UPDATE users.ukg_users
            SET %s = %s
            WHERE email = "%s"
        """ % (DB_NS_VENDOR_COL, id, identifier)

    db_cursor.execute(query)
    db.commit()
    db_cursor.close()
      
def get_orgs_from_db(db, org_level):
    # don't grab legal
    db_cursor = db.cursor(dictionary=True)
    db_cursor.execute("""
        select name, alt_name, %s, archived
        from users.ukg_teams
        where org_level = %d and name != "Legal" and name!= "Operations" and name != "Balance Sheet"
    """ % (DB_NS_ORG_COL,org_level))
    response = db_cursor.fetchall()
    db_cursor.close()
    return response

def get_employee_count(db):
    db_cursor = db.cursor(dictionary=True)
    db_cursor.execute("""
        SELECT COUNT(*) FROM users.ukg_users
        WHERE netsuite_admin = 0
    """)
    response = db_cursor.fetchall()
    db_cursor.close()
    return response[0]["COUNT(*)"]

def get_employees_from_db(db):
    db_cursor = db.cursor(dictionary=True)
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
            division.name as "division_name",
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
        where u.netsuite_admin != 1 or u.netsuite_admin is null
        order by u.last ASC
        LIMIT 10
    """ % (DB_NS_EMPLOYEE_COL, DB_NS_VENDOR_COL,DB_NS_ORG_COL,DB_NS_EMPLOYEE_COL,DB_NS_ORG_COL,DB_NS_ORG_COL,DB_NS_ORG_COL,DB_NS_ORG_COL,DB_NS_ORG_COL))
    response = db_cursor.fetchall()
    db_cursor.close()

    return response