# WGU D385 Task 1 — Student 9925673

Start with Report_9925673.docx or Report_9925673.pdf. Both contain the application screenshot and four passing-test screenshots. The revised application and 30 executed tests are in application/; original materials remain in the source archive, and supplied historical logs/reports are retained in application/ for comparison.

## Open in Visual Studio Code

This cloud machine has no VS Code desktop or `code` command. On your own machine, extract this submission and open WGU-Rental.code-workspace using File → Open Workspace from File. Alternatively run `code WGU-Rental.code-workspace` if the command is installed. Install the Microsoft Python extension and choose the virtual environment interpreter created below. The screenshots supplied here show actual browser and pytest execution, not an IDE session.

## Install and run

Python 3.12 was used for validation. From the application folder:

```sh
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. Then run:

```sh
python -m pip install -r requirements.txt
python app_student.py
```

Visit the local application in a browser on port 5000. The rental calculator runs immediately. The server is a local development server with debugging disabled. It does not persist rental orders.

The optional demo login is disabled unless a password hash is configured. To enable it for a local demonstration, stop the server with Ctrl+C and run:

```sh
python launch_demo.py
```

Enter a temporary password at the hidden prompt (12–256 characters). Use the username admin, alice, bob, or charlie with that password. The password is not written to source or logs. Login only demonstrates validation and redirects; it does not create an authorized session. For process configuration alternatives, see RENTAL_PASSWORD_HASH and FLASK_SECRET_KEY in app_student.py. Never put actual secret values in a submission. The random default signing key changes on restart.

The automatically generated file is application/Troubleshooting_9925673.log. A snapshot from the executed tests is included. Running more tests or requests appends records. The file uses UTC timestamps; it rolls over at 1 MB and retains three backups. Bootstrap assets and their MIT license are bundled in static/vendor/ so styling works without a CDN. Stock photos on the home page still require the external image host.

## Reproduce validation

From application/ with the virtual environment active:

```sh
python -m pytest test_run.py -v
python -m pip install -r requirements-dev.txt
python -m pytest test_run.py -v --junitxml=../evidence/test_results.xml --html=../evidence/all_tests.html --self-contained-html
python -m flake8 app_student.py
python -m bandit app_student.py
```

Expected: 30 passed, Flake8 exit 0, and Bandit exit 1 with two reviewed B101 assertion warnings. Do not interpret the Bandit exit status as a clean security scan. Assertions are required by the assignment, and explicit validation continues to work with `python -O`. The full-suite test output records an optimized-mode check. These tests are real assertions, replacing the starter's empty student-test placeholders.

The four individually captured tests are:

- test_invalid_equipment_type_handled
- test_non_numeric_days_handled
- test_negative_days_rejected
- test_student_correct_output

Run one with `python -m pytest test_run.py::test_invalid_equipment_type_handled -v`. Individual HTML reports, screenshots, and actual stdout are under evidence/. The application screenshot is evidence/00_application_running.png. All screenshot filenames match their figure descriptions in the report.

For the exact cloud tool versions, requirements-lock.txt records the full installed package set. It includes evidence-generation tools beyond normal application needs. Use `python -m pip install -r requirements-lock.txt` to reproduce that set on a compatible Python 3.12 system.

## Limits

The student must still open the workspace in their local VS Code if an IDE demonstration is required. The demonstration is not a production rental or identity system: it lacks authorization, CSRF controls, rate limiting, durable rental storage, and production server/TLS configuration. External-network warnings are monitoring signals and do not block addresses. No claims of successful SQL injection, actual hostile traffic, or database failures are made from the illustrative starter logs.
