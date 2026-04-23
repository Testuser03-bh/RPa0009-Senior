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
        base_filepath = str(fp_param[0]).strip() if fp_param else r"C:\\Temp\\RPA0009"
        
        cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FileLog' AND ID_Process = 'RPA'")
        fl_param = cursor.fetchone()
        file_log_name = str(fl_param[0]).strip() if fl_param else "LogEventosSenior.csv"
        
        # Step 4: Delete old log file from BASE path (not package path)
        old_log_path = os.path.join(base_filepath, file_log_name)
        if os.path.exists(old_log_path):
            os.remove(old_log_path)
            logger.console("[DB HELPER] Deleted old LogEventosSenior.csv")
        
        # Step 2: Query for pending records
        cursor.execute(
            "SELECT TOP 1 ID_Lines, Registration, Employee_Name, Company, Package, Start_Date, End_Date, Email FROM tb_RPA0009 WHERE Status = 0 ORDER BY ID_Lines ASC")
        row = cursor.fetchone()
        
        if not row:
            # Step 2.2: No pending records found, check CSV
            cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FileListName' AND ID_Process = 'RPA'")
            flist_param = cursor.fetchone()
            file_list_name = str(flist_param[0]).strip() if flist_param else "ListaFuncionarios.csv"
            
            # Step 2.2.1: Check CSV existence
            # csv_path = r"C:\\TEMP\\RPA0009\\ListaFuncionarios.csv"
            csv_path = r"C:\TEMP\RPA0009\ListaFuncionarios.csv"
            # For testing, you can use: csv_path = r"C:\TEMP\RPA0009\ListaFuncionarios.csv"
            
            if os.path.exists(csv_path):
                logger.console("[DB HELPER] No DB records found. Reading CSV to populate database...")
                
                # Step 2.2.1.1.1: Read CSV content
                with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                    lines = f.readlines()
                
                if lines:
                    # Step 2.2.1.1.2: Date transformation
                    first_line = lines[0].strip().split(';')
                    month_num = int(first_line[0])
                    year_num = int(first_line[1])
                    package = f"{year_num}_{month_num:02d}"
                    initial_year = year_num - 1 if month_num == 1 else year_num
                    
                    # Step 2.2.1.1.3: Check if package already processed
                    cursor.execute("SELECT TOP 1 1 FROM tb_RPA0009 WHERE Package = ?", (package,))
                    if cursor.fetchone():
                        logger.error("[DB HELPER] Package already processed.")
                        return {"found": False, "error": "already_processed"}
                    
                    # Get month-specific date parameters
                    month_key = f"{month_num:02d}"
                    cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = ? AND ID_Process = 'RPA'", (month_key,))
                    month_param = cursor.fetchone()
                    
                    # FIX: Removed duplicate fetchone() and fixed default format
                    month_val = str(month_param[0]) if month_param else "26;02;25;03"
                    
                    # FIX: Added validation before parsing
                    parts = month_val.split(';')
                    if len(parts) >= 4:
                        day_start   = parts[0].strip()
                        month_start = parts[1].strip()
                        day_end     = parts[2].strip()
                        month_end   = parts[3].strip()
                    else:
                        logger.error(f"[DB HELPER] Invalid month parameter format: {month_val}. Using defaults.")
                        day_start, month_start = "26", f"{month_num-1:02d}" if month_num > 1 else "12"
                        day_end, month_end = "25", f"{month_num:02d}"
                    
                    # Step 2.2.1.1.3.1.2.1-2: Format dates for SQL
                    db_start_date = f"{initial_year}-{month_start}-{day_start}"
                    db_end_date   = f"{year_num}-{month_end}-{day_end}"
                    logger.console(f"[DB HELPER] Formatted SQL Dates - Start: {db_start_date}, End: {db_end_date}")
                    
                    # Step 2.2.1.1.3.1.1.1: Create package folder
                    pkg_folder = os.path.join(base_filepath, package)
                    if not os.path.exists(pkg_folder):
                        os.makedirs(pkg_folder)
                    
                    # Step 2.2.1.1.3.1.1.2: Copy CSV to package folder
                    shutil.copy(csv_path, os.path.join(pkg_folder, file_list_name))
                    
                    # Step 2.2.1.1.3.1.2.3-4: Insert each employee record
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
                            
                            # FIX: Improved validation logic
                            if raw_reg and (raw_reg.isdigit() or raw_reg.strip()):
                                cursor.execute("""
                                    INSERT INTO tb_RPA0009 
                                    (Status, Registration, Email, Creation_Date, Employee_Name, Company, Package, Start_Date, End_Date)
                                    VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (raw_reg, email, datetime.datetime.now(), emp_name, company, package,
                                      db_start_date, db_end_date))
                    
                    conn.commit()
                    logger.console("[DB HELPER] CSV data inserted into DB. Awaiting processing.")
                    
                    # Re-query for first record
                    cursor.execute(
                        "SELECT TOP 1 ID_Lines, Registration, Employee_Name, Company, Package, Start_Date, End_Date, Email FROM tb_RPA0009 WHERE Status = 0 ORDER BY ID_Lines ASC")
                    row = cursor.fetchone()
            else:
                logger.error("[DB HELPER] CSV file not found at expected path: " + csv_path)
                return {"found": False, "error": "csv_missing"}
        
        # Step 7: Process the fetched record
        if row:
            id_lines  = str(row[0]).strip()
            clean_reg = str(row[1]).split('.')[0].strip()
            name      = str(row[2]).strip()
            company   = str(row[3]).strip()
            package   = str(row[4]).strip()  # FIX: Changed from row[3] to row[4]
            start_date = row[5]
            end_date   = row[6]
            email     = str(row[7]).strip()
            
            # Step 7.1-7.2.2.1: Validation checks
            # FIX: Changed from clean_reg to id_lines in all update calls
            if not clean_reg:
                update_transaction_status(id_lines, 1, "Número de matrícula não encontrado na lista de funcionários")
                return get_current_employee_data()
            elif not name:
                update_transaction_status(id_lines, 1, "Nome do funcionário não encontrado na lista de funcionários")
                return get_current_employee_data()
            elif not company:
                update_transaction_status(id_lines, 1, "Número de empresa não encontrada na lista de funcionários")
                return get_current_employee_data()
            
            # Date formatting for Senior application (DDMMYYYY format)
            def to_senior_fmt(d):
                if isinstance(d, (datetime.date, datetime.datetime)):
                    return d.strftime("%d%m%Y")
                clean = str(d).split(' ')[0].replace('-', '')
                if len(clean) == 8:
                    return f"{clean[6:8]}{clean[4:6]}{clean[0:4]}"
                return clean
            
            # FIX: Extract month/year from package (index 4, not 3)
            pkg_parts = package.split('_')
            
            data = {
                "id_lines": id_lines,
                "registration": clean_reg,
                "name": name,
                "company": company,
                "package": package,  # Already extracted correctly above
                "start_date": to_senior_fmt(start_date),
                "end_date": to_senior_fmt(end_date),
                "month": pkg_parts[1] if len(pkg_parts) > 1 else "",
                "year":  pkg_parts[0] if len(pkg_parts) > 0 else "",
                "email": email,
                "found": True
            }
            return data
        
        return {"found": False}
        
    except Exception as e:
        logger.error(f"[DB HELPER] Error in get_current_employee_data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"found": False}
    finally:
        if conn: 
            conn.close()

def encrypt_downloaded_pdf(pdf_path, password):
    """
    Step 7.2.2.2.12.3: Encrypts the PDF using the Registration as password.
    """
    import time
    time.sleep(1)  # Wait for PDF to finish writing
    
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
            
            writer.encrypt(user_password=str(password), owner_password=str(password), permissions_flag=-1)
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
        
        os.replace(output_path, pdf_path)
        print(f"PDF encrypted successfully: {pdf_path}")
        return True
        
    except Exception as e:
        print(f"Encryption failed: {e}")
        return False
    
def generate_dynamic_filename(employee_name, package):
    """
    Step 7.2.2.2.12.2: Generate filename as per documentation
    Format: Voith_FolhaPonto_EMPLOYEENAME_PACKAGE_HHMMSS
    """
    timestamp = datetime.datetime.now().strftime("%H%M%S")
    clean_name = employee_name.replace(' ', '').upper()
    return f"Voith_FolhaPonto_{clean_name}_{package}_{timestamp}"

def update_transaction_status(id_lines, status, message):
    """
    Update the status of a transaction record
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.datetime.now()
        
        cursor.execute(
            "UPDATE tb_RPA0009 SET Status = ?, Log_Message = ?, Matching_Date = ? WHERE ID_Lines = ?",
            (status, message, now, id_lines))
        conn.commit()
        
        logger.console(f"[DB HELPER] Updated ID {id_lines}: Status={status}, Message={message}")
        
    except Exception as e:
        logger.error(f"[DB HELPER] Error updating status: {e}")
    finally:
        if conn: 
            conn.close()

def generate_process_log():
    """
    Step 11: Generate log CSV file with all processed records
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        today = datetime.datetime.now()
        package = f"{today.year}_{today.month:02d}"
        
        cursor.execute("SELECT Value FROM tb_ProcessConfig WHERE Name = 'FilePath' AND ID_Process = 'RPA'")
        fp_row = cursor.fetchone()
        file_path = str(fp_row[0]).strip() if fp_row else r"C:\TEMP\RPA0009"
        
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
        
        logger.console(f"[DB HELPER] Log file created: {full_log_path}")
        return full_log_path
        
    except Exception as e:
        logger.error(f"[DB HELPER] Error generating log: {e}")
        raise
    finally:
        if conn:
            conn.close()
