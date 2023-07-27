from flask import Flask, render_template, request, redirect, url_for, send_file, session
import os,psycopg2
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import csv
from datetime import datetime
from flask import jsonify


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
        templ.execute("SELECT * FROM templates")
        templates = []
        for template in templ:
            templates.append({'service': template[1], 'salutation': template[2], 'heading': template[3], 
                            'message': template[4],'endtag': template[5]})

        reports.execute("SELECT * FROM email_report")
        email_report = []
        for report in reports:
            email_report.append({'recipient': report[1], 'subject': report[2], 'timestamp': report[3], 'service':report[4]})

        cur2.execute("SELECT * FROM email_listing")
        records = []
        for record in cur2:
            records.append({'id': record[0], 'email': record[1], 'service': record[2]})
        username = request.form['username']
        passwd = request.form['password']

        cur.execute("SELECT * FROM logins WHERE username='" + username + "' and password='" + passwd + "'")
        data = cur.fetchone()
        if data is None:
            return "Username or Password wrong"
        else:
            return render_template("index.html", records=records, templates=templates, email_report=email_report, username=username)

# Template Route
@app.route('/page/<page_name>')
def load_page(page_name):
        selected_value = session.get('selectedValue')
        selected_value = selected_value.upper()
        # Connect to the database
        conn = get_db_connection()
        cur = conn.cursor()
        templ = conn.cursor()

        # Retrieve data from the database
        query = ("SELECT * FROM email_listing WHERE service=%s")
        service = selected_value
        params = (service,)
        cur.execute(query, params)

        query2 = ("SELECT * FROM templates WHERE service=%s")
        service = selected_value
        params = (service,)
        templ.execute(query2, params)

        templates = []
        records = []
        for record in cur:
            records.append({'id': record[0], 'email': record[1], 'service': record[2]})
        for template in templ:
            templates.append({'service': template[1], 'salutation': template[2], 'heading': template[3], 
                            'message': template[4],'endtag': template[5]})
            
        print(templates)
        print(records)
        # Render the HTML template with the data
        return render_template('default.html', records=records, templates=templates)

# Submit Route     
@app.route('/submit', methods=['POST'])
def submit():
    clients = request.form['items']
    session['clients'] = clients

    return redirect(url_for('load_page', clients=clients))

# Send Route
@app.route('/send', methods=['POST'])
def send():
    selected_value = session.get('selectedValue')
    selected_value = selected_value.upper()
    print(selected_value)
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor()
        templ = conn.cursor()

        clients = request.form.getlist('clients')
        subject = request.form['subject']
        message = request.form['message']

        # Subject Update
        # Update the existing record
        update_query = "UPDATE templates SET heading = %s, message = %s WHERE service = %s"
        update_values = (subject, message, selected_value)
        cur.execute(update_query, update_values)
        conn.commit()

        #Drop SMS service data
        # Use the DELETE statement to delete data from the database table
        delete_query = "DELETE FROM email_listing WHERE service = %s"
        delete_value = (selected_value, )
        cur.execute(delete_query, delete_value)
        conn.commit()

        # Update the email_listings database
        elements = eval(clients[0])
        
        for email in elements:
            data = [(email,selected_value)]
            query = "INSERT INTO email_listing (email, service) VALUES (%s, %s)"
            cur.executemany(query, data)

            # Commit the changes to the database
            conn.commit()

        query = ("SELECT * FROM templates WHERE service = %s")
        service = selected_value
        params = (service,)
        cur.execute(query, params)
        records = []
        for template in cur:
            records.append({'service': template[1], 'salutation': template[2], 'heading': template[3], 
                        'message': template[4],'endtag': template[5]})
        
        html_content = render_template("template.html",records=records)

        query = ("SELECT email FROM email_listing WHERE service = %s")
        service = selected_value
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
            with open('static/images/email2.png', 'rb') as img_file:
                # Create an image MIME attachment
                mt_image = MIMEImage(img_file.read())
                mt_image.add_header('Content-ID', '<logo>')
                msg.attach(mt_image)

            # sending the email
            server.sendmail("symon7672@gmail.com", [record[0]], msg.as_string())

            # Define the values to be inserted
            values = (record[0], email_subject,selected_value)
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
    query = "SELECT DISTINCT service FROM email_listing"
    cur.execute(query)
    services = [service[0] for service in cur.fetchall()]
    return jsonify(services)

@app.route('/email_template', methods=['POST'])
def get_email_template():
    service = request.form['service']
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT heading, message FROM templates WHERE service = %s"
    cur.execute(query, (service,))
    result = cur.fetchone()
    if result:
        subject, message = result
    else:
        subject, message = "", ""
    return jsonify({"subject": subject, "message": message})


@app.route('/add_option', methods=['POST'])
def add_option():
    conn = get_db_connection()
    cur = conn.cursor()
    option = request.form['name']
  
    
    query = ("SELECT service FROM templates WHERE service = %s")
    service = option
    params = (service,)
    cur.execute(query, params)
    records = cur.fetchall()

    if(len(records)<1):
        option_lower = option.lower()
        option = [option]
        query = ("INSERT INTO templates (service) VALUES (%s)")
        cur.execute(query, (option[0],))
        query2 = ("INSERT INTO email_listing (service) VALUES (%s)")
        cur.execute(query2, (option[0],))
        conn.commit()
        return jsonify({'message': 'Option added successfully'})
    
    else:
        return jsonify({'message': 'Option Already Exists'})


@app.route('/process_selected_value', methods=['POST'])
def process_selected_value():
    selected_value = request.json['selectedValue']

    session['selectedValue'] = selected_value

    # Return a response if needed
    return jsonify({'message': 'Value received and processed successfully.'})