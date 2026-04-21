*** Settings ***
Library    RPA.Desktop
Library    Process
Library    OperatingSystem
Library    DateTime
Library    Collections
Library    String
Library    RPA.Email.ImapSmtp
Library    dotenv
Library    ../adapter/db_logic.py
Resource   ../data/locators.resource
Library    ../adapter/Library/InitAllSettingsSQL.py

*** Variables ***
${PRIMARY_PROCESS_NAME}      RPA0009
${SECONDARY_PROCESS_NAME}      RPA
${primary_config}
${secondary_config}

*** Keywords ***
Open Senior Application
    Load Dotenv     .env
    ${primary_fetched_config}=    Get All Settings    ${PRIMARY_PROCESS_NAME}
    ${secondary_fetched_config}=    Get All Settings    ${SECONDARY_PROCESS_NAME}
    Set Global Variable    ${primary_config}    ${primary_fetched_config}
    Set Global Variable    ${secondary_config}    ${secondary_fetched_config}
    Run Process    powershell    -Command    Start-Process explorer.exe "shell:::{2559a1f3-21d7-11d4-bdaf-00c04f60b9f0}"
    Wait For Element    ${run}    timeout=10
    RPA.Desktop.Press Keys    ctrl    a
    RPA.Desktop.Press Keys    delete
    RPA.Desktop.Type Text    ${primary_config['Senior_Path_Exe']}
    RPA.Desktop.Press Keys    enter
    Wait For Element    ${senior}    timeout=100
    Move Mouse    ${senior}
    Click    ${senior}
Login Senior
    Wait For Element    ${user}    timeout=10
    Move Mouse    ${user}
    Click    ${user}
    ${user}=        Evaluate        "${primary_config['Senior_User']}".split("_")[0].strip()
    RPA.Desktop.Type Text         ${user}
    Wait For Element    ${password}    timeout=10
    Move Mouse    ${password}
    Click    ${password}
    Evaluate                __import__('dotenv').load_dotenv(".env")
    ${pass}=    Get Environment Variable    PASSWORD
    RPA.Desktop.Type Text    ${pass}
    RPA.Desktop.Press Keys    enter
Validate Employee Data
    Wait For Element    ${homepage}    timeout=100
    Move Mouse      ${homepage}
    Click       ${homepage}
    Authorize SMTP    account=${primary_config['Email_SenderAddress']}    password=${EMPTY}    smtp_server=${secondary_config['SMTP_Server']}    smtp_port=${secondary_config['SMTP_Port']}
    ${responsible_list}=    Split String    ${primary_config['Email_Responsible']}    ;
    Wait For Element    ${fav}    timeout=10
    Click    ${fav}
    Wait For Element    ${cartao}    timeout=10
    Click    ${cartao}
    Wait For Element    ${model}    timeout=50
    RPA.Desktop.Type Text    V
    WHILE    True
        ${emp}=    Get Current Employee Data
        ${error_flag}=    Evaluate    $emp.get('error', '')
        IF    '${error_flag}' == 'csv_missing'
            Send Message    sender=${primary_config['Email_SenderAddress']}    recipients=${responsible_list}    subject=${primary_config['Email_Subject_Error_01']}    body=${primary_config['Email_Body_Error_01']}
            BREAK
        ELSE IF    '${error_flag}' == 'already_processed'
            Send Message    sender=${primary_config['Email_SenderAddress']}    recipients=${responsible_list}    subject=${primary_config['Email_Subject_Error_01']}    body=${primary_config['Email_Body_Error_04']}
            BREAK
        END
        IF    ${emp['found']} == False
            Log To Console    No more pending records found. Finished.
            BREAK
        END
        Wait For Element    ${model_voith}    timeout=10
        Click    ${model_voith}
        RPA.Desktop.Press Keys    enter
        Log To Console    Voith model selected, entering loop...
        Log To Console    Processing Employee: ${emp['name']} (Registration: ${emp['registration']})
        Wait For Element    ${entrada}    timeout=100
        Wait For Element    ${initial}    timeout=10
        Click    ${initial}
        RPA.Desktop.Type Text    ${emp['start_date']}
        Wait For Element    ${final}    timeout=10
        Click    ${final}
        RPA.Desktop.Type Text    ${emp['end_date']}
        Wait For Element    ${colaborador}    timeout=10
        Click    ${colaborador}
        RPA.Desktop.Press Keys    end
        WHILE    True
            ${field_is_blank}=    Run Keyword And Return Status    Wait For Element    ${blank}    timeout=0.01
            IF    ${field_is_blank}    BREAK
            RPA.Desktop.Press Keys    backspace
        END
        RPA.Desktop.Type Text    ${emp['registration']}
        Wait For Element    ${ok}    timeout=10
        Click    ${ok}
        ${report_generated}=    Run Keyword And Return Status    Wait For Element    ${result}    timeout=30
        IF    not ${report_generated}
            Update Transaction Status    ${emp['registration']}    1    Error generating report in Senior
            RPA.Desktop.Press Keys    enter
            Log To Console    Error caught for ${emp['registration']}, skipping...
            CONTINUE
        END
        Log To Console    Timesheet generated successfully.
        Wait For Element    ${save}    timeout=10
        Click    ${save}
        Wait For Element    ${save_as}    timeout=10
        ${pdf_filename}=    Generate Dynamic Filename    ${emp['name']}    ${emp['package']}
        RPA.Desktop.Type Text    ${pdf_filename}
        Wait For Element    ${select_pdf}    timeout=10
        Move Mouse    ${select_pdf}
        Click    ${select_pdf_blue}
        Wait For Element    ${option_pdf}    timeout=10
        Move Mouse    ${option_pdf}
        RPA.Desktop.Press Keys    enter
        Wait For Element    ${save_button}    timeout=10
        Move Mouse      ${save_button}
        Click    ${save_button_blue}
        ${temp_path}=        Set Variable    ${primary_config['Path_Temp']}
        ${full_pdf_path}=    Set Variable    ${temp_path}\\${pdf_filename}.pdf
        Encrypt Downloaded Pdf    ${full_pdf_path}    ${emp['registration']}
        ${is_voith}=    Evaluate    "${emp['email']}".lower().endswith("@voith.com")
        ${active_smtp}=    Set Variable If    ${is_voith}    ${secondary_config['SMTP_Server']}    ${secondary_config['SMTP_Server_Out']}
        Authorize SMTP    account=${primary_config['Email_SenderAddress']}    password=${EMPTY}    smtp_server=${active_smtp}    smtp_port=${secondary_config['SMTP_Port']}
        ${email_body}=    Get File    ../data/body.html
        ${email_status}=    Run Keyword And Return Status    Send Message    sender=${primary_config['Email_SenderAddress']}    recipients=${emp['email']}    subject=Ponto ${emp['month']}/${emp['year']}    body=${email_body}    html=True    attachments=${full_pdf_path}
        IF    ${email_status}
            Update Transaction Status    ${emp['registration']}    2    E-mail enviado com sucesso
            ${final_folder}=    Set Variable    ${primary_config['FilePath']}\\${emp['package']}
            Copy File    ${full_pdf_path}    ${final_folder}\\${pdf_filename}.pdf
            Remove File  ${full_pdf_path}
            Log To Console    File copied and removed from temp.
        ELSE
            Update Transaction Status    ${emp['registration']}    1    Error to send e-mail
        END
        Wait For Element    ${close_pdf}    timeout=10
        Click    ${close_pdf}
        Log To Console    Moving to next employee...
    END
    # BUG 18 FIX: Soft Close Senior
    # 1. Handle Model Closure
    ${model_visible}=    Run Keyword And Return Status    Wait For Element    ${close_model}    timeout=10
    IF    ${model_visible}
        Click    ${close_model}
        RPA.Desktop.Press Keys    alt    f4
        Log To Console    Model window found and closed via Alt+F4.
    ELSE
        Log To Console    Model window not detected, skipping Alt+F4 for model.
    END
    # 2. Handle Senior Application Closure
    ${senior_visible}=    Run Keyword And Return Status    Wait For Element    ${close_senior}    timeout=10
    IF    ${senior_visible}
        Click    ${close_senior}
        RPA.Desktop.Press Keys    alt    f4
        # Often Senior asks for a final confirmation (Step 10 in your docs)
        RPA.Desktop.Press Keys    enter
        Log To Console    Senior main window found and closed.
    ELSE
        Log To Console    Senior main window not detected.
    END
    Log To Console    Senior Soft Close sequence completed.
Send Email Final Report
    ${log_path}=    Generate Process Log
    Log To Console    Log file ready for attachment: ${log_path}
    ${email_subject}=      Set Variable    ${primary_config['Email_Subject_FinalProcess']} - RPA0009
    ${body_msg}=           Set Variable    ${primary_config['Email_Body_FinalProcess']}
    ${test_recipients}=    Split String    ${primary_config['Email_Responsible_Test']}    ;
    Authorize SMTP    account=${primary_config['Email_SenderAddress']}    password=${EMPTY}    smtp_server=${secondary_config['SMTP_Server']}    smtp_port=${secondary_config['SMTP_Port']}
    TRY
        Send Message    sender=${primary_config['Email_SenderAddress']}    recipients=${test_recipients}    subject=${email_subject}    body=${body_msg}    html=True    attachments=${log_path}
        Log To Console    📧 Report successfully sent with attached log!
    EXCEPT
        Log To Console    Failed to send final report. Sending fallback error email.
        Send Message    sender=${primary_config['Email_SenderAddress']}    recipients=${test_recipients}    subject=${primary_config['Email_Subject_Error_02']}    body=${primary_config['Email_Body_Error_03']} Process Failed
    END