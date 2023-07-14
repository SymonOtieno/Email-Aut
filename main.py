from flask import Flask, render_template, request, redirect, url_for
import os,psycopg2

app = Flask(__name__)

app = Flask(__name__)
def get_db_connection():
    conn = psycopg2.connect(host='localhost',
                            database='email_automation',
                            user=os.environ['DB_USERNAME'],
                            password=os.environ['DB_PASSWORD'])
    return conn

@app.route('/')
def edit_form():
	

	# Render the HTML template with the data
	return render_template('form.html')

@app.route('/submit', methods=['POST'])
def submit_form():
	# Connect to the database
	conn = get_db_connection()
	cur = conn.cursor()

	# Update data in the database
	for key, value in request.form.items():
		cur.execute("UPDATE books SET title=%s WHERE id=%s", (value, key))
	conn.commit()

	# Redirect back to the edit form
	return redirect('/')
@app.route('/form', methods=['GET', 'POST'])
def form():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Fetch data from the database
    cur.execute("SELECT id, service, salutation, heading, message, endtag FROM sms_template")
    records = cur.fetchall()

    if request.method == 'POST':
        # Process the submitted form data
        for record in records:
            service = record[0]
            salutation = request.form['']

            # Update the records in the database
            #cur.execute("UPDATE users SET name = %s, email = %s WHERE id = %s", (name, email, user_id))
            conn.commit()

    return render_template('form.html', records=records)
