# 🎬 BookMyShow Clone — Django Enterprise Movie Ticketing Platform

> A full-featured, high-performance Django web platform for movie discovery, real-time seat reservations with concurrency safety, online payments, PDF ticket generation, and real-time business analytics.

[![Django](https://img.shields.io/badge/Django-5.1-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Celery](https://img.shields.io/badge/Celery-5.6-37B24D?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

---

## 📌 Overview

Welcome to the **BookMyShow Clone**! This project is a complete end-to-end movie discovery and ticket booking engine engineered with Python and Django.

Whether you're looking for the latest blockbuster, picking your favorite seats in real-time, receiving an instant PDF ticket with a scannable QR code via email, or analyzing business revenue via an interactive admin dashboard, this platform has you covered.

### 💡 Core Architectural Philosophy: Non-Intrusive Modular Extensions
This project was built on top of an existing Django foundation with a strict rule: **Zero modification to legacy models**. Instead of altering original schemas (`Movie`, `Theater`, `Seat`, `Booking`, `User`), all new capabilities were built as decoupled, self-contained Django apps:
- `movie_features`: Extended movie metadata, video trailers, cast profiles, review reporting, verified viewer badges.
- `seat_reservations`: Atomic row-level concurrency locking (`select_for_update`) with 2-minute expiration timers.
- `booking_payments` & `payments`: Gateway integrations (Razorpay/Stripe), HMAC webhook signature verification, and Celery asynchronous PDF ticket generation with QR code embedding.
- `analytics`: Staff dashboard with interactive Chart.js graphs, KPI summaries, and CSV business report exports.
- `discovery`: Tabbed user/admin login UI, multi-criteria filtering, full-text search, and personalized recommendation engines based on booking history.

---

## 🚀 Key Features

### 🎬 Task 1: Movie Management, Trailers & Verified Reviews (`movie_features`)
- **Embedded Trailers & Galleries**: Watch YouTube trailers in responsive modal overlays and browse multi-photo movie galleries.
- **Detailed Cast & Crew**: Rich cards detailing cast members, directors, character names, and actor bios.
- **Database-Level Ratings**: Automatic `Avg('rating')` aggregation computed directly in SQL.
- **Verified Viewer Reviews**: Reviews from users with confirmed bookings receive an official **✓ Verified Viewer** badge.
- **Review Moderation**: Eligible users can post, edit, or report inappropriate reviews.

### 💺 Task 2: Smart Seat Reservation & Live Availability (`seat_reservations`)
- **Interactive Seat Grid**: Color-coded seat maps (Available 🟢, Reserved 🟡, Booked 🔴, Selected 🔵) supporting 50 seats (A1 to E10) per screen.
- **2-Minute Lock Timer**: Reserving seats locks them temporarily for 120 seconds with a live JS countdown (`01:59` → `00:00`).
- **Race Condition & Concurrency Safe**: Uses PostgreSQL/SQLite atomic row locking (`select_for_update` inside `@transaction.atomic`) so two users clicking the same seat simultaneously will never cause double-booking.
- **Auto-Expiration Background Command**: `python manage.py expire_seat_reservations` automatically releases stale locks.

### 💳 Task 3: Payment Workflows, Webhook Security & PDF Tickets (`booking_payments` & `payments`)
- **Multi-Gateway Ready**: Integration templates for Razorpay and Stripe Python SDKs alongside mock test checkout modes.
- **HMAC SHA256 Webhook Verification**: Cryptographically verifies webhook payloads to prevent unauthorized payment injection.
- **Webhook Idempotency Protection**: Ensures duplicate webhook retries never produce duplicate bookings or double charges.
- **PDF Ticket & QR Code Engine**: Generates downloadable ReportLab PDF tickets with embedded PNG QR codes.
- **Asynchronous Email Confirmation (Celery)**: Dispatches PDF tickets asynchronously using Celery background tasks with automatic retry handling (`max_retries=3`).
- **User Payment History**: View past transactions and download historical PDF tickets anytime from your user profile.

### 📊 Task 4: Comprehensive Admin Analytics Dashboard (`analytics`)
- **Staff Secured Dashboard**: Accessible at `/admin-dashboard/` exclusively for staff members (`is_staff`).
- **Real-Time KPI Cards**: Revenue Totals, Booking Counts, Active User Counts, and Average Seat Occupancy %.
- **Interactive Chart.js Visualizations**:
  - Revenue Timeline (Line Chart with 7D / 30D / All Time toggle)
  - Top Performing Movies (Bar Chart)
  - Screen Occupancy Rates % (Doughnut Chart)
- **One-Click CSV Export**: Download sales, booking, and movie metrics directly into Excel/CSV format.

### 🔍 Task 5: Movie Discovery & Custom Tabbed Authentication (`discovery`)
- **Custom Tabbed Auth Interface**: `/login/` features **User Login** and **Admin Login** tabs to cleanly segment moviegoers from staff admins.
- **Full-Text Search**: Single-pass `Q` OR-expressions searching title, description, and cast with 300ms debouncing.
- **Multi-Criteria Filtering**: Filter dynamically by Genre, Language, Theater / Screen, and Minimum Rating range.
- **Personalized Recommendations**: Analyzes user booking history for preferred genres and languages to display tailored movie suggestions, falling back to top trending blockbusters.
- **Recently Viewed Tracker**: Logs user movie views for easy return access.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, Django 5.1, Django ORM
- **Database**: SQLite (Development) / PostgreSQL compatible
- **Background Tasks & Queue**: Celery 5.6, Redis
- **Templating & UI**: HTML5, Vanilla CSS3, Bootstrap 4/5, Vanilla JavaScript (ES6+ AJAX)
- **Data Visualization**: Chart.js (CDN)
- **PDF & QR Code Generation**: ReportLab, `qrcode`, Pillow
- **Payment SDKs**: Razorpay, Stripe

---

## 💻 Installation & Setup Instructions

Follow these steps to get a local development environment running:

### 1. Prerequisites
- Python 3.10+ installed on your system.
- Git installed on your system.
- Redis server running locally (optional for Celery async tasks; background thread fallback included).

### 2. Clone the Repository
```bash
git clone https://github.com/NoorMohamedHalith/DJANGO-BOOKMYSHOW-CLONE.git
cd DJANGO-BOOKMYSHOW-CLONE
```

### 3. Create & Activate Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Create a `.env` file in the root directory (or rely on default development fallbacks):
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Payment Gateways (Optional)
RAZORPAY_KEY_ID=rzp_test_mockkeyid123
RAZORPAY_KEY_SECRET=mockkeysecret123456789
RAZORPAY_WEBHOOK_SECRET=mockwebhooksecret123456

STRIPE_PUBLISHABLE_KEY=pk_test_mockpublishablekey
STRIPE_SECRET_KEY=sk_test_mocksecretkey
STRIPE_WEBHOOK_SECRET=whsec_mockwebhooksecret
```

### 6. Apply Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create Superuser (Admin Account)
```bash
python manage.py createsuperuser
```
*(Pre-configured development superuser: Username `admin` | Password `admin123`)*

---

## 🏃 Running the Application

### 1. Start Django Web Server
```bash
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser.

### 2. Start Celery Worker (Optional for Async Emails)
In a separate terminal window:
```bash
celery -A bookmyseat worker --loglevel=info
```
*(If Redis is not running, the platform automatically uses a non-blocking background thread fallback for emails, ensuring 100% execution uptime).*

---

## 🧪 Testing Strategy (52/52 Passing)

The project includes unit and integration tests across all custom Django applications.

Run the full test suite:
```bash
python manage.py test movie_features seat_reservations booking_payments payments analytics discovery
```

**Output:**
```text
Creating test database for alias 'default'...
Found 52 test(s).
System check identified no issues (0 silenced).
....................................................
Ran 52 tests in 66.879s

OK
```

---

## 🔑 Admin Access Credentials

To review the **Admin Analytics Dashboard** or standard **Django Admin Panel**:

- **URL**: [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/) *(Click Admin Login Tab)*
- **Django Admin URL**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **Username**: `admin`
- **Password**: `admin123`

---

## 📸 Screenshots

*(Place screenshots here)*

- **Discovery Hub**: `![Discovery Hub](docs/screenshots/discovery.png)`
- **Seat Reservation Grid**: `![Seat Reservation Grid](docs/screenshots/seats.png)`
- **PDF Ticket with QR Code**: `![PDF Ticket](docs/screenshots/ticket.png)`
- **Admin Analytics Dashboard**: `![Analytics Dashboard](docs/screenshots/analytics.png)`

---

## 🚢 Deployment Notes

- **Webhooks Handling**: When testing Razorpay or Stripe webhooks locally, use [ngrok](https://ngrok.com/):
  ```bash
  ngrok http 8000
  ```
  Set your webhook target URL to `https://<your-ngrok-id>.ngrok-free.app/payments/webhook/razorpay/`.
- **Production Server**: Recommended stack includes Gunicorn + Nginx + PostgreSQL + Redis.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.

---

## 🙌 Acknowledgements & Credits

Developed with ❤️ by **[NoorMohamedHalith](https://github.com/NoorMohamedHalith)**.  
Built using Python, Django, Chart.js, ReportLab, and Celery.
