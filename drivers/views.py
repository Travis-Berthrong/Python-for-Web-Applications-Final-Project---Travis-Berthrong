import datetime
from flask import Flask, render_template, url_for, redirect, request, session, jsonify, g
from flask_socketio import emit, join_room
import folium
from flask_login import login_required, current_user
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from bson import ObjectId
import sqlite3
from folium.elements import JavascriptLink, Element

from . import drivers
from app import socketio

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

    driver_location = session.get('driver_location', None)
    if not driver_location:
        sent_location = False
        driver_location = default_location
    else:
        sent_location = True

    map = folium.Map(location=driver_location, zoom_start=15)
    pending_orders = active_orders.find({'status': 'waiting', 'vehicle_type': vehicle_type})
    num_orders = 0
    for order in pending_orders:
        num_orders += 1
        origin = order['origin']
        destination = order['destination']
        distance = order['distance']
        price = order['price']
        id = str(order['_id'])
        #create a marker to display the order details on the map
        order_marker_html = f"""
            <form action="javascript:;" onsubmit="parent.acceptOrder(\'{id}\')">
                <input type='hidden' name='order_id' value='{id}'>
                <strong>Pickup location: </strong>{origin[0]}, {origin[1]}<br>
                <strong>Destination: </strong>{destination[0]}, {destination[1]}<br>
                <strong>Distance: </strong>{round(distance,2)}<br>
                <strong>Price: </strong>{round(price,2)}<br>
                <input type="submit" value="Accept">
            </form>"""
        marker = folium.Marker(origin, popup=order_marker_html, tooltip='<strong>Awaiting order</strong>')
        marker.add_to(map)

    folium.Marker(driver_location, tooltip=f'<strong>Your location</strong><br>{driver_location[0]},{driver_location[1]}').add_to(map)
    return render_template('driver_home.html', map=map._repr_html_(), sent_location=sent_location, default_location=default_location, driver_name=current_user.username, num_orders=num_orders)

@drivers.route('/receive_driver_location', methods=['POST'])
def receive_driver_location():
    location = request.get_json()['location']
    session['driver_location'] = [location['lat'], location['lng']]
    return jsonify({'result': 'success'})

@drivers.route('/accept_order', methods=['POST'])
def accept_order():
    str_id = request.json.get('order_id')
    obj_id = ObjectId(str_id)
    active_orders.update_one({'_id': obj_id}, {'$set': {
        'driver': current_user.id,
        'driver_name': current_user.username,
        'status': 'accepted',
    }})
    return jsonify({'result': 'success'})

@drivers.route('/driver_ongoing_ride/<order_id>')
@login_required
def driver_ongoing_ride(order_id):
    obj_id = ObjectId(order_id)
    order = active_orders.find_one({'_id': obj_id})
    client_name = order['client_name']
    origin = order['origin']
    destination = order['destination']
    distance = order['distance']
    return render_template('driver_ongoing_ride.html', client_name=client_name, origin=origin, destination=destination, distance=distance, driver_name = current_user.username, order_id=order_id)

@drivers.route('/end_ride', methods=['POST'])
def end_ride():
    str_id = request.get_json()['order_id']
    completion_time = request.get_json()['time']
    obj_id = ObjectId(str_id)
    active_orders.update_one({'_id': obj_id}, {'$set': {
        'status': 'completed',
        'completed_at': completion_time
    }})
    print(f'Order {str_id} completed')
    return jsonify({'result': 'success'})

@drivers.route('/ride_summary/<str_order_id>')
@login_required
def ride_summary(str_order_id):
    obj_id = ObjectId(str_order_id)
    order = active_orders.find_one({'_id': obj_id})
    client_name = order['client_name']
    vehicle = order['vehicle_type']
    origin = order['origin']
    destination = order['destination']
    distance = round(order['distance'], 2)
    departure_time = order['departure_time']
    completed_at = order['completed_at']
    price = round(order['price'], 2)
    return render_template('ride_summary.html', client_name=client_name, origin=origin, destination=destination, distance=distance, price=price, driver_name=current_user.username, vehicle=vehicle, departure_time=departure_time, completed_at=completed_at)