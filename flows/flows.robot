*** Settings ***
Resource    ../domain/senior.robot

*** Keywords ***
Senior employee timesheet data flow
    Open Senior Application
    Login Senior
    Validate Employee Data
    Send Email Final Report