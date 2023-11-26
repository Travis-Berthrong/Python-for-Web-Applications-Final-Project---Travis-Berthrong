from flask import Blueprint
from flask_login import LoginManager

authentication = Blueprint('authentication', __name__, template_folder='templates')

from . import views

    