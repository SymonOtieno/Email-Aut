from flask import Flask, render_template, request, redirect, url_for, send_file, session
import os,psycopg2
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import csv
from datetime import datetime
from flask import jsonify
import json


app = Flask(__name__)
app.config['SECRET_KEY'] = 'fgrhsw9912djjk'
# Create SMTP server object
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('symon7672@gmail.com', 'dqtxhtyklwchzrgn')

# DB Connection
def get_db_connection():
    conn = psycopg2.connect(host='localhost',
                            database='email_automation',
                            user=os.environ['DB_USERNAME'],
                            password=os.environ['DB_PASSWORD'])
    return conn
# Login endpoint
@app.route("/")
def home():
    return render_template('login.html')

# Custom Jinja filter for formatting timestamp
def format_timestamp(timestamp):
    return datetime.strftime(timestamp, '%Y-%m-%d %H:%M:%S')

app.jinja_env.filters['format_timestamp'] = format_timestamp

# Login Handler
@app.route("/", methods=['GET', 'POST'])
def login():
    conn = get_db_connection()
    cur = conn.cursor()
    cur2 = conn.cursor()
    
    templ = conn.cursor()
    reports = conn.cursor()
    error = None
    if request.method == 'POST':
        templ.execute("SELECT * FROM templates WHERE is_deleted = FALSE")
        templates = []
        for template in templ:
            templates.append({'service': template[1], 'salutation': template[2], 'heading': template[3], 
                            'message': template[4],'endtag': template[5]})

        reports.execute("SELECT * FROM email_report")
        email_report = []
        for report in reports:
            email_report.append({'recipient': report[1], 'subject': report[2], 'timestamp': report[3], 'service':report[4]})

        cur.execute("SELECT * FROM email_listing WHERE is_deleted = FALSE")
        records = []
        for record in cur:
            records.append({'id': record[0], 'email': record[1], 'service': record[2]})
        
        cur.execute("SELECT * FROM email_listing WHERE is_deleted = TRUE")
        deleted_records = []
        for deleted in cur:
            deleted_records.append({'id': deleted[0], 'email': deleted[1], 'service': deleted[2]})

        username = request.form['username']
        passwd = request.form['password']

        cur.execute("SELECT * FROM logins WHERE username='" + username + "' and password='" + passwd + "'")
        data = cur.fetchone()
        if data is None:
            return "Username or Password wrong"
        else:
            return render_template("index.html", records=records, deleted_records=deleted_records, templates=templates, email_report=email_report, username=username)

# Send Route
@app.route('/send', methods=['POST'])
def send():
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor()
        templ = conn.cursor()

        recipients = request.form.getlist('recipients')
        subject = request.form['subject']
        service = request.form['service']
        message = request.form['message-body']

        # Subject Update
        # Update the existing record
        update_query = "UPDATE templates SET heading = %s, message = %s WHERE service = %s"
        update_values = (subject, message, service)
        cur.execute(update_query, update_values)
        conn.commit()

        print(f"Recipients==> {recipients}")

         #Drop SMS service data
        # Use the DELETE statement to delete data from the database table
        delete_query = "UPDATE email_listing SET is_deleted = TRUE WHERE service = %s"
        delete_value = (service, )
        cur.execute(delete_query, delete_value)
        conn.commit()

        # Update the email_listings database
        elements = recipients[0].split('\r\n')
        

        for email in elements:
            clean_data = email.strip()
            if clean_data:
                data = [(email,service)]
                query = "INSERT INTO email_listing (email, service) VALUES (%s, %s)"
                cur.executemany(query, data)

                # Commit the changes to the database
                conn.commit()
            else:
                print("Data is empty after cleaning")

        query = ("SELECT * FROM templates WHERE service = %s AND is_deleted = FALSE")
        params = (service,)
        cur.execute(query, params)
        records = []
        for template in cur:
            records.append({'service': template[1], 'salutation': template[2], 'heading': template[3], 
                        'message': template[4],'endtag': template[5]})
        
        html_content = render_template("template.html",records=records)

        query = ("SELECT email FROM email_listing WHERE service = %s AND is_deleted = FALSE")
        params = (service,)
        cur.execute(query, params)
        records = cur.fetchall()
        for record in records:
            query = ("INSERT INTO email_report (recipient, subject, service) VALUES (%s, %s, %s)")
            # the message to be emailed
            message = html_content
            email_subject = "Service Downtime"
            email_body = message

            msg = MIMEMultipart('alternative')
            msg['Subject'] = email_subject
            mt_html = MIMEText(email_body, 'html')
            msg.attach(mt_html)
            
            # Load the image file
            with open('static/images/mfs-tech-logo-2.png', 'rb') as img_file:
                # Create an image MIME attachment
                mt_image = MIMEImage(img_file.read())
                mt_image.add_header('Content-ID', '<logo>')
                msg.attach(mt_image)

            # sending the email
            server.sendmail("symon7672@gmail.com", [record[0]], msg.as_string())

            # Define the values to be inserted
            values = (record[0], email_subject,service)
            # Execute the query with the provided values
            cur.execute(query, values)
            # Commit the changes to the database
            conn.commit()

            # close the smtp server
            #server.close()
    return render_template('success.html')

@app.route('/download_data')
def download_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM email_report")
    data = cur.fetchall()

    # Generate a CSV file
    filename = "email_report.csv"
    with open(filename, 'w', newline='') as file:
        writer = csv.writer(file)
        headers = [i[0] for i in cur.description]
        writer.writerow(headers)
        writer.writerows(data)

    # Send the file for download
    return send_file(filename, as_attachment=True)

@app.route('/services')
def get_services():
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT DISTINCT service FROM email_listing WHERE is_deleted = FALSE"
    cur.execute(query)
    services = [service[0] for service in cur.fetchall()]
    return jsonify(services)

@app.route('/email_template', methods=['POST'])
def get_email_template():
    service = request.form['service']
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT heading, message FROM templates WHERE service = %s AND is_deleted = FALSE"
    cur.execute(query, (service,))
    result = cur.fetchone()
    if result:
        subject, message = result
    else:
        subject, message = "", ""
    return jsonify({"subject": subject, "message": message})


@app.route('/data')
def get_data():
    conn = get_db_connection()
    cur = conn.cursor()
    # Fetch service name and emails from the database
    cur.execute("SELECT  service, email FROM email_listing WHERE is_deleted = FALSE")
    data = cur.fetchall()
    print(data)
    return jsonify(data)

# Route to handle the POST request for saving the new client
@app.route('/save_client', methods=['POST'])
def save_client():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        data = request.get_json()
        email = data.get('email')
        service = data.get('service')

        query = "SELECT email, service FROM email_listing WHERE email = %s AND is_deleted = FALSE"
        cur.execute(query, (service,))
        existing_mail = cur.fetchone()

        if existing_mail:
            print("Mail Exists")

        else:
            data = [(email,service)]
            query = "INSERT INTO email_listing (email, service) VALUES (%s, %s)"
            cur.executemany(query, data)

        # Commit the changes to the database
        conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Route to handle the POST request for deleting the new client
@app.route('/delete_client', methods=['POST'])
def delete_client():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        data = request.get_json()
        email = data.get('email')
        service = data.get('service')

        delete_query = "UPDATE email_listing SET is_deleted = TRUE WHERE email = %s"
        delete_value = (email, )
        cur.execute(delete_query, delete_value)

        # Commit the changes to the database
        conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
# Route to handle the POST request for saving the new client
@app.route('/save_template', methods=['POST'])
def save_template():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        data = request.get_json()
        service = data.get('service')
        salutation = data.get('salutation')
        heading = data.get('heading')
        message = data.get('message')
        endtag = data.get('endtag')
        values = (service, salutation, heading, message, endtag)

        print(f"Template Values ==> {values}")

        query = "SELECT service FROM templates WHERE service = %s AND is_deleted = FALSE"
        cur.execute(query, (service,))
        existing_template = cur.fetchone()

        if existing_template:
            print("Template Exists")
        else:
            query = "INSERT INTO templates (service, salutation, heading, message, endtag) VALUES (%s, %s, %s, %s, %s)"
            cur.execute(query, values)

        # Commit the changes to the database
        conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        print("Error:", e)  # Print the error for debugging
        return jsonify({'success': False, 'error': str(e)})

# Route to handle the POST request for deleting the new client
@app.route('/delete_template', methods=['POST'])
def delete_template():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        data = request.get_json()
        service = data.get('service')

        delete_query = "UPDATE templates SET is_deleted = TRUE WHERE service = %s"
        delete_value = (service, )
        cur.execute(delete_query, delete_value)

        # Commit the changes to the database
        conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})