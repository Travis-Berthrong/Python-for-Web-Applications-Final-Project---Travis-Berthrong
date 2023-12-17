import sqlite3
from flask import g, render_template, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from . import authentication

login_manager = LoginManager()
login_manager.login_view = "authentication.login"
login_manager.login_message = 'Please log in to access this page.'

@authentication.record_once
def on_load(state):
    login_manager.init_app(state.app)

class User(UserMixin):
    def __init__(self, id, username, password, email, is_driver=False):
        self.id = id
        self.username = username
        self.password = password
        self.email = email
        self.is_driver = is_driver

@login_manager.user_loader
def load_user(user_id):
    """
    This function loads a user given their user_id. It checks if the user is a driver or a client and fetches the user from the appropriate table.
    """
    db = get_db()
    cursor = db.cursor()
    is_driver = session.get('is_driver', False)
    if is_driver:
        cursor.execute(f'SELECT * FROM drivers WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if user:
            return User(user[0], user[1], user[2], user[3], is_driver=True)
    else:
        cursor.execute(f'SELECT * FROM clients WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if user:
            return User(user[0], user[1], user[2], user[3])
    return None

def get_db():
    """
    This function gets the database connection. If the connection does not exist, it creates one and also creates the clients and drivers tables.
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('./uber_application.db')
        create_clients_table(db)
        create_drivers_table(db)
    return db

def create_clients_table(db):
    """
    This function creates the clients table in the database if it does not exist.
    """
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, username TEXT, password TEXT, email TEXT)') 
    db.commit()
    cursor.close()

def create_drivers_table(db):
    """
    This function creates the drivers table in the database if it does not exist.
    """
    cursor = db.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS drivers (id INTEGER PRIMARY KEY, username TEXT, password TEXT, email TEXT, first_name TEXT, last_name TEXT, phone_number TEXT, vehicle TEXT, license_plate TEXT)')
    db.commit()
    cursor.close()

def unique_username(form, field):
    """
    This function checks if the username is unique across both the clients and drivers tables.
    If the username already exists, it raises a ValidationError.
    """
    db = get_db()
    cursor = db.cursor()
    cursor.execute(f'SELECT * FROM clients WHERE username = ?', (field.data,))
    current_user1 = cursor.fetchone()
    cursor.execute(f'SELECT * FROM drivers WHERE username = ?', (field.data,))
    current_user2 = cursor.fetchone()
    if current_user1 or current_user2:
        raise ValidationError('Username already exists')
    
def unique_email(form, field):
    """
    This function checks if the email is unique across either the clients or drivers table, depending on the form.
    If the email already exists, it raises a ValidationError.
    """
    # check if request originated from client or driver sign up form
    is_driver = form.vehicle.data is not None

    db = get_db()
    cursor = db.cursor()
    if is_driver:
        cursor.execute(f'SELECT * FROM drivers WHERE email = ?', (field.data,))
        current_user = cursor.fetchone()
    else:
        cursor.execute(f'SELECT * FROM clients WHERE email = ?', (field.data,))
        current_user = cursor.fetchone()
    if current_user:
        raise ValidationError('Account already exists')

class ClientRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4, max=20)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(min=4, max=20)])
    submit = SubmitField('Sign Up')

class DriverRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=1, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4, max=20)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(min=4, max=20)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=20)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=2, max=20)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=8, max=20)])
    vehicle = SelectField('Vehicle', choices=[('car', 'Car'), ('van', 'Van'), ('horse', 'Horse-drawn carriage')])
    license_plate = StringField('License Plate', validators=[DataRequired(), Length(min=4, max=20)])
    submit = SubmitField('Sign Up')
    
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4, max=20)])
    submit = SubmitField('Login')

@authentication.route('/login', methods=['GET', 'POST'])
def login():
    """
    Route: /login
    Methods: GET, POST
    This route first displays two buttons, one for logging in as a client and one for logging in as a driver.
    When the user clicks on one of the buttons, the login form for that type of user is displayed.
    If the form is valid, the user is logged in and redirected to the home page.
    """
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.driver_home'))
        return redirect(url_for('clients.home'))
    return render_template('login.html')

@authentication.route('/login/client', methods=['GET', 'POST'])
def client_login():
    """
    Route for client login. If the client is already logged in, they are redirected to the home page.
    If the form is submitted and the username and password match a record in the database, the client is logged in and redirected to the home page.
    If the username and password do not match, an error message is flashed.
    """
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.driver_home'))
        return redirect(url_for('clients.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM clients WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            user_obj = User(user[0], user[1], user[2], user[3])
            session['is_driver'] = False
            login_user(user_obj)
            return redirect(url_for('clients.home'))
        else:
            flash('Invalid username or password', 'danger')
    return render_template('client_login.html', form=form)


@authentication.route('/login/driver', methods=['GET', 'POST'])
def driver_login():
    """
    Route for driver login. If the driver is already logged in, they are redirected to the home page.
    If the form is submitted and the username and password match a record in the database, the driver is logged in and redirected to the home page.
    If the username and password do not match, an error message is flashed.
    """
    if current_user.is_authenticated:
        if current_user.is_driver:
            return redirect(url_for('drivers.driver_home'))
        return redirect(url_for('clients.home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM drivers WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
        if user:
            print(user)
            user_obj = User(user[0], user[1], user[2], user[3], is_driver=True)
            session['is_driver'] = True
            login_user(user_obj)
            return redirect(url_for('drivers.driver_home'))
        else:
            flash('Invalid username or password', 'danger')
        cursor.close()
    return render_template('driver_login.html', form=form)

@authentication.route('/sign_up/client', methods=['GET', 'POST'])
def client_sign_up():
    """
    Route for client sign up. If the form is submitted and the username does not already exist in the database,
    a new client is created and the user is redirected to the login page.
    If the username already exists, an error message is flashed.
    """
    form = ClientRegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        email = form.email.data
        
        db = get_db()
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
    """
    Route for driver sign up. If the form is submitted and the username does not already exist in the database,
    a new driver is created and the user is redirected to the login page.
    If the username already exists, an error message is flashed.
    """
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
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM drivers WHERE username = ?', (username,))
        current_user = cursor.fetchone()
        if current_user:
            flash('User already exists', 'danger')
        else:
            cursor.execute('INSERT INTO drivers (username, password, email, first_name, last_name, phone_number, vehicle, license_plate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (username, password, email, first_name, last_name, phone_number, vehicle, license_plate))
            db.commit()
            cursor.close()
            flash('User added successfully', 'success')
            return redirect(url_for('authentication.driver_login'))
    return render_template('driver_sign_up.html', form=form)

@authentication.route('/logout')
@login_required
def logout():
    """
    Route: /logout
    Requires login
    This route logs the user out and redirects them to the home page.
    """
    session.pop('is_driver', None)
    logout_user()
    return redirect(url_for('authentication.login'))