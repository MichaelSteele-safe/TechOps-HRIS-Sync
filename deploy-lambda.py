# Packages the desired lambda function and dependencies, and
# uploads package to AWS.

# usage example: 
# $ python3 aws-lambda-functions/deploy-lambda.py aws-lambda-functions/REL-jira

import os
import sys
import shutil

# get lambda function to update from args
lambda_function = sys.argv[1] 
lambda_function_name = os.path.basename(sys.argv[1])

deploy_directory_name = '%s_deploy' % lambda_function_name
deploy_zip_name = '%s.zip' % deploy_directory_name
# get current working directory
original_path = os.getcwd()
print(original_path)
os.chdir(lambda_function)

# clean up files
print('Getting ready to package dependencies...')

if os.path.isdir(deploy_directory_name):
    print('Removing %s' % deploy_directory_name)
    shutil.rmtree(deploy_directory_name)
if os.path.isfile(deploy_zip_name):
    print('Removing %s' % deploy_zip_name)
    os.remove(deploy_zip_name)
if os.path.isdir('./__pycache__'):
    print('Removing ./__pycache__')
    shutil.rmtree('./__pycache__')

# copy over all files to deploy directory
print('Copy all files to a deploy directory')
os.system('cp -r . ../%s' % deploy_directory_name)

# install dependencies to deploy directory
print('Checking for dependencies in requirements.txt ...')
if os.path.isfile('./requirements.txt'):
    print('Installing dependencies into package directory ...')
    os.system('pip3 install --target ../%s -r ./requirements.txt' % deploy_directory_name)

# zip up deploy directory
os.chdir("../%s" % deploy_directory_name)
os.system('zip -r %s ./*' % deploy_zip_name)

# upload deployment package to lambda
print('Uploading deployment package to lambda ...')
os.system(f'aws lambda update-function-code --function-name {lambda_function_name} --zip-file fileb://{deploy_zip_name}')

os.chdir("..")
print(os.getcwd())
# clean up files after deployment
print('Cleaning up files ...')
if os.path.isdir('./%s' % deploy_directory_name):
    print('Removing ./%s directory' % deploy_directory_name)
    shutil.rmtree('./%s' % deploy_directory_name)

# return to CWD
os.chdir(original_path)
