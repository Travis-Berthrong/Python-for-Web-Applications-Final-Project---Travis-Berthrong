import sqlite3
from flask import g, render_template, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from . import authentication

from final_project.app import app

login_manager = LoginManager()
login_manager.login_view = "authentication.login"
login_manager.login_message = 'Please log in to access this page.'
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, username, password, email, is_driver=False):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.is_driver = is_driver

@login_manager.user_loader
def load_user(user_id, get_db, table):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f'SELECT * FROM {table} WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        if table == 'drivers':
            return User(user[0], user[1], user[2], user[3], is_driver=True)
        return User(user[0], user[1], user[2], user[3])
    else:
        return None

def get_clients_db():
    db = getattr(g, '_clients_database', None)
    if db is None:
        db = g._users_database = sqlite3.connect('./clients.db')
        create_clients_table(db)
    return db

def create_clients_table(db):
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, email TEXT)') 
    db.commit()
    cursor.close()

def get_drivers_db():
    db = getattr(g, '_drivers_database', None)
    if db is None:
        db = g._drivers_database = sqlite3.connect('./drivers.db')
        create_drivers_table(db)
    return db

def create_drivers_table(db):
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS drivers (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, email TEXT, first_name TEXT, last_name TEXT, phone_number TEXT, vehicle TEXT, license_plate TEXT, available BOOLEAN)')


def unique_username(form, field, get_db, table):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f'SELECT * FROM {table} WHERE username = ?', (field.data,))
    current_user = cursor.fetchone()
    if current_user:
        raise ValidationError('Username already exists')
    
def unique_email(form, field, get_db, table):
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f'SELECT * FROM {table} WHERE email = ?', (field.data,))
    current_user = cursor.fetchone()
    if current_user:
        raise ValidationError('Account already exists')

class ClientRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20), unique_username(get_db=get_clients_db, table='clients')])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4, max=20)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(min=4, max=20), unique_email(get_db=get_clients_db, table='clients')])
    submit = SubmitField('Sign Up')

class DriverRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20), unique_username(get_db=get_drivers_db, table='drivers')])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4, max=20)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(min=4, max=20), unique_email(get_db=get_drivers_db, table='drivers')])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=4, max=20)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=4, max=20)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=4, max=20)])
    vehicle = StringField('Vehicle', validators=[DataRequired(), Length(min=4, max=20)])
    license_plate = StringField('License Plate', validators=[DataRequired(), Length(min=4, max=20)])
    submit = SubmitField('Sign Up')
    
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4, max=20)])
    submit = SubmitField('Login')

"""
Route: /login
Methods: GET, POST
This route first displays two buttons, one for logging in as a client and one for logging in as a driver.
When the user clicks on one of the buttons, the login form for that type of user is displayed.
If the form is valid, the user is logged in and redirected to the home page."""
@authentication.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.home'))
        return redirect(url_for('clients.home'))
    return render_template('login.html')

@authentication.route('/login/client', methods=['GET', 'POST'])
def client_login():
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.home'))
        return redirect(url_for('clients.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        db = get_clients_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM clients WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            user_obj = User(user[0], user[1], user[2], user[3])
            login_user(user_obj)
            return redirect(url_for('clients.home'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('client_login.html', form=form)
@authentication.route('/login/driver', methods=['GET', 'POST'])
def driver_login():
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.home'))
        return redirect(url_for('clients.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        db = get_drivers_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM drivers WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            user_obj = User(user[0], user[1], user[2], user[3], is_driver=True)
            login_user(user_obj)
            return redirect(url_for('drivers.home'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('driver_login.html', form=form)

@authentication.route('/sign_up/client', methods=['GET', 'POST'])
def client_sign_up():
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.home'))
        return redirect(url_for('clients.home'))
    
    form = ClientRegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        email = form.email.data
        
        db = get_clients_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM clients WHERE username = ?', (username,))
        current_user = cursor.fetchone()
        if current_user:
            flash('User already exists', 'danger')
        else:
            cursor.execute('INSERT INTO clients (username, password, email) VALUES (?, ?, ?)', (username, password, email))
            db.commit()
            cursor.close()
            flash('User added successfully', 'success')
            return redirect(url_for('authentication.client_login'))
    return render_template('client_sign_up.html', form=form)

@authentication.route('/sign_up/driver', methods=['GET', 'POST'])
def driver_sign_up():
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.home'))
        return redirect(url_for('clients.home'))
    
    form = DriverRegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        email = form.email.data
        first_name = form.first_name.data
        last_name = form.last_name.data
        phone_number = form.phone_number.data
        vehicle = form.vehicle.data
        license_plate = form.license_plate.data
        
        db = get_drivers_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM drivers WHERE username = ?', (username,))
        current_user = cursor.fetchone()
        if current_user:
            flash('User already exists', 'danger')
        else:
            cursor.execute('INSERT INTO drivers (username, password, email, first_name, last_name, phone_number, vehicle, license_plate, available) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', (username, password, email, first_name, last_name, phone_number, vehicle, license_plate, True))
            db.commit()
            cursor.close()
            flash('User added successfully', 'success')
            return redirect(url_for('authentication.driver_login'))
    return render_template('driver_sign_up.html', form=form)

# Route: /logout
# Requires login
# This route logs the user out and redirects them to the home page.
@authentication.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('authentication.login'))