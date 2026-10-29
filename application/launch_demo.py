"""Enable the local demo login without storing or printing a password."""
from getpass import getpass
import os

from werkzeug.security import generate_password_hash

if __name__ == '__main__':
    password = getpass('Choose a temporary demo password (12+ characters): ')
    if not 12 <= len(password) <= 256:
        raise SystemExit('Use 12 to 256 characters.')
    os.environ['RENTAL_PASSWORD_HASH'] = generate_password_hash(password)
    del password
    from app_student import app
    app.run(debug=False, host='127.0.0.1', port=5000)
