"""Stripe-hosted checkout for Edwards Ventures' fixed-price pilot."""
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory='app/templates')
DATABASE = Path(os.getenv('VENTURES_DB_PATH', '/data/ventures.db'))
BASE_URL = os.getenv('CHECKOUT_BASE_URL', 'http://localhost:8140').rstrip('/')
STRIPE_KEY = os.getenv('STRIPE_SECRET_KEY', '')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
stripe.api_key = STRIPE_KEY


def db():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE), timeout=20)
    connection.execute('''CREATE TABLE IF NOT EXISTS checkout_payments (
        session_id TEXT PRIMARY KEY, amount_total INTEGER NOT NULL,
        currency TEXT NOT NULL, customer_email TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL, paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    connection.commit()
    return connection


@router.get('/checkout', response_class=HTMLResponse)
def checkout_page(request: Request):
    return templates.TemplateResponse(request, 'checkout.html', {
        'enabled': STRIPE_KEY.startswith('sk_test_') or STRIPE_KEY.startswith('sk_live_'),
        'test_mode': STRIPE_KEY.startswith('sk_test_')
    })


@router.post('/checkout/start')
def start_checkout():
    if not STRIPE_KEY.startswith(('sk_test_', 'sk_live_')):
        raise HTTPException(503, 'Payments are not configured yet. No charge was made.')
    try:
        session = stripe.checkout.Session.create(
            mode='payment',
            line_items=[
                {'price_data': {'currency':'usd','unit_amount':30000,'product_data': {'name':'Lead Response System — pilot setup'}}, 'quantity':1},
                {'price_data': {'currency':'usd','unit_amount':7500,'product_data': {'name':'Lead Response System — initial 30 days of support'}}, 'quantity':1}
            ],
            customer_creation='always',
            billing_address_collection='auto',
            success_url=BASE_URL + '/checkout/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=BASE_URL + '/checkout?canceled=1',
            metadata={'product':'lead-response-pilot', 'package':'setup-plus-30-day-support'},
        )
    except stripe.error.StripeError:
        raise HTTPException(502, 'Unable to start checkout. Please try again later.')
    if not session.url or urlparse(session.url).hostname not in {'checkout.stripe.com'}:
        raise HTTPException(502,'Invalid checkout destination')
    return RedirectResponse(session.url, status_code=303)


@router.get('/checkout/success', response_class=HTMLResponse)
def checkout_success(request: Request, session_id: str = ''):
    paid = False
    if STRIPE_KEY and session_id.startswith('cs_') and len(session_id) < 250:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            paid = (session.payment_status == 'paid'
                    and session.amount_total == 37500
                    and session.currency == 'usd'
                    and session.metadata.get('product') == 'lead-response-pilot')
        except stripe.error.StripeError:
            paid = False
    return templates.TemplateResponse(request,'checkout_success.html', {'paid':paid})


@router.post('/stripe/webhook')
async def stripe_webhook(request: Request):
    if not WEBHOOK_SECRET or not STRIPE_KEY:
        raise HTTPException(503, 'Webhook not configured')
    body = await request.body()
    signature = request.headers.get('stripe-signature', '')
    try:
        event = stripe.Webhook.construct_event(body, signature, WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(400, 'Invalid webhook')
    if event.type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
        incoming = event.data.object
        try:
            session = stripe.checkout.Session.retrieve(incoming.id)
        except stripe.error.StripeError:
            raise HTTPException(502, 'Unable to verify payment')
        if (session.payment_status == 'paid' and session.amount_total == 37500
                and session.currency == 'usd' and session.metadata.get('product') == 'lead-response-pilot'):
            email = (session.customer_details.email if session.customer_details else '') or ''
            conn = db()
            try:
                conn.execute('''INSERT OR IGNORE INTO checkout_payments
                    (session_id,amount_total,currency,customer_email,status)
                    VALUES (?,?,?,?,?)''', (session.id,37500,'usd',email,'Paid'))
                conn.commit()
            finally:
                conn.close()
    return {'received': True}
