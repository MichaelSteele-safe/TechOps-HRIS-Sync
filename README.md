# hris_automation

Overview: 
UKG is set to send a daily report on current org structure and employee email to hrisautomation@safe.com (group)
The attachment is then saved to a Group Google Drive folder, HRISAutomation/UKG Automated Reports using App Scripts (HRISGmailToDriveAppScript)
UkgImport.fmw then reads the latest org and employee csv files from "HRISAutomation/UKG Automated Reports" folder and migrates
data into set-rds user.ukg_org and user.ukg_employee tables.

To set up the App Script: 
1) Go to https://script.google.com/home
2) Select New Project
3) Copy and paste the script "HRISGmailToDriveAppScript" found in this repo
4) Hit save
5) Select "Triggers" (the alarm clock icon) from the left side menu
6) Select "Add Trigger"
7) Create trigger with following values:
Choose which function to run: main
D