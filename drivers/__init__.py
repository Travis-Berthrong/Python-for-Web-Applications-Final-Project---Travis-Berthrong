from flask import Blueprint

drivers = Blueprint('drivers', __name__, template_folder='templates')

from . import views