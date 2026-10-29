"""WGU equipment rental demonstration with defensive validation and audit logs.

Login demonstrates credential checking only. Rental actions are public.
Set RENTAL_PASSWORD_HASH to a Werkzeug scrypt hash to enable the demo login.
"""

import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import secrets
import time

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32),
    PASSWORD_HASH=os.environ.get('RENTAL_PASSWORD_HASH'),
    MAX_CONTENT_LENGTH=16 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

LOG_PATH = Path(__file__).with_name('Troubleshooting_9925673.log')
logger = logging.getLogger('rental.audit')
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = RotatingFileHandler(
        LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding='utf-8'
    )
    formatter = logging.Formatter(
        '%(asctime)sZ - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger.addHandler(handler)

EQUIPMENT_PRICES = {'Bulldozer': 500, 'Excavator': 450, 'Crane': 800}
MAX_RENTAL_DAYS = 365
TRUSTED_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    '127.0.0.0/8', '::1/128', '10.0.0.0/8', '192.168.0.0/16',
))


def audit(level, event, action, **details):
    """JSON-encode fields so untrusted newlines cannot forge log entries."""
    logger.log(level, json.dumps(
        {'event': event, 'action': action, **details}, ensure_ascii=True
    ))


def validate_username(username):
    """Reject wrong types and require an exact, bounded allowlisted name."""
    return (
        isinstance(username, str)
        and 1 <= len(username) <= 32
        and username in {'admin', 'alice', 'bob', 'charlie'}
    )


def calculate_rental_cost(equipment_type, days_str):
    """Raise KeyError for unknown equipment and ValueError for invalid days."""
    daily_rate = EQUIPMENT_PRICES[equipment_type]
    if (not isinstance(days_str, str) or len(days_str) > 3
            or not days_str.isascii() or not days_str.isdecimal()):
        raise ValueError('Rental days must be an integer from 1 to 365.')
    days = int(days_str)
    if not 1 <= days <= MAX_RENTAL_DAYS:
        raise ValueError('Rental days must be an integer from 1 to 365.')

    # Internal invariants: validation above also works under python -O.
    if not isinstance(daily_rate, int) or daily_rate <= 0:
        raise RuntimeError('Invalid equipment pricing configuration.')
    assert isinstance(daily_rate, int) and daily_rate > 0
    audit(logging.INFO, 'assertion_passed', 'verified_positive_integer_rate',
          equipment=equipment_type, rate=daily_rate)
    total_cost = daily_rate * days
    if total_cost <= 0:
        raise RuntimeError('Invalid calculated rental total.')
    assert total_cost > 0
    audit(logging.INFO, 'assertion_passed', 'verified_positive_total',
          total=total_cost)
    return {'equipment': equipment_type, 'days': days,
            'total_cost': total_cost}


@app.before_request
def log_request():
    # Ignore X-Forwarded-For without a configured, trusted reverse proxy.
    address = request.remote_addr
    audit(logging.INFO, 'request_received', 'process_request',
          method=request.method, path=request.path[:128], ip=address)
    try:
        parsed = ipaddress.ip_address(address or '')
    except ValueError:
        audit(logging.WARNING, 'invalid_client_ip', 'reject_request')
        return 'Invalid client address.', 400
    if not any(parsed in network for network in TRUSTED_NETWORKS):
        audit(logging.WARNING, 'untrusted_network', 'observe_request',
              ip=address)
    # Being outside the local networks is a signal, not proof of an attacker.


@app.after_request
def log_response(response):
    audit(logging.INFO, 'request_completed', 'return_response',
          status=response.status_code, path=request.path[:128])
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


@app.route('/')
def home():
    audit(logging.INFO, 'home_accessed', 'render_home')
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password', '')
        allowed = validate_username(username)
        stored_hash = app.config.get('PASSWORD_HASH')
        if not stored_hash:
            audit(logging.WARNING, 'login_disabled', 'reject_login',
                  ip=request.remote_addr)
            flash('Demo login is not configured.', 'warning')
            return render_template('login.html'), 503
        if (allowed and 1 <= len(password) <= 256
                and check_password_hash(stored_hash, password)):
            audit(logging.INFO, 'login_success', 'redirect_home',
                  username=username, ip=request.remote_addr)
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('home'))
        # Do not log passwords or arbitrary submitted usernames.
        audit(logging.WARNING, 'login_failed', 'reject_login',
              ip=request.remote_addr, allowed_username=allowed)
        flash('Invalid credentials.', 'danger')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/rent', methods=['GET', 'POST'])
def rent_equipment():
    rental_result = None
    if request.method == 'POST':
        equipment_type = request.form.get('equipment_type')
        days_str = request.form.get('days')
        try:
            rental_result = calculate_rental_cost(equipment_type, days_str)
        except KeyError:
            audit(logging.ERROR, 'unknown_equipment', 'reject_rental',
                  equipment=(equipment_type or '')[:80],
                  ip=request.remote_addr)
            flash('Please choose available equipment.', 'danger')
        except ValueError:
            audit(logging.WARNING, 'invalid_rental_days', 'reject_rental',
                  days=(days_str or '')[:32], ip=request.remote_addr)
            flash('Rental days must be an integer from 1 to 365.', 'danger')
        else:
            audit(logging.INFO, 'rental_calculated', 'show_confirmation',
                  **rental_result, ip=request.remote_addr)
            flash('Rental calculated successfully!', 'success')
    # Preserve the supplied tests' form redisplay contract (HTTP 200).
    return render_template('rent.html', rental_result=rental_result)


if __name__ == '__main__':
    audit(logging.INFO, 'application_start', 'start_development_server')
    app.run(debug=False, host='127.0.0.1', port=5000)
