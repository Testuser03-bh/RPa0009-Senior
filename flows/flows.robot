*** Settings ***
Resource    ../domain/senior.robot

*** Keywords ***
Senior employee timesheet data flow
    Clean up
    Open Senior Application
    Login Senior
    Validate Employee Data
    Send Email Final Report
    Clean up