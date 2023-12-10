from flask import Blueprint

clients = Blueprint('clients', __name__, template_folder='templates')

from . import views