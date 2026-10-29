"""Regression tests for rental validation, output, logging and demo login."""
import json
import logging
import subprocess
import sys

import pytest
from werkzeug.security import generate_password_hash

from app_student import (
    LOG_PATH, EQUIPMENT_PRICES, app, calculate_rental_cost,
    logger, validate_username,
)


@pytest.fixture
def client():
    app.config.update(TESTING=True, PASSWORD_HASH=None)
    with app.test_client() as client:
        yield client


def flush_log():
    for handler in logger.handlers:
        handler.flush()
    return LOG_PATH.read_text(encoding='utf-8')


def test_invalid_equipment_type_handled(client):
    response = client.post('/rent', data={
        'equipment_type': 'SpaceShuttle', 'days': '3',
    })
    assert response.status_code == 200
    assert b'Please choose available equipment.' in response.data
    assert b'Rental Confirmation' not in response.data
    assert '"event": "unknown_equipment"' in flush_log()
    print('Unknown equipment: HTTP 200, helpful error, no confirmation; ERROR logged.')


def test_non_numeric_days_handled(client):
    response = client.post('/rent', data={
        'equipment_type': 'Bulldozer', 'days': 'abc',
    })
    assert response.status_code == 200
    assert b'Rental days must be an integer from 1 to 365.' in response.data
    assert b'Rental Confirmation' not in response.data
    assert '"event": "invalid_rental_days"' in flush_log()
    print('Non-numeric days: HTTP 200, helpful error, no confirmation; WARNING logged.')


def test_negative_days_rejected(client):
    response = client.post('/rent', data={
        'equipment_type': 'Bulldozer', 'days': '-5',
    })
    assert response.status_code == 200
    assert b'Rental days must be an integer from 1 to 365.' in response.data
    assert b'-2500' not in response.data
    assert b'Rental Confirmation' not in response.data
    print('Negative duration: -5 rejected; no negative $2500 total or confirmation.')


def test_student_input_validation():
    assert validate_username('admin') is True
    assert validate_username('alice') is True
    for invalid in ('hacker', '', None, [], 123, ' admin ', 'a' * 100):
        assert validate_username(invalid) is False


def test_student_correct_output(client):
    response = client.post('/rent', data={
        'equipment_type': 'Bulldozer', 'days': '3',
    })
    assert response.status_code == 200
    assert b'Rental Confirmation' in response.data
    assert b'Duration: 3 days' in response.data
    assert b'Total Cost: $1500' in response.data
    text = flush_log()
    assert 'verified_positive_integer_rate' in text
    assert 'verified_positive_total' in text
    print('Bulldozer: $500 x 3 days = $1500; both invariant assertions logged at INFO.')


def test_student_application_behavior(client):
    assert client.get('/').status_code == 200
    app.config['PASSWORD_HASH'] = generate_password_hash('test-only-password')
    response = client.post('/login', data={
        'username': 'admin', 'password': 'test-only-password',
    })
    assert response.status_code == 302
    assert response.location.endswith('/')
    response = client.post('/login', data={
        'username': 'admin', 'password': 'wrong',
    }, follow_redirects=True)
    assert b'Invalid credentials.' in response.data
    assert 'test-only-password' not in flush_log()


@pytest.mark.parametrize('days', ['', None, '0', '-1', '366', '999999',
                                  '1.5', ' 3', '1e2', '\u0663'])
def test_invalid_duration_boundaries(client, days):
    data = {'equipment_type': 'Crane'}
    if days is not None:
        data['days'] = days
    response = client.post('/rent', data=data)
    assert response.status_code == 200
    assert b'Rental Confirmation' not in response.data
    assert b'Rental days must be an integer from 1 to 365.' in response.data


@pytest.mark.parametrize('equipment,days,total', [
    ('Excavator', '5', 2250), ('Crane', '2', 1600),
    ('Bulldozer', '1', 500), ('Bulldozer', '365', 182500),
])
def test_calculation_boundaries(equipment, days, total):
    assert calculate_rental_cost(equipment, days)['total_cost'] == total


def test_missing_equipment(client):
    response = client.post('/rent', data={'days': '3'})
    assert response.status_code == 200
    assert b'Please choose available equipment.' in response.data


def test_login_disabled_without_secret(client):
    response = client.post('/login', data={
        'username': 'admin', 'password': 'secret123',
    })
    assert response.status_code == 503
    assert b'Demo login is not configured.' in response.data


def test_external_address_warning(client):
    response = client.get('/', environ_overrides={'REMOTE_ADDR': '203.0.113.45'})
    assert response.status_code == 200
    text = flush_log()
    assert '"event": "untrusted_network"' in text
    assert '"ip": "203.0.113.45"' in text


def test_invalid_address_rejected(client):
    response = client.get('/', environ_overrides={'REMOTE_ADDR': 'not-an-ip'})
    assert response.status_code == 400


def test_forwarded_header_not_trusted(client):
    before = LOG_PATH.stat().st_size
    response = client.get('/', headers={'X-Forwarded-For': '203.0.113.45'})
    assert response.status_code == 200
    assert 'untrusted_network' not in flush_log()[before:]


def test_logs_are_structured_and_injection_safe(client):
    start = LOG_PATH.stat().st_size
    client.post('/rent', data={'equipment_type': 'bad\nFORGED', 'days': '3'})
    lines = flush_log()[start:].splitlines()
    records = [json.loads(line.split(' - ', 2)[2]) for line in lines]
    rejected = [record for record in records
                if record['event'] == 'unknown_equipment']
    assert len(rejected) == 1
    assert rejected[0]['equipment'] == 'bad\nFORGED'
    assert all('event' in record and 'action' in record for record in records)
    assert any(' - ERROR - ' in line for line in lines)


def test_validation_survives_optimized_python():
    code = '''from app_student import calculate_rental_cost
for days in ('0', '-5', 'abc'):
    try:
        calculate_rental_cost('Bulldozer', days)
    except ValueError:
        continue
    raise SystemExit('Invalid duration was accepted')
print('optimized validation passed')
'''
    result = subprocess.run([sys.executable, '-O', '-c', code],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'optimized validation passed' in result.stdout


def test_get_forms_and_security_headers(client):
    for path in ('/', '/rent', '/login'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        assert response.headers['X-Frame-Options'] == 'DENY'


def test_request_size_limit(client):
    response = client.post('/rent', data={'days': 'x' * 17000})
    assert response.status_code == 413


def test_log_levels_and_assertion_records(client):
    start = LOG_PATH.stat().st_size
    client.post('/rent', data={'equipment_type': 'Crane', 'days': '2'})
    client.post('/rent', data={'equipment_type': 'Crane', 'days': 'abc'})
    client.post('/rent', data={'equipment_type': 'Unknown', 'days': '2'})
    lines = flush_log()[start:].splitlines()
    assert any(' - WARNING - ' in line and 'invalid_rental_days' in line
               for line in lines)
    assert any(' - ERROR - ' in line and 'unknown_equipment' in line
               for line in lines)
    successes = [line for line in lines
                 if ' - INFO - ' in line and 'assertion_passed' in line]
    assert len(successes) == 2
    assert EQUIPMENT_PRICES['Crane'] == 800
    assert logger.level == logging.INFO
