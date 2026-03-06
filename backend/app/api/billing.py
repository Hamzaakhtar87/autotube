"""
Billing API Endpoints
Handles Lemon Squeezy subscriptions, checkout sessions, and webhooks.
"""

import logging
import os
import hmac
import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.models import User, SubscriptionTier
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing")

# Configure Lemon Squeezy Config
LEMON_API_KEY = os.getenv("LEMON_SQUEEZY_API_KEY")
LEMON_WEBHOOK_SECRET = os.getenv("LEMON_SQUEEZY_WEBHOOK_SECRET")

# Lemon Squeezy Variant IDs for Checkout links
VARIANT_IDS = {
    SubscriptionTier.PRO: os.getenv("LEMON_VARIANT_ID_PRO", "variant_pro_123"),
    SubscriptionTier.ENTERPRISE: os.getenv("LEMON_VARIANT_ID_ENTERPRISE", "variant_ent_123"),
}

# The unique store URL name for simple URL builders
STORE_URL = os.getenv("LEMON_SQUEEZY_STORE_URL", "https://autotube.lemonsqueezy.com")

class CheckoutSessionRequest(BaseModel):
    tier: str  # pro, enterprise


class CheckoutSessionResponse(BaseModel):
    url: str


class PortalSessionResponse(BaseModel):
    url: str


class SubscriptionStatusResponse(BaseModel):
    tier: str
    is_active: bool
    stripe_status: Optional[str] = None
    ends_at: Optional[str] = None


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(
    request: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Lemon Squeezy Checkout URL for the requested subscription tier."""
    try:
        tier_enum = SubscriptionTier(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid subscription tier")
        
    variant_id = VARIANT_IDS.get(tier_enum)
    if not variant_id:
        raise HTTPException(status_code=400, detail="Variant ID not configured for this tier")
        
    # Since we are creating a generic direct link, Lemon Squeezy allows appending
    # customer details and custom data directly in the URL params for fast integration.
    # Docs: https://docs.lemonsqueezy.com/help/checkout/passing-custom-data
    
    checkout_url = f"{STORE_URL}/checkout/buy/{variant_id}"
    checkout_url += f"?checkout[email]={current_user.email}"
    checkout_url += f"&checkout[name]={current_user.full_name or 'User'}"
    checkout_url += f"&checkout[custom][user_id]={current_user.id}"
    
    # Update user with a pseudo customer_id indicator if they didn't have one
    if not current_user.stripe_customer_id:
        current_user.stripe_customer_id = f"ls_cust_mock_{current_user.id}"
        db.commit()
    
    return CheckoutSessionResponse(url=checkout_url)


@router.post("/create-portal-session", response_model=PortalSessionResponse)
def create_portal_session(
    current_user: User = Depends(get_current_user)
):
    """Create a Lemon Squeezy Customer Portal session for managing subscription."""
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")
        
    # In a full integration, you would use the API to get the Customer Portal URL.
    # For now, it routes to the general billing/orders tracking link for Lemon Squeezy.
    portal_url = "https://app.lemonsqueezy.com/my-orders"
    return PortalSessionResponse(url=portal_url)


@router.get("/subscription", response_model=SubscriptionStatusResponse)
def get_subscription_status(current_user: User = Depends(get_current_user)):
    """Get current user's subscription status."""
    return SubscriptionStatusResponse(
        tier=current_user.subscription_tier,
        is_active=current_user.subscription_tier != SubscriptionTier.FREE,
        stripe_status="active" if current_user.stripe_subscription_id else "incomplete",
        ends_at=current_user.subscription_ends_at.isoformat() if current_user.subscription_ends_at else None
    )


@router.post("/webhook")
async def lemonsqueezy_webhook(
    request: Request, 
    x_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Handle Lemon Squeezy webhooks for subscription updates."""
    payload = await request.body()
    
    # Verify Signature
    if LEMON_WEBHOOK_SECRET and x_signature:
        digest = hmac.new(LEMON_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, x_signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

    import json
    try:
        event = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid payload")
        
    event_name = event.get('meta', {}).get('event_name')
    data = event.get('data', {})
    
    custom_data = event.get('meta', {}).get('custom_data', {})
    user_id = custom_data.get('user_id')
    
    if event_name == 'subscription_created':
        handle_subscription_created(data, user_id, db)
    elif event_name in ['subscription_updated', 'subscription_cancelled', 'subscription_expired']:
        handle_subscription_updated(data, user_id, db)
        
    return {"status": "success"}


def handle_subscription_created(data: dict, user_id: str, db: Session):
    """Handle successful checkout via LemonSqueezy."""
    if not user_id:
        return
        
    attributes = data.get('attributes', {})
    product_name = attributes.get('product_name', '').lower()
    
    tier = SubscriptionTier.FREE
    if 'enterprise' in product_name:
        tier = SubscriptionTier.ENTERPRISE
    elif 'pro' in product_name:
        tier = SubscriptionTier.PRO
        
    user = db.query(User).filter(User.id == int(user_id)).with_for_update().first()
    if user:
        user.subscription_tier = tier
        user.stripe_customer_id = str(attributes.get('customer_id'))
        user.stripe_subscription_id = str(data.get('id'))
        db.commit()
        logger.info(f"User {user_id} upgraded to {tier} via Lemon Squeezy")


def handle_subscription_updated(data: dict, user_id: str, db: Session):
    """Handle Lemon Squeezy subscription alterations."""
    attributes = data.get('attributes', {})
    status = attributes.get('status')
    
    if not user_id:
        return
        
    user = db.query(User).filter(User.id == int(user_id)).with_for_update().first()
    if user:
        if status in ['expired', 'cancelled']:
            user.subscription_tier = SubscriptionTier.FREE
            user.stripe_subscription_id = None
            db.commit()
            logger.info(f"User {user.id} downgraded to FREE due to subscription cancellation (Lemon Squeezy)")

def cancel_lemonsqueezy_subscription(subscription_id: str):
    """Hits the Lemon Squeezy API to officially cancel an active subscription."""
    import requests
    if not LEMON_API_KEY or not subscription_id:
        return
        
    # Standard implementation: DELETE /v1/subscriptions/:id
    url = f"https://api.lemonsqueezy.com/v1/subscriptions/{subscription_id}"
    headers = {
        "Accept": "application/vnd.api+json",
        "Authorization": f"Bearer {LEMON_API_KEY}"
    }
    try:
        response = requests.delete(url, headers=headers, timeout=5)
        response.raise_for_status()
        logger.info(f"Successfully cancelled Lemon Squeezy subscription: {subscription_id}")
    except Exception as e:
        logger.error(f"Failed to cancel Lemon Squeezy subscription {subscription_id}: {e}")
