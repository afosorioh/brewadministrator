# BrewAdministrator

<p align="center">
  <strong>A production-oriented brewery management platform built with Flask and PostgreSQL.</strong>
</p>

<p align="center">
  BrewAdministrator centralizes brewing operations—from recipes and raw-material inventory to batch execution, keg traceability, tastings, customers, and operational analytics.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-supported-4169E1?logo=postgresql&logoColor=white">
  <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-2.x-D71F00?logo=sqlalchemy&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-GPL--3.0-blue">
</p>

## Overview

BrewAdministrator is a web application designed to support the operational lifecycle of a craft brewery. It replaces disconnected spreadsheets and manual records with a centralized system for production planning, inventory control, traceability, quality evaluation, and reusable operational reporting.

The application follows Flask's application-factory pattern and separates routes, services, templates, utilities, database models, and migrations. It is currently used as a real operational platform, which makes the project both a software-engineering portfolio and a domain-specific production system.

## Key modules

### Recipes

Define reusable beer recipes and their required ingredients, quantities, process stages, hop additions, yeast information, and production parameters.

### Raw materials

Manage malt, hops, yeast, and other brewing inputs, including lots, units, available stock, and consumption associated with production batches.

### Production batches

Create and track brewing batches through their operational states. The module records recipe, brew date, target and final volume, original and final gravity, mash temperatures, pH, fermentation measurements, ingredients used, and calculated indicators such as approximate ABV and attenuation.

### Keg lifecycle and traceability

Track individual kegs by code, capacity, filled volume, beer style, batch, customer/location, status, and last movement date. Supported workflows include registration, filling, dispatch, return, washing, maintenance, and decommissioning.

### Keg analytics

Provide an operational dashboard with total inventory, clean, full, delivered, and dirty keg counts. Visualizations group kegs by status and capacity, while filters support date, customer, and beer-style analysis.

### Inventory and catalog integration

Expose product availability for inventory workflows and external consumers, including integration with the brewery's chatbot/catalog services.

### Tastings and quality control

Create tasting sessions linked to production batches and collect structured
quality evaluations through internal or public workflows. Each active session
provides a shareable URL and QR code so participants can open the tasting form
without access to the management portal.

### Customers, users, and authorization

Manage customers and authenticated users with role-based access controls for administrative and operational responsibilities.

### Statistics and reports

Generate production and operational statistics, visual summaries, and PDF exports using Matplotlib and ReportLab.

### Temperature monitoring and control

The temperature module connects Full Gauge MT-512E Log v09 controllers to the
management portal through a Raspberry Pi and an isolated USB–RS-485 adapter.
The field service in [`raspberry_gateway/gateway_mt512e_sitrad_py34.py`](raspberry_gateway/gateway_mt512e_sitrad_py34.py)
communicates directly with the controllers through the validated Sitrad serial
protocol, without requiring Sitrad Pro or a Windows computer.

Current capabilities include:

- Poll multiple controller IDs once per minute over a shared RS-485 bus.
- Read temperature, setpoint, firmware version, sensor status, and refrigeration output.
- Buffer measurements in a local SQLite outbox during Internet or VPS outages.
- Upload idempotent reading batches to the Flask REST API over HTTPS.
- Associate each controller and its historical readings with a production batch.
- Display live status and historical temperature/setpoint charts in local Colombian time.
- Queue remote setpoint changes and verify each write by reading the physical controller back.
- Run continuously as a `systemd` service on an older Raspberry Pi with Python 3.4.2.

## Screenshots

<table>
  <tr>
    <td width="50%">
      <img src="docs/images/batches-list.png" alt="Production batches list"><br>
      <sub><b>Production batches:</b> searchable overview of active and completed brewing batches.</sub>
    </td>
    <td width="50%">
      <img src="docs/images/batch-detail.png" alt="Batch detail and calculated indicators"><br>
      <sub><b>Batch detail:</b> process parameters, measurements, calculated indicators, and raw-material traceability.</sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/images/kegs-list.png" alt="Keg inventory and lifecycle"><br>
      <sub><b>Keg traceability:</b> current status, location, batch, beer style, volume, and latest movement.</sub>
    </td>
    <td width="50%">
      <img src="docs/images/keg-dashboard.png" alt="Keg analytics dashboard"><br>
      <sub><b>Operational analytics:</b> status KPIs, capacity breakdowns, filters, and inventory detail.</sub>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/images/tasting-session.png" alt="Public tasting session with access QR code"><br>
      <sub><b>Tasting sessions:</b> batch information, public access link, QR code, and session activation controls.</sub>
    </td>
    <td width="50%">
      <img src="docs/images/temperature-monitoring.png" alt="Live fermentation temperature monitoring"><br>
      <sub><b>Temperature monitoring:</b> live measurements, batch assignment, refrigeration output, connectivity, and verified setpoint control.</sub>
    </td>
  </tr>
</table>

## Technology stack

| Layer | Technologies |
|---|---|
| Backend | Python, Flask, Flask Blueprints, Jinja2 |
| Data access | SQLAlchemy, Flask-SQLAlchemy |
| Database | PostgreSQL; MySQL driver support |
| Authentication | Flask-Login, role-based authorization |
| Schema evolution | Alembic, Flask-Migrate |
| Reporting and analytics | Matplotlib, NumPy, ReportLab, Pillow |
| Edge and industrial integration | Raspberry Pi, RS-485, PySerial, Sitrad, SQLite outbox, systemd |
| Configuration | python-dotenv |
| Production deployment | Ubuntu, Nginx, Gunicorn |
| Version control | Git, GitHub |

## Application structure

```text
brewadministrator/
├── app/
│   ├── routes/          # Flask blueprints by business module
│   ├── services/        # Security and external integration services
│   ├── static/          # CSS, JavaScript, images, and generated assets
│   ├── templates/       # Jinja2 templates organized by module
│   ├── utils/           # Shared application utilities
│   ├── authz.py         # Authorization helpers
│   ├── extensions.py    # Flask extension instances
│   ├── models.py        # Relational domain model
│   ├── rasp_mt512_v9.py # Raspberry Pi temperature gateway
│   └── __init__.py      # Application factory and blueprint registration
├── migrations/          # Alembic database migrations
├── sql/                 # Supporting SQL scripts
├── requirements.txt
└── run.py
```

## Architecture highlights

- **Modular monolith:** business capabilities are separated into Flask blueprints while sharing a consistent relational domain model.
- **Application factory:** extensions and routes are initialized through `create_app()`, making configuration and deployment easier to manage.
- **Relational traceability:** recipes, raw-material lots, batches, measurements, kegs, movements, customers, and tastings are connected through SQLAlchemy models.
- **Role-based access control:** authenticated users receive permissions according to their operational role.
- **Service boundary:** integrations such as chatbot inventory access are isolated from HTTP route handlers.
- **Database migrations:** Alembic and Flask-Migrate provide controlled schema evolution.
- **Production deployment:** the application runs behind Nginx and Gunicorn on Ubuntu with PostgreSQL.
- **Resilient edge integration:** the Raspberry Pi persists readings locally before delivery, while UUID-based idempotency prevents duplicate measurements after retries.
- **Verified remote control:** setpoint commands include expected-current-value and maximum-delta safeguards, physical acknowledgement, and read-back confirmation.

## Local development

### Requirements

- Python 3.11 or later recommended
- PostgreSQL or MySQL
- `venv` or another Python virtual-environment tool

### Installation

```bash
git clone https://github.com/afosorioh/brewadministrator.git
cd brewadministrator

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Create the local configuration expected by the application's `Config` class. At minimum, configure a secret key and database connection without committing credentials to Git.

Example environment values:

```bash
export SECRET_KEY="replace-with-a-secure-random-value"
export DATABASE_URL="postgresql+psycopg2://user:password@localhost/brewadministrator"
```

Apply database migrations and start the development server:

```bash
flask --app run.py db upgrade
python run.py
```

The development server is normally available at `http://127.0.0.1:5000`.

> The exact configuration variable names depend on the repository's local `Config` implementation. Review that file before deployment and keep production secrets outside source control.

## Production considerations

A typical deployment uses:

```text
Client
  ↓
Nginx
  ↓
Gunicorn
  ↓
Flask application
  ↓
PostgreSQL
```

Recommended operational controls include TLS termination, restricted database access, environment-based secrets, regular PostgreSQL backups, structured application logs, and migration review before releases.

Raw-material quality certificates are stored outside the public static directory in `instance/quality_certificates` by default. Production backups should include this directory together with the PostgreSQL database. Deployments may override the location with the `QUALITY_CERTIFICATES_FOLDER` application setting; the Gunicorn service user must have read and write access to it. The reverse proxy request-body limit must also accommodate the configured certificate size (for the 10 MB default, an Nginx `client_max_body_size 11M;` limit allows multipart overhead).

## Project status

The platform is under active development and is already used for brewery operations. Current work focuses on extending operational workflows, reporting, inventory integrations, usability, and production traceability.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Author

**Andrés Felipe Osorio Henker**  
Backend Software Engineer · Telecommunications Engineer · University Lecturer · Researcher

- GitHub: [@afosorioh](https://github.com/afosorioh)
- LinkedIn: [andres-felipe-osorio-henker](https://www.linkedin.com/in/andres-felipe-osorio-henker)
