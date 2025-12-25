# Django Stripe Payments

A simple Django application for handling Stripe payments with user authentication, webhook handling, and payment verification.

## Features

- **User Authentication** - Register, login, logout with email support
- **Stripe Checkout** - Secure payment processing via Stripe Checkout Sessions
- **Webhook Handling** - Reliable payment confirmation with signature verification
- **Payment Verification** - API endpoint to verify payment status
- **Dashboard** - View payment history and total spent

## Tech Stack

- Django 6.0
- Stripe API (v14.1.0)
- SQLite (development)
- Python 3.14+

## Setup

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd django-stripe

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the project root:

```env
STRIPE_SECRET_KEY=sk_test_your_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
```

Get your keys from [Stripe Dashboard](https://dashboard.stripe.com/apikeys).

### 3. Database Setup

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Run the Server

```bash
python manage.py runserver
```

Visit `http://localhost:8000`

## Webhook Testing (Local Development)

Use the Stripe CLI to forward webhooks locally:

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli

# Login to Stripe
stripe login

# Forward webhooks to your local server
stripe listen --forward-to http://localhost:8000/payments/webhook/
```

Copy the webhook signing secret from the CLI output and add it to your `.env` file.

## URLs

| URL | Method | Description |
|-----|--------|-------------|
| `/` | GET | Home page |
| `/register/` | GET, POST | User registration |
| `/login/` | GET, POST | User login |
| `/logout/` | GET | User logout |
| `/payments/dashboard/` | GET | User dashboard with payment history |
| `/payments/create-checkout-session/` | POST | Create Stripe checkout session |
| `/payments/success/` | GET | Payment success page |
| `/payments/cancel/` | GET | Payment cancelled page |
| `/payments/verify/` | GET | Verify payment status (API) |
| `/payments/webhook/` | POST | Stripe webhook endpoint |

## API Endpoints

### Create Checkout Session

```bash
POST /payments/create-checkout-session/
```

**Response:**
```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_test_..."
}
```

### Verify Payment

```bash
GET /payments/verify/?session_id=cs_test_...
```

**Response:**
```json
{
  "status": "success",
  "payment": {
    "id": 1,
    "session_id": "cs_test_...",
    "amount": 20.00,
    "currency": "usd",
    "status": "paid",
    "created_at": "2025-12-25T12:00:00Z"
  }
}
```

## Webhook Events Handled

- `checkout.session.completed` - Marks payment as paid
- `checkout.session.async_payment_succeeded` - Handles async payments (3DS)
- `payment_intent.succeeded` - Fallback payment confirmation
- `charge.succeeded` - Additional payment confirmation
- `charge.failed` - Marks payment as failed
- `charge.refunded` - Logs refund events
- `charge.dispute.created` - Logs dispute events
- `invoice.payment_succeeded` - For future subscription support

## Project Structure

```
django-stripe/
├── config/                 # Django settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── payments/               # Main app
│   ├── models.py          # Payment model
│   ├── views.py           # Views and webhook handler
│   ├── urls.py            # URL routes
│   └── admin.py           # Admin configuration
├── templates/
│   ├── base.html          # Base template
│   ├── home.html          # Home page
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   └── payments/
│       ├── dashboard.html
│       ├── success.html
│       └── cancel.html
├── logs/                   # Log files
├── .env                    # Environment variables
├── manage.py
└── requirements.txt
```

## Test Card Numbers

Use these test cards in Stripe's test mode:

| Card | Number |
|------|--------|
| Success | 4242 4242 4242 4242 |
| Decline | 4000 0000 0000 0002 |
| 3D Secure | 4000 0000 0000 3220 |

Use any future expiry date and any 3-digit CVC.

## License

MIT
