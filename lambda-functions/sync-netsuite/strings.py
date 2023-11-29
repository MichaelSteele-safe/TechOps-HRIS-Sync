import aws_functions

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
DB_NS_EMPLOYEE_COL = "netsuite_employee_id_sb" if NS_ENV == "Sandbox" else "netsuite_employee_id"
DB_NS_VENDOR_COL = "netsuite_vendor_id_sb" if NS_ENV == "Sandbox" else "netsuite_vendor_id"
DB_NS_ORG_COL = "netsuite_id_sb" if NS_ENV == "Sandbox" else "netsuite_id"
