import uuid
from collections import defaultdict
from datetime import datetime
from random import random
from flask import Flask, request, render_template, redirect, session, url_for, flash
from flask_mail import Mail,Message
import json, os,random,smtplib
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from pyexpat.errors import messages
from pygments.lexer import default
from werkzeug.security import  generate_password_hash,check_password_hash
#from pyngrok import  ngrok
from zmq.backend.select import public_api

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # For session

load_dotenv()
# Mail config for Gmail SMTP
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')  # NOT your Gmail password

mail=Mail(app)

#DATA_DIR = 'data'
#DATA_DIR = os.getenv('DATA_DIR')
#TRANSACTION_CATEGORY_FILE=os.path.join(DATA_DIR, 'transaction_category.json')
TRANSACTION_CATEGORY_FILE=os.getenv('TRANSACTION_CATEGORY_FILE')
#USERS_FILE = os.path.join(DATA_DIR, 'users.json')
USERS_FILE = os.getenv('USERS_FILE')
#TRANSACTIONS_DIR = os.path.join(DATA_DIR, 'transactions')
TRANSACTIONS_DIR = os.getenv('TRANSACTIONS_DIR')

os.makedirs(TRANSACTIONS_DIR, exist_ok=True)

def send_otp_email(to_email, otp):
    msg = Message("Your OTP Code", sender=app.config['MAIL_USERNAME'], recipients=[to_email])
    msg.body = f"Your OTP for login is: {otp}"
    mail.send(msg)

def load_users():
    if not os.path.exists(USERS_FILE): return []
    with open(USERS_FILE, 'r') as f: return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f: json.dump(users, f, indent=2)

@app.route('/')
def index():
    if 'user' in session:
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        password = request.form['password']
        hashed_password=generate_password_hash(password)
        email=request.form['email']
        if any(u['username'] == username for u in users):
            return "User exists"
        users.append({'uid':str(uuid.uuid4()),'username': username, 'password': hashed_password ,'email':email})
        save_users(users)
        os.makedirs(TRANSACTIONS_DIR, exist_ok=True)
        with open(os.path.join(TRANSACTIONS_DIR, f"{username}.json"), 'w') as f:
            json.dump([], f)
        return redirect('/')
    return render_template('register.html')

@app.route('/login', methods=['POST'])
def login():
    #show_otp=False
    #if request.method=='POST':
    users = load_users()
    action=request.form['action']
    username = request.form['username']
    password = request.form['password']
    user = next((u for u in users if u['username'] == username), None)
    #email=request.form['email']
    #user = next((u for u in users if u['username'] == username and u['password'] == password), None)
    #user = next((u for u in users if u['uid'] == user_id), None)
    #if action=='send-otp':

    if user and check_password_hash(user['password'],password):
        otp=str(random.randint(100000,999999))
        email=user['email']
        session['otp']=otp
        session['email']=email
        session['user'] = username
        send_otp_email(email,otp)
        return redirect(url_for('verify_otp'))
    else:
        flash("Email not registered", "danger")
    #elif action=='verify-otp':

        #return redirect(url_for('verify_otp'))
        #show_otp=True

            #return redirect(url_for('verify_otp'))
        #elif action=='verify-otp':
            #input_otp = request.form['otp']
            #otp = session.get('otp')
            #show_otp = True
            #if input_otp == otp:
                #return redirect(url_for('dashboard'))


    return redirect('/')

@app.route('/verifyotp',methods=['GET', 'POST'])
def verify_otp():
    if 'user' not in session:
        return redirect('/')
    if request.method=='POST':
        input_otp=request.form['otp']
        otp=session.get('otp')
        if input_otp==otp:
            return redirect(url_for('dashboard'))
        return render_template('verifyotp.html',message="Incorrect OTP!")
    return render_template('verifyotp.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect('/')
    with open(TRANSACTION_CATEGORY_FILE, 'r') as f:
        data = json.load(f)
    transaction_category_list = data.get("transaction_category", [])
    username = session['user']
    filepath = os.path.join(TRANSACTIONS_DIR, f"{username}.json")
    if request.method == 'POST':
        amount_str = request.form.get('amount')
        selected_transaction_type=request.form.get('transaction_type')
        selected_transaction_category=request.form.get('transaction_category')
        new_txn = {
            'tid':str(uuid.uuid4()),
            'date': request.form['date'],
            'transaction_type':selected_transaction_type,
            'transaction_category':selected_transaction_category,
            'amount': amount_str,
            'note': request.form['note']
        }
        with open(filepath, 'r') as f:
            txns = json.load(f)
        txns.append(new_txn)
        with open(filepath, 'w') as f:
            json.dump(txns, f, indent=2)
    with open(filepath, 'r') as f:
        txns = json.load(f)
    return render_template('dashboard.html', txns=txns,transaction_categories=transaction_category_list)

@app.route('/viewdetails',methods=['GET', 'POST'])
def view_details():
    if 'user' not in session:
        return redirect('/')
    username = session['user']
    filepath = os.path.join(TRANSACTIONS_DIR, f"{username}.json")
    with open(filepath, 'r') as f:
        txns = json.load(f)
    monthly_totals_income = defaultdict(float)
    monthly_totals_expense = defaultdict(float)
    daily_totals_expense = defaultdict(float)
    for txn in txns:
         # month_key = datetime.strptime(txn['date'], '%Y-%m-%d').strftime('%Y-%m')
        month_key = datetime.strptime(txn['date'], '%Y-%m-%d').strftime('%b')
        date_key = datetime.strptime(txn['date'], '%Y-%m-%d').strftime('%b-%d')
        if txn['transaction_type'] == "income":
            monthly_totals_income[month_key] += float(txn['amount'])
        elif txn['transaction_type'] == "expense":
            monthly_totals_expense[month_key] += float(txn['amount'])
            daily_totals_expense[date_key] += float(txn['amount'])
    monthly_totals_income = dict(monthly_totals_income)
    monthly_totals_expense = dict(monthly_totals_expense)
    daily_totals_expense = dict(daily_totals_expense)
    return render_template('viewdetails.html', txns=txns, monthly_totals_income=monthly_totals_income,monthly_totals_expense=monthly_totals_expense,daily_totals_expense=daily_totals_expense)


@app.route('/delete/<txn_id>', methods=['POST'])
def delete_transaction(txn_id):
    if 'user' not in session:
        return redirect('/')
    username = session['user']
    filepath = os.path.join(TRANSACTIONS_DIR, f"{username}.json")
    with open(filepath, 'r') as f:
        txns = json.load(f)
    txns = [t for t in txns if t['tid'] != txn_id]
    with open(filepath, 'w') as f:
        json.dump(txns, f, indent=2)
    return redirect('/viewdetails')


@app.route('/edit/<txn_id>', methods=['GET', 'POST'])
def edit_transaction(txn_id):
    if 'user' not in session:
        return redirect('/')
    username = session['user']
    filepath = os.path.join(TRANSACTIONS_DIR, f"{username}.json")
    with open(filepath, 'r') as f:
        txns = json.load(f)
    transaction_types = [
            {'value': 'income', 'label': 'Income'},
            {'value': 'expense', 'label': 'Expense'}
    ]
    with open(TRANSACTION_CATEGORY_FILE, 'r') as f:
        data = json.load(f)
    transaction_category_list = data.get("transaction_category", [])
    selected_transaction_type = request.form.get('transaction_type')
    selected_transaction_category=request.form.get('transaction_category')

    txn = next((t for t in txns if t['tid'] == txn_id), None)
    if not txn:
        return "Transaction not found", 404

    if request.method == 'POST':
        txn['date'] = request.form['date']
        txn['amount'] = request.form['amount']
        txn['note'] = request.form['note']
        txn['transaction_type']=selected_transaction_type
        txn['transaction_category']=selected_transaction_category
        with open(filepath, 'w') as f:
            json.dump(txns, f, indent=2)
        return redirect('/viewdetails')

    return render_template('edit.html', txn=txn,transactions=transaction_types,transaction_categories=transaction_category_list)

@app.route('/resetpassword', methods=['GET','POST'])
def reset_password():
    if request.method == 'POST':
        users=load_users()
        u_name = request.form['username']
        newpassword = request.form['newpassword']
        confirmnewpassword = request.form['confirmnewpassword']
        hashednewpassword=generate_password_hash(confirmnewpassword)
        user = next((u for u in users if u['username'] == u_name), None)
        if not user:
            flash("User does not exist")
            return redirect('/resetpassword')

            #return "User does not exist",404

    #if request.method == 'POST':
        if confirmnewpassword == newpassword:
            user['username']=u_name
            user['password']=hashednewpassword
            save_users(users)
            return redirect('/')
        return render_template('resetpassword.html',message="Passwords do not match!")
    return render_template('resetpassword.html')



@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    #ngrok.set_auth_token(os.getenv("NGROK_AUTH_TOKEN"))

    #public_url=ngrok.connect(5000)
    #print("* Ngrok URL:",public_url)
    app.run(host='0.0.0.0',port=5000,debug=True)