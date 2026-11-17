# SmartBite - AI-enabled online food delivery

Customers, restaurant owners (with cooks/packagers), delivery riders and an admin on one Flask + MySQL platform.
Prices are in Nigerian Naira. Python 3.10+ and MySQL 8 (or MariaDB 10.5+) are required.

## Run it

```bash
# 1. Install
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Create the database and import the schema
mysql -u root -p -e "CREATE DATABASE smartbite_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
mysql -u root -p smartbite_db < database.sql

# 3. Configure (copy .env.example to .env and set DB_PASSWORD at least)
cp .env.example .env

# 4. Start
python app.py                       # http://127.0.0.1:5000
```

**First admin login:** `admin@smartbite.com` / `Admin@12345` (change `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env` *before* the first start if you prefer).
You are forced to set a new password the first time you sign in.

### Windows setup (PowerShell)

1. Install Python 3.10+ and MySQL 8 (or MariaDB). During Python setup, enable **Add Python to PATH**.
2. Open the `smartbite` project folder in File Explorer, click the address bar, type `powershell`, and press Enter.
3. Run these commands one at a time:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

4. Open `.env` in a text editor and enter your MySQL password in `DB_PASSWORD`. The example uses the first-run administrator account shown below; change the administrator password after signing in. Leave `SECRET_KEY` blank to let SmartBite generate a private random key, or enter a long random value.
5. Open MySQL Workbench, create a database named `smartbite_db` with `utf8mb4` character set, then use **Server → Data Import** (or **File → Open SQL Script**) to run `database.sql` against `smartbite_db`.
6. Return to PowerShell and run `python app.py`. Open `http://127.0.0.1:5000` in your browser.

If PowerShell blocks virtual-environment activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell window, then activate `.venv` again. Do not share your `.env` file or `.secret_key`.

## Try the whole flow (about 5 minutes)

1. Sign up as a **restaurant owner** (restaurant name required). Add bank details under *Profile* and a few dishes under *My Foods*.
2. Log in as **admin** -> *Manage Restaurants* -> *Approve*. (Set commission, service charge, ad price and bank details under *Settings*.)
3. Sign up as a **customer** -> browse -> add to cart -> checkout. Pick *Online* to see the bank details, Paystack button and the **proof-of-payment upload**.
4. As the owner open *Payment Verifications* -> *Approve*; the order becomes **Confirmed**. (Rejecting notifies the customer, who can upload again.)
5. Sign up as a **rider** -> open the new *Dashboard* -> *Available Orders* -> *Accept* -> *Route Map* -> update Picked -> On the way -> Delivered.
6. The customer watches order progress and, when the rider enables GPS sharing, the rider marker on *Order Tracking*. After delivery the customer can leave a review.
7. Owners can add **staff** (cook/packager). Staff see only the kitchen queue (no prices) and their own monthly salary. Riders have a dedicated dashboard with workload, completed-delivery and daily-earnings summaries.

## Pricing formula

`total = food_total + service_charge + (food_total * commission / 100)` - both values are set by the admin and stored on every order.
Rider pay per delivery is a separate admin setting funded from platform income.

## Recently added customer features

- **Password recovery:** Login includes a Forgot Password link. Reset links are signed, expire after 30 minutes, and become invalid after the password changes. Configure the optional SMTP values in `.env` for email delivery (`MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, `MAIL_USE_TLS`). For Gmail, use an App Password rather than your normal account password. Without SMTP settings, reset emails cannot be delivered.
- **Meal suggestion popup:** The customer dashboard has a “Suggest a meal for me” button. It opens a popup using SmartBite's existing customer recommendations and popular-meal picks.
- **Delivery estimate:** Checkout displays an approximate window that changes with the order stage. It is a simple status-based estimate, not a trained regression model or live traffic prediction.

## The six AI features (all run on your own database - no external AI service)

| # | Feature | Where | How it works |
|---|---------|-------|--------------|
| 1 | Food recommendation | Customer dashboard | Frequency-based ranking of the customer’s past orders. Falls back to popular dishes for new users; not a trained collaborative-filtering model. |
| 2 | Smart Search | Top search bar, landing page | Parses text like `spicy chicken under 3000` into price constraints and keywords matched against menu and restaurant data. Understands under/below/over/between and `3k`; this is rule-based parsing. |
| 3 | AI Picks | Customer dashboard | Most ordered today and trending near the customer (restaurants sharing words with their address). |
| 4 | Demand forecasting | Owner dashboard + Analytics | Uses the previous 28 days of sales, combining same-weekday averages with a recent seven-day average to produce indicative next-day dish estimates. |
| 5 | Route optimisation | Rider -> Route Map | Leaflet + OpenStreetMap, nearest-stop-first ordering (drop-off only after pickup), road distance/time from OSRM with a straight-line fallback. Heuristic, not a global optimum solver. |
| 6 | Fraud detection | Admin -> Fraud Alerts | Rule-based alerts for more than 5 orders from one customer in 10 minutes, or any order above ₦50,000. Runs on every order and on demand (*Re-scan*); not a trained fraud model. |

## Security built in

Passwords hashed (scrypt via Werkzeug) - CSRF token on every POST - login throttling (5 failures / 5 min) - HttpOnly + SameSite cookies - role checks on every route and ownership checks on every record -
uploads limited to JPG/PNG, verified, re-encoded (metadata stripped), random file names, 5 MB cap - SQL via SQLAlchemy (parameterised) - Jinja auto-escaping - strict Content-Security-Policy and other security headers -
open-redirect protection - forced password change for the seeded admin and new staff accounts.

## Before you go live (checklist)

1. Set a strong `SECRET_KEY` in `.env` (otherwise one is generated into `.secret_key`; keep that file private).
2. Serve over **HTTPS** and set `SESSION_COOKIE_SECURE=1`.
3. Run with a production server, not `python app.py`: `pip install gunicorn` then `gunicorn -w 3 -b 127.0.0.1:8000 app:app` behind Nginx/Caddy.
   The login rate limiter is in-process memory; with several workers use a shared limiter (e.g. Flask-Limiter + Redis) or keep to one worker per host.
4. Let Nginx serve `/static/` directly and set `client_max_body_size 6m;`. Payment proofs live in `static/uploads/proofs/` with unguessable names;
   for stricter privacy, move them outside `static/` and serve them through an authenticated route.
5. Back up the database and the `static/uploads` folder.
6. Paystack: put your public key in `PAYSTACK_PUBLIC_KEY` to enable the Paystack Inline popup. The browser callback reference is saved, but this version does not verify the transaction with Paystack on the server. The restaurant still reviews the uploaded proof before an order is confirmed. For production, add a server-side webhook/verify call using a secret key kept only on the server.
7. Map search and routing use free public OpenStreetMap services (Nominatim, OSRM). They are fine for starting out; for heavy traffic use a paid geocoding/routing provider.
8. Fonts, Chart.js (jsDelivr) and Leaflet (unpkg) load from CDNs. To remove that dependency, download them into `static/` and update the CSP in `app.py`.

## Project layout

```
app.py            all routes, AI logic, security, seed data      models.py   SQLAlchemy models
config.py         environment-based settings                     database.sql MySQL schema + starter data
templates/        Jinja2 pages (public, customer/, restaurant/, rider/, admin/, staff/, shared/)
static/           css/style.css, js/main.js, images/ (logo.png, illustrations), uploads/ and uploads/proofs/
```

Roles: `customer`, `restaurant_owner`, `rider`, `admin`, plus `staff` (created by restaurant owners).


## Live GPS delivery tracking

SmartBite supports rider-to-customer live GPS updates. A rider opens **Route Map**, selects an assigned active order, and presses **Enable live GPS**. The browser asks for location permission and sends coordinates to the Flask server; the customer's Order Tracking page refreshes the rider marker approximately every five seconds. Tracking stops being available when the order is delivered or cancelled.

### Database update for an existing installation

If SmartBite is already installed, run `database/migrations/2026_11_add_rider_locations.sql` once in the `smartbite` MySQL database (or import the updated `database.sql` into a fresh database):

```sql
CREATE TABLE IF NOT EXISTS rider_locations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  rider_id INT NOT NULL, order_id INT NOT NULL,
  latitude DOUBLE NOT NULL, longitude DOUBLE NOT NULL, accuracy DOUBLE NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_rider_location_order (rider_id, order_id),
  INDEX ix_rider_locations_order (order_id), INDEX ix_rider_locations_rider (rider_id),
  CONSTRAINT fk_rider_locations_rider FOREIGN KEY (rider_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_rider_locations_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Important GPS requirements

- Browser geolocation requires **HTTPS** on deployed websites. `http://localhost` is allowed for local development, but another phone accessing a laptop over a local-network HTTP address may be blocked by the browser.
- The rider must allow location permission and keep the rider page open while sharing. Mobile operating systems may pause browser GPS when the screen is locked or the browser is in the background; this implementation is not a native background-tracking service.
- Customer location is not collected by this feature. Only the assigned rider's coordinates are shared, and only with the customer who owns that order.
- Map tiles require an internet connection. OpenStreetMap attribution is displayed on the map.
- For production deployment, use HTTPS, a privacy notice and a clear rider consent policy.

## Documentation included

The corrected project report is included at `docs/SmartBite_Corrected.docx`. It describes the actual Flask/MySQL implementation, the implemented role modules, the limits of the current payment and AI functions, and a website-feature/documentation alignment table. The report notes that the code was statically inspected but not run against a live MySQL database during this correction.

## Rider dashboard update

Riders now land on `/rider/dashboard` after login. The dashboard shows active deliveries, available orders, deliveries completed today, earnings today, recent delivery activity, and shortcuts to the route map and earnings pages.
