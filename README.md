# hris_automation

Overview: 

UKG is set to send a daily csv report on current org structure and employee email to hrisautomation@safe.com (group)

A filter is set up to star these emails, apply a "UKGAutomatedReport" label and star it

An app script (HRISGmailToDriveAppScript) runs daily to look for starred emails with the "UKGAutomatedReport" label. The script will then save the attachment in the email

UkgImport.fmw which currently lives in set-fmeserver runs daily to read the latest org and employee csv files from "HRISAutomation/UKG Automated Reports" folder and migrate the data into set-rds user.ukg_org and user.ukg_employee tables.

To update and deploy lambda function:

Requirements: AWS CLI and SAM CLI configured
sam build && sam deploy

To set up the App Script: 
1) Go to https://script.google.com/home
2) Select New Project
3) Copy and paste the script "HRISGmailToDriveAppScript" found in this repo
4) Hit save
5) Select "Triggers" (the alarm clock icon) from the left side menu
6) Select "Add Trigger"
7) Create trigger with following values:
Choose which function to run: main
Which runs at deployment: Head
Select event source: Time-driven
Select type of time based trigger: Day timer
Select time of day: 11pm to midnight
8) In Gmail, create a label named "UKGAutomatedReport"
9) Create a filter with the following search criteria, select the "Star it" option and apply the "UKGAutomatedReport" label
To: hrisautomation@safe.com
Subject: UKG Automation