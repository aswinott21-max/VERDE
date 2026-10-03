# VERDÉ

**Plant, Pot and Gardening Tools E-Commerce Website**

VERDÉ is an e-commerce web application developed for selling plants, pots, and gardening equipment online. The project provides separate customer and administrator features for browsing products, managing carts and wishlists, placing orders, and managing the store.

## Features

### Customer Features

- User registration and login
- OAuth login
- Product listing with search, sorting, filtering, and pagination
- Product details with pricing, offers, stock informations, ratings, and reviews
- Related product recommendations
- Wishlist management
- Shopping cart management
- Stock and maximum purchase quantity validation
- Checkout and order placement
- Order history and invoice
- Return and refund management
- Wallet functionality
- Coupon support

### Administrator Features

- Admin authentication
- Product management
- Category management
- Product offer management
- Order management
- User management
- Coupon management
- Sales and revenue reports
- Best-selling category information
- Banner management
- Referral management
- Settings management

## Technologies Used

- **Python**
- **Django**
- **PostgreSQL**
- **HTML**
- **CSS**
- **JavaScript**
- **Razorpay**
- **Git & GitHub**

## Project Structure

The project is organized into separate Django applications based on their responsibilities:

VERDE/
├── adminpanel/
├── cart/
├── catalog/
├── config/
├── orders/
├── products/
├── users/
├── wishlist/
├── static/
├── manage.py
└── README.md

### Main Applications

- **users** — User authentication, registration, profiles, and user management
- **catalog** — Categories and product catalog data
- **products** — Product listing, product details, pricing, offers, and product management
- **cart** — Shopping cart functionality
- **wishlist** — Wishlist functionality
- **orders** — Checkout, orders, returns, refunds, and order management
- **adminpanel** — Administrator-related functionality
- **config** — Django project configuration

> **Note:** The project structure may be expanded with additional Django applications as new features are implemented.

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/aswinott21-max/VERDE.git
cd VERDE
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

### 3. Activate the Virtual Environment

On Linux/macOS:

```bash
source .venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the project root and add the required environment variables.

Do not commit the `.env` file to GitHub.

### 6. Apply Database Migrations

```bash
python manage.py migrate
```

### 7. Run the Development Server

```bash
python manage.py runserver
```

The application can then be accessed at:

```text
http://127.0.0.1:8000/

```

## Environment Variables

VERDÉ uses environment variables for sensitive configuration such as database credentials and payment gateway settings.

Create a `.env` file in the project root and configure the required values according to your local environment.

Example:

```env
SECRET_KEY=your-secret-key
DEBUG=True

DB_NAME=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_HOST=localhost
DB_PORT=5432
```

Payment gateway credentials, OAuth credentials, and other sensitive values should also be stored in the `.env` file when required.

**Never commit real credentials or API keys to GitHub.**

## Database Setup

VERDÉ uses **PostgreSQL** as its database.

Make sure PostgreSQL is installed and running before starting the application.

Create a PostgreSQL database and configure the database credentials in the `.env` file.

After configuring the database, run:

```bash
python manage.py migrate
```

To create an administrator account for the Django application:

```bash
python manage.py createsuperuser
```

## Running the Project

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Start the Django development server:

```bash
python manage.py runserver
```

Open the application in a web browser:

```text
http://127.0.0.1:8000/
```

To stop the development server, press:

```text
Ctrl + C
```

## Project Status

VERDÉ is currently under active development.

Core e-commerce functionality has been implemented, including product browsing, search, filtering, sorting, pagination, product details, wishlist, shopping cart, offers, and administrative product and order management.

Additional features and improvements will continue to be added as development progresses.

## Future Improvements

- Additional e-commerce features
- Further improvements to the customer experience
- Performance optimization
- Additional testing and validation
- UI and usability improvements
- Additional reporting and management features
