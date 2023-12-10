from flask import Flask, render_template, url_for, redirect, request, session, jsonify, g
import folium
from flask_login import login_required, current_user
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from datetime import datetime
import math

from . import clients

load_dotenv()
db = MongoClient(os.getenv('MONGO_URI'))['uber']
active_orders = db['active_orders']


def calculate_distance(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination

    radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
        math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = radius * c

    return distance

@clients.route('/home')
@login_required
def home():
    client_location = session.get('client_location', None)
    if client_location is None:
        client_location = [48.810001, 2.358100]
        fetched_location = False
    else:
        fetched_location = True
    map = folium.Map(location=client_location, zoom_start=15)
    folium.Marker(client_location, tooltip='<strong>Your location</strong>').add_to(map)
    return render_template('home.html', map=map._repr_html_(), fetched_location=fetched_location)

@clients.route('/receive_location', methods=['POST'])
def receive_location():
    location = request.get_json()['location']
    session['client_location'] = [location['lat'], location['lng']]
    print(session['client_location'])
    return jsonify({'result': 'success'})

@clients.route('/client_destination', methods=['POST'])
def client_destination():
    destination_lat = request.form['destination_lat']
    destination_lng = request.form['destination_lng']
    active_orders.insert_one({
        'client': current_user.id,
        'driver': '',
        'destination': [destination_lat, destination_lng],
        'distance': calculate_distance(session['client_location'], [float(destination_lat), float(destination_lng)]),
        'status': 'waiting',
        'created_at': datetime.now(),
        'completed_at': ''
    })
    return redirect(url_for('clients.home'))
    

