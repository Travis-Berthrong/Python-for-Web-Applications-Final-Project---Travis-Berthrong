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

from . import drivers

load_dotenv()

db = MongoClient(os.getenv('MONGO_URI'))['uber']
active_orders = db['active_orders']

default_location = [os.getenv('DEFAULT_LAT'), os.getenv('DEFAULT_LNG')]


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect('uber_application.db')
    return db


@drivers.route('/driver_home')
@login_required
def driver_home():
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT vehicle FROM drivers WHERE id=?', (current_user.id,))
    vehicle_type = cursor.fetchone()[0]

    driver_location = session.get('driver_location')
    if not driver_location:
        sent_location = False
        driver_location = default_location
    else:
        sent_location = True

    map = folium.Map(location=driver_location, zoom_start=15)
    pending_orders = active_orders.find({'status': 'waiting', 'vehicle_type': vehicle_type})
    for order in pending_orders:
        origin = order['origin']
        destination = order['destination']
        distance = order['distance']
        price = order['price']
        id = str(order['_id'])
        #create a marker to display the order details on the map
        order_marker_html = f"""
            <form action='/accept_order' method='POST'>
                <input type='hidden' name='order_id' value='{id}'>
                <strong>Pickup location: </strong>{origin[0]}, {origin[1]}<br>
                <strong>Destination: </strong>{destination[0]}, {destination[1]}<br>
                <strong>Distance: </strong>{round(distance,2)}<br>
                <strong>Price: </strong>{round(price,2)}<br>
                <input type='submit' value='Accept'>
            </form>"""
        marker = folium.Marker(origin, popup=order_marker_html, tooltip='<strong>Awaiting order</strong>')
        marker.add_to(map)

    folium.Marker(driver_location, tooltip=f'<strong>Your location</strong><br>{driver_location[0]},{driver_location[1]}').add_to(map)
    return render_template('driver_home.html', map=map._repr_html_(), sent_location=sent_location, default_location=default_location)

@drivers.route('/receive_location', methods=['POST'])
def receive_location():
    location = request.get_json()['location']
    session['driver_location'] = [location['lat'], location['lng']]
    return jsonify({'result': 'success'})

@drivers.route('/accept_order', methods=['POST'])
def accept_order():
    obj_id = ObjectId(request.form.get('order_id'))
    active_orders.update_one({'_id': obj_id}, {'$set': {
        'driver': current_user.id,
        'status': 'accepted',
    }})
    print('Order accepted')
    return redirect(url_for('drivers.driver_home'))