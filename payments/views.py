import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
import json
import logging
from django.http import HttpResponse
from .models import Payment


class RegistrationForm(UserCreationForm):
    """Custom registration form with required email field"""
    email = forms.EmailField(required=True, help_text='Required. Enter a valid email address.')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

# ===================== AUTHENTICATION VIEWS =====================

def register(request):
    """Register a new user account"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            logger.info(f"New user registered: {user.username} ({user.email})")
            return redirect('dashboard')
    else:
        form = RegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})


def login_view(request):
    """Login to user account"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            logger.info(f"User logged in: {username}")
            return redirect('dashboard')
        else:
            return render(request, 'auth/login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'auth/login.html')


@login_required(login_url='login')
def logout_view(request):
    """Logout user"""
    username = request.user.username
    logout(request)
    logger.info(f"User logged out: {username}")
    return redirect('login')


# ===================== PAYMENT VIEWS =====================

@login_required(login_url='login')
def dashboard(request):
    """Display user dashboard with payment history"""
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'payments': payments,
        'total_spent': sum(p.amount for p in payments if p.status == 'paid') / 100,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, 'payments/dashboard.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def create_checkout_session(request):
    """Create a Stripe checkout session for payment"""
    try:
        # Create payment first so we can correlate via metadata
        payment = Payment.objects.create(
            user=request.user,
            amount=2000,
            currency="usd",
            status="pending",
        )

        # Build checkout session data
        checkout_data = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Django Stripe Test Product"},
                    "unit_amount": payment.amount,
                },
                "quantity": 1,
            }],
            "mode": "payment",
            # Include session id so success view can confirm and update
            "success_url": "http://localhost:8000/payments/success/?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "http://localhost:8000/payments/cancel/",
            # Help correlate webhooks back to our Payment
            "client_reference_id": str(request.user.id),
            "metadata": {
                "payment_id": str(payment.id),
                "user_id": str(request.user.id),
            },
            # Ensure the PaymentIntent also carries the metadata
            "payment_intent_data": {
                "metadata": {
                    "payment_id": str(payment.id),
                    "user_id": str(request.user.id),
                }
            },
        }

        # Only add email if user has one
        if request.user.email:
            checkout_data["customer_email"] = request.user.email

        session = stripe.checkout.Session.create(**checkout_data)

        # Link session id to our payment
        payment.stripe_session_id = session.id
        payment.save(update_fields=["stripe_session_id"])

        logger.info(
            f"Checkout session created: {session.id} for user {request.user.username} (payment_id={payment.id})"
        )

        return JsonResponse({"checkout_url": session.url, "session_id": session.id})

    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)


def payment_success(request):
    """Payment success page"""
    session_id = request.GET.get('session_id')
    payment = None
    
    if session_id:
        try:
            payment = Payment.objects.filter(stripe_session_id=session_id).first()

            # Confirm with Stripe to update status immediately (fallback to webhook)
            session = stripe.checkout.Session.retrieve(session_id)
            payment_status = session.get("payment_status")
            intent_id = session.get("payment_intent")

            if payment and payment_status == "paid" and payment.status != "paid":
                payment.status = "paid"
                if intent_id:
                    payment.stripe_payment_intent = intent_id
                payment.save()
                logger.info(f"Success view marked payment as paid (payment_id={payment.id})")
        except Payment.DoesNotExist:
            logger.warning(f"Payment not found: {session_id}")
        except Exception as e:
            logger.error(f"Error confirming payment on success page: {str(e)}")
    
    return render(request, 'payments/success.html', {'payment': payment})


def payment_cancel(request):
    """Payment cancel page"""
    return render(request, 'payments/cancel.html')


@login_required(login_url='login')
@require_http_methods(["GET"])
def verify_payment(request):
    """Verify payment status and retrieve payment details"""
    session_id = request.GET.get('session_id')
    
    if not session_id:
        return JsonResponse({"error": "session_id parameter required"}, status=400)
    
    try:
        payment = Payment.objects.get(stripe_session_id=session_id, user=request.user)
        
        return JsonResponse({
            "status": "success",
            "payment": {
                "id": payment.id,
                "session_id": payment.stripe_session_id,
                "amount": payment.amount / 100,  # Convert to dollars
                "currency": payment.currency,
                "status": payment.status,
                "created_at": payment.created_at.isoformat(),
            }
        })
    except Payment.DoesNotExist:
        logger.warning(f"Payment verification failed for session: {session_id}")
        return JsonResponse({"error": "Payment not found"}, status=404)


# ===================== WEBHOOK =====================

@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """Handle Stripe webhook events with improved error handling and idempotency"""
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    if not sig_header:
        logger.warning("Webhook received without signature header")
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        logger.info(f"Webhook event received: {event['type']}")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        return HttpResponse(status=400)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {str(e)}")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {str(e)}")
        return HttpResponse(status=400)

    # Log the event type
    logger.info(f"Webhook event: {event['type']}")

    # Helper to safely mark a payment as paid (idempotent)
    def mark_payment_paid(pmt: Payment, payment_intent_id=None):
        try:
            if pmt.status != "paid":
                if payment_intent_id and not pmt.stripe_payment_intent:
                    pmt.stripe_payment_intent = payment_intent_id
                pmt.status = "paid"
                pmt.save()
                logger.info(f"Payment marked as paid (payment_id={pmt.id})")
            else:
                logger.info(f"Payment already paid (idempotent), payment_id={pmt.id}")
        except Exception as ex:
            logger.error(f"Error saving paid status for payment_id={pmt.id}: {str(ex)}")

    # Handle checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["id"]

        # Try metadata mapping first
        metadata = session.get("metadata") or {}
        payment_id = metadata.get("payment_id")
        payment = None
        try:
            if payment_id:
                payment = Payment.objects.get(id=int(payment_id))
            else:
                payment = Payment.objects.get(stripe_session_id=session_id)

            mark_payment_paid(payment, session.get("payment_intent"))

            # Optional: email extraction/logging
            email = (
                (session.get("customer_details") or {}).get("email")
                or session.get("customer_email")
            )
            if email:
                logger.info(f"Linked email from session: {email}")

        except Payment.DoesNotExist:
            logger.warning(f"Webhook received for unknown payment: session={session_id} metadata.payment_id={payment_id}")
            return HttpResponse(status=400)
        except Exception as e:
            logger.error(f"Error updating payment status: {str(e)}")
            return HttpResponse(status=500)

    # Handle async card confirmation success (e.g., 3DS)
    elif event["type"] == "checkout.session.async_payment_succeeded":
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}
        payment_id = metadata.get("payment_id")
        try:
            if payment_id:
                payment = Payment.objects.get(id=int(payment_id))
                mark_payment_paid(payment, session.get("payment_intent"))
        except Exception as e:
            logger.error(f"Error on async payment success: {str(e)}")

    # Handle charge.failed event
    elif event["type"] == "charge.failed":
        charge = event["data"]["object"]
        logger.warning(f"Charge failed: {charge.get('id')}")
        
        try:
            payment = Payment.objects.filter(
                stripe_payment_intent=charge.get("payment_intent")
            ).first()
            
            if payment:
                payment.status = "failed"
                payment.save()
                logger.info(f"Payment marked as failed: {payment.stripe_session_id}")
        except Exception as e:
            logger.error(f"Error updating failed payment: {str(e)}")

    # Handle charge.refunded event
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        logger.info(f"Charge refunded: {charge.get('id')}")
        logger.info(f"Refund amount: {charge.get('amount_refunded')}")

    # Handle charge.succeeded event (fallback to ensure paid status)
    elif event["type"] == "charge.succeeded":
        charge = event["data"]["object"]
        intent_id = charge.get("payment_intent")
        try:
            payment = Payment.objects.filter(stripe_payment_intent=intent_id).first()
            if payment:
                mark_payment_paid(payment, intent_id)
        except Exception as e:
            logger.error(f"Error updating payment from charge.succeeded: {str(e)}")

    # Handle charge.dispute.created event
    elif event["type"] == "charge.dispute.created":
        dispute = event["data"]["object"]
        logger.warning(f"Dispute created for charge: {dispute.get('charge')}")

    # Handle invoice.payment_succeeded event (for future subscriptions)
    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        logger.info(f"Invoice payment succeeded: {invoice.get('id')}")

    # Handle payment_intent.succeeded event
    elif event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        intent_id = payment_intent.get("id")
        logger.info(f"Payment intent succeeded: {intent_id}")
        metadata = payment_intent.get("metadata") or {}
        payment_id = metadata.get("payment_id")
        try:
            payment = None
            if payment_id:
                payment = Payment.objects.get(id=int(payment_id))
            else:
                payment = Payment.objects.filter(stripe_payment_intent=intent_id).first()
            if payment:
                mark_payment_paid(payment, intent_id)
        except Exception as e:
            logger.error(f"Error updating payment from payment_intent.succeeded: {str(e)}")

    return HttpResponse(status=200)
