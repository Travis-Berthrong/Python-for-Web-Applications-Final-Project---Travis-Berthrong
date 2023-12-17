import logging
from flask import Flask, flash, redirect, render_template, request, session, jsonify, g, url_for
import folium
from flask_login import login_required, current_user
from flask_mail import Message
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from datetime import datetime
import math
from bson import ObjectId
import sqlite3

from app import mail
from . import clients

load_dotenv()

# Connect to MongoDB database
db = MongoClient(os.getenv('MONGO_URI'))['uber']
active_orders = db['active_orders']

# Set default location
default_location = [os.getenv('DEFAULT_LAT'), os.getenv('DEFAULT_LNG')]

def calculate_distance(origin, destination):
    """
    Calculate the distance between two points on the earth's surface.
    :param origin: tuple of latitude and longitude of the origin point
    :param destination: tuple of latitude and longitude of the destination point
    :return: distance in kilometers
    """
    # Unpack latitude and longitude from the origin and destination
    lat1, lon1 = origin
    lat2, lon2 = destination

    radius = 6371  # Earth's radius in km

    # Calculate the distance between two points on the earth
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = radius * c

    # Add 10% to the distance to account for further distance due to road layout
    distance *= 1.1

    return distance # in km

def calculate_price(distance, vehicle_type):
    """
    Calculate the price of the ride based on the distance and vehicle type.
    :param distance: distance of the ride in kilometers
    :param vehicle_type: type of the vehicle ('car', 'van', 'horse')
    :return: price of the ride
    """
    if vehicle_type == 'car':
        return distance * 0.5
    elif vehicle_type == 'van':
        return distance * 0.75
    elif vehicle_type == 'horse':
        return distance * 1.25

def get_db():
    """
    Get the database connection.
    :return: database connection object
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('uber_application.db')
    return db

def send_email(message_content, message_title):
    """
    Send an email to the current user.
    :param message_content: content of the email
    :param message_title: title of the email
    """
    try:
        msg = Message(message_title, sender='recipe-website@noreply.com', recipients=[current_user.email])
        msg.body = message_content
        mail.send(msg)
        flash(f'Your invoice has been sent to {current_user.email}', 'success')
    except Exception as e:
        flash('There was an error sending your confirmation!', 'danger')
        flash(str(e), 'danger')
        logging.info(f"SMTP Exception: {str(e)}")
        
@clients.route('/home')
@login_required
def home():
    """
    Render the home page.
    """
    client_location = session.get('client_location')
    if not client_location:
        client_location = default_location
        fetched_location = False
    else:
        fetched_location = True
    map = folium.Map(location=client_location, zoom_start=15)
    folium.Marker(client_location, tooltip=f'<strong>Your location</strong><br>{client_location[0]}, {client_location[1]}').add_to(map)
    return render_template('home.html', map=map._repr_html_(), fetched_location=fetched_location, default_location=default_location)

@clients.route('/receive_location', methods=['POST'])
def receive_location():
    """
    This route receives the client's location from the frontend and stores it in the session.
    """
    location = request.get_json()['location']
    session['client_location'] = [location['lat'], location['lng']]
    print(session['client_location'])
    return jsonify({'result': 'success'})

@clients.route('/receive_destination', methods=['POST'])
def receive_destination():
    """
    This route receives the client's destination from the frontend and stores it in the database.
    """
    destination = request.get_json()['destination']
    destination_lat = destination['lat']
    destination_lng = destination['lng']
    obj = active_orders.insert_one({
        'client_id': current_user.id,
        'client_name': current_user.username,
        'driver_id': '',
        'driver_name': '',
        'vehicle_type': '',
        'departure_time': '',
        'number_of_passengers': '',
        'origin': session['client_location'],
        'destination': [destination_lat, destination_lng],
        'distance': calculate_distance(session['client_location'], [float(destination_lat), float(destination_lng)]),
        'price': 0,
        'status': 'waiting',
        'created_at': datetime.now(),
        'completed_at': ''
    })
    return jsonify({'result': 'success', 'id': str(obj.inserted_id)})

@clients.route('/receive_additional_info', methods=['POST'])
def receive_additional_info():
    """
    This route receives additional information about the order from the frontend and updates the order in the database.
    """
    additional_info = request.get_json()['additional_info']
    obj_id = ObjectId(additional_info['obj_id'])
    number_of_passengers = additional_info['number_of_passengers']
    vehicle_type = additional_info['vehicle_type']
    departure_time = additional_info['departure_time']
    order = active_orders.find_one({'_id': obj_id})
    price = calculate_price(order['distance'], vehicle_type)
    active_orders.update_one({'_id': obj_id}, {'$set': {
        'number_of_passengers': number_of_passengers,
        'vehicle_type': vehicle_type,
        'departure_time': departure_time,
        'price': price
    }})
    return jsonify({'result': 'success', 'id': str(obj_id)})

@clients.route('/waiting_page/<order_id>')
@login_required
def waiting_page(order_id):
    """
    This route renders the waiting page for the client.
    """
    order = active_orders.find_one({'_id': ObjectId(order_id)})
    order_origin = order['origin']
    order_destination = order['destination']
    order_vehicle_type = order['vehicle_type']
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM drivers WHERE vehicle = ?", (order_vehicle_type,))
    available_drivers = cur.fetchall()
    print(f"Available drivers: {available_drivers}")
    map = folium.Map(location=order_origin, zoom_start=15)
    folium.Marker(order_origin, tooltip=f'<strong>Origin</strong><br>{order_origin[0]}, {order_origin[1]}').add_to(map)
    folium.Marker(order_destination, tooltip=f'<strong>Destination</strong><br>{order_destination[0]}, {order_destination[1]}').add_to(map)
    return render_template('waiting_page.html', client_id=current_user.id, map=map._repr_html_(), available_drivers=available_drivers, order_id=order_id)

@clients.route('/cancel_order/<str_order_id>')
@login_required
def cancel_order(str_order_id):
    """
    This route cancels the order and redirects the client to the home page.
    """
    obj_id = ObjectId(str_order_id)
    active_orders.delete_one({'_id': obj_id})
    flash('Your order has been cancelled', 'success')
    return redirect(url_for('clients.home'))

@clients.route('/ongoing_ride/<order_id>')
@login_required
def client_ongoing_ride(order_id):
    """
    This route renders the ongoing ride page for the client.
    """
    obj_id = ObjectId(order_id)
    order = active_orders.find_one({'_id': obj_id})
    driver_name = order['driver_name']
    origin = order['origin']
    destination = order['destination']
    distance = order['distance']
    return render_template('client_ongoing_ride.html', driver_name=driver_name, origin=origin, destination=destination, distance=distance, order_id=order_id, client_username=current_user.username)

@clients.route('/ride_invoice/<order_id>')
@login_required
def ride_invoice(order_id):
    """
    This route renders the ride invoice for the client and sends an email with the invoice.
    """
    obj_id = ObjectId(order_id)
    order = active_orders.find_one({'_id': obj_id})
    driver_name = order['driver_name']
    vehicle = order['vehicle_type']
    origin = order['origin']
    destination = order['destination']
    distance = round(order['distance'], 2)
    departure_time = order['departure_time']
    completed_at = order['completed_at']
    price = round(order['price'], 2)
    send_email(f"Your ride from {origin} to {destination} has been completed. Your driver was {driver_name}. The total price was {price}.", "Your ride invoice")
    return render_template('ride_invoice.html', driver_name=driver_name, vehicle=vehicle, origin=origin, destination=destination, distance=distance, price=price, order_id=order_id, client_name=current_user.username, departure_time=departure_time, completed_at=completed_at)
