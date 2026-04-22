*** Settings ***
Resource    flows/flows.robot
Library     adapter/Library/RobotProcessLibrary.py

*** Tasks ***
Senior Main Task
    # Initialize Robot Process
    Senior employee timesheet data flow
    # End Robot Process