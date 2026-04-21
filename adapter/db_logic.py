import datetime
import PyPDF2
import os
import pyodbc
import shutil
import csv
from robot.api import logger
DB_CONFIG = {
    "server": "ITLSQLOTHERSCONS\ITLSQL65",
    "database": "UIPath_Param",
    "trusted": "yes"
}
def get_db_connection():
    drivers = ["{ODBC Driver 17 for SQL Server}", "{SQL Server Native Client 11.0}", "{SQL Server}"]
    for driver in drivers:
        try:
            conn_str = f"DRIVER={driver};SERVER={DB_CONFIG['server']};DATABASE={DB_CONFIG['database']};Trusted_Connection={DB_CONFIG['trusted']};"
            conn = pyodbc.connect(conn_str, timeout=5)
            return conn
        except pyodbc.Error:
            continue
    raise ConnectionError(f"Could not connect to {DB_CONFIG['server']}.")
def get_current_employee_data():
    logger.console("[DB HELPER] Checking for pending records (Status 0)...")
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FilePath' AND ID_Process = 'RPA'")
        fp_param = cursor.fetchone()
        base_filepath = str(fp_param[0]).strip() if fp_param else r"\\EURO1\SAO\Systems\RPA\RPA0009"
        cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FileLog' AND ID_Process = 'RPA'")
        fl_param = cursor.fetchone()
        file_log_name = str(fl_param[0]).strip() if fl_param else "LogEventosSenior.csv"
        old_log_path = os.path.join(base_filepath, file_log_name)
        if os.path.exists(old_log_path):
            os.remove(old_log_path)
            logger.console("[DB HELPER] Deleted old LogEventosSenior.csv")
        cursor.execute(
            "SELECT TOP 1 Registration, Employee_Name, Company, Package, Start_Date, End_Date, Email FROM tb_RPA0009 WHERE Status = 0 ORDER BY ID_Lines ASC")
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FileListName' AND ID_Process = 'RPA'")
            flist_param = cursor.fetchone()
            file_list_name = str(flist_param[0]).strip() if flist_param else "ListaFuncionarios.csv"
            csv_path = os.path.join(base_filepath, file_list_name)
            if os.path.exists(csv_path):
                logger.console("[DB HELPER] No DB records found. Reading CSV to populate database...")
                with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
                if lines:
                    first_line = lines[0].strip().split(';')
                    month_num = int(first_line[0])
                    year_num = int(first_line[1])
                    package = f"{year_num}_{month_num:02d}"
                    initial_year = year_num - 1 if month_num == 1 else year_num
                    cursor.execute("SELECT TOP 1 1 FROM tb_RPA0009 WHERE Package = ?", (package,))
                    if cursor.fetchone():
                        logger.error("[DB HELPER] Package already processed.")
                        return {"found": False, "error": "already_processed"}
                    cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'MONTH' AND ID_Process = 'RPA'")
                    month_param = cursor.fetchone()
                    month_val = str(month_param[0]) if month_param else "2625"
                    day_start = month_val[0:2]
                    day_end = month_val[2:4]
                    prev_month = 12 if month_num == 1 else month_num - 1
                    db_start_date = f"{initial_year}-{prev_month:02d}-{day_start}"
                    db_end_date = f"{year_num}-{month_num:02d}-{day_end}"
                    logger.console(f"[DB HELPER] Formatted SQL Dates - Start: {db_start_date}, End: {db_end_date}")
                    pkg_folder = os.path.join(base_filepath, package)
                    if not os.path.exists(pkg_folder):
                        os.makedirs(pkg_folder)
                    shutil.copy(csv_path, os.path.join(pkg_folder, file_list_name))
                    for line in lines[1:]:
                        clean_line = line.strip()
                        if not clean_line:
                            continue
                        csv_row = clean_line.split(';')
                        if len(csv_row) >= 5:
                            raw_reg = str(csv_row[0]).split('.')[0].strip()
                            email = str(csv_row[1]).strip()
                            emp_name = str(csv_row[3]).strip()
                            company = str(csv_row[4]).strip()
                            if raw_reg.isdigit() or raw_reg != "":
                                cursor.execute("""
                                    INSERT INTO tb_RPA0009 
                                    (Status, Registration, Email, Creation_Date, Employee_Name, Company, Package, Start_Date, End_Date)
                                    VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (raw_reg, email, datetime.datetime.now(), emp_name, company, package,
                                      db_start_date, db_end_date))
                    conn.commit()
                    logger.console("[DB HELPER] CSV data inserted into DB. Awaiting processing.")
                    cursor.execute(
                        "SELECT TOP 1 Registration, Employee_Name, Company, Package, Start_Date, End_Date, Email FROM tb_RPA0009 WHERE Status = 0 ORDER BY ID_Lines ASC")
                    row = cursor.fetchone()
            else:
                logger.error("[DB HELPER] CSV file not found at expected path.")
                return {"found": False, "error": "csv_missing"}
        if row:
            clean_reg = str(row[0]).split('.')[0].strip()
            name = str(row[1]).strip()
            company = str(row[2]).strip()
            email = str(row[6]).strip()
            if not email:
                update_transaction_status(clean_reg, 1, "Número de matrícula não encontrado na lista de funcionários")
                return get_current_employee_data()  # Skip to next
            elif not name:
                update_transaction_status(clean_reg, 1, "Nome do funcionário não encontrado na lista de funcionários")
                return get_current_employee_data()  # Skip to next
            elif not company:
                update_transaction_status(clean_reg, 1, "Número de empresa não encontrada na lista de funcionários")
                return get_current_employee_data()  # Skip to next
            def to_senior_fmt(d):
                if isinstance(d, (datetime.date, datetime.datetime)):
                    return d.strftime("%d%m%Y")
                clean = str(d).split(' ')[0].replace('-', '')
                if len(clean) == 8:
                    return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
                return clean
            data = {
                "registration": clean_reg,
                "name": name,
                "company": company,
                "package": str(row[3]).strip(),
                "start_date": to_senior_fmt(row[4]),
                "end_date": to_senior_fmt(row[5]),
                "email": email,
                "found": True
            }
            return data
        return {"found": False}
    except Exception as e:
        logger.error(f"[DB HELPER] Error in get_current_employee_data: {e}")
        return {"found": False}
    finally:
        if conn: conn.close()
def encrypt_downloaded_pdf(pdf_path, password):
    """
    Step 7.2.2.2.12.3: Encrypts the PDF using the Registration as password.
    """
    try:
        if not os.path.exists(pdf_path):
            print(f"File not found: {pdf_path}")
            return False
        output_path = pdf_path.replace('.pdf', '_temp.pdf')
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            writer = PyPDF2.PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(str(password))
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
        os.replace(output_path, pdf_path)
        return True
    except Exception as e:
        print(f"Encryption failed: {e}")
        return False
def generate_dynamic_filename(employee_name, package):
    timestamp = datetime.datetime.now().strftime("%H%M%S")
    return f"Voith_FolhaPonto_{employee_name.replace(' ', '_')}_{package}_{timestamp}"
def update_transaction_status(registration, status, message):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now()
        clean_reg = str(registration).split('.')[0].strip()
        cursor.execute(
            "UPDATE tb_RPA0009 SET Status = ?, Log_Message = ?, Matching_Date = ? WHERE Registration = ? AND Status = 0",
            (status, message, now, clean_reg))
        conn.commit()
    finally:
        if conn: conn.close()
def generate_process_log():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today = datetime.datetime.now()
        package = f"{today.year}_{today.month:02d}"
        cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FilePath' AND ID_Process = 'RPA'")
        fp_row = cursor.fetchone()
        file_path = str(fp_row[0]).strip() if fp_row else r"C:\TEMP\RPA\RPA0009"
        cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FileLog' AND ID_Process = 'RPA'")
        fl_row = cursor.fetchone()
        file_log = str(fl_row[0]).strip() if fl_row else "LogEventosSenior.csv"
        target_folder = os.path.join(file_path, package)
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        full_log_path = os.path.join(target_folder, file_log)
        cursor.execute("SELECT * FROM tb_RPA0009 WHERE Package = ?", (package,))
        rows = cursor.fetchall()
        headers = [column[0] for column in cursor.description]
        with open(full_log_path, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        return full_log_path
    except Exception as e:
        raise
    finally:
        if conn:
            conn.close()