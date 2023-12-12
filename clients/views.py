from flask import Flask, render_template, url_for, redirect, request, session, jsonify, g
import folium
from flask_login import login_required, current_user
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from datetime import datetime
import math
from bson import ObjectId
import sqlite3

from . import clients

load_dotenv()

db = MongoClient(os.getenv('MONGO_URI'))['uber']
active_orders = db['active_orders']

default_location = [os.getenv('DEFAULT_LAT'), os.getenv('DEFAULT_LNG')]


def calculate_distance(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination

    radius = 6371  # km

    # calculate the distance between two points on the earth
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = radius * c

    # add 10% to the distance to account for further distance due to road layout
    distance *= 1.1

    return distance # in km

def calculate_price(distance, vehicle_type):
    if vehicle_type == 'car':
        return distance * 0.5
    elif vehicle_type == 'van':
        return distance * 0.75
    elif vehicle_type == 'horse':
        return distance * 1.25
    
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('uber_application.db')
    return db

@clients.route('/home')
@login_required
def home():
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
    location = request.get_json()['location']
    session['client_location'] = [location['lat'], location['lng']]
    print(session['client_location'])
    return jsonify({'result': 'success'})

@clients.route('/receive_destination', methods=['POST'])
def receive_destination():
    destination = request.get_json()['destination']
    destination_lat = destination['lat']
    destination_lng = destination['lng']
    obj = active_orders.insert_one({
        'client': current_user.id,
        'driver': '',
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
    return jsonify({'result': 'success'})

@clients.route('/waiting_page')
@login_required
def waiting_page():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM drivers WHERE available = True')
    available_drivers = cursor.fetchall()
    if len(available_drivers) > 0:
        return render_template('waiting_page.html', available_drivers=available_drivers)
    return render_template('waiting_page.html')

    

