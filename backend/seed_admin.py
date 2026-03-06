from app.db import SessionLocal
from app.models.models import User
from app.services.auth_service import get_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_admin():
    db = SessionLocal()
    try:
        admin_email = "hamza@autotube.com"
        existing = db.query(User).filter(User.email == admin_email).first()
        if not existing:
            logger.info("Seeding enterprise admin user...")
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash("Enterprise2026!"),
                subscription_tier="enterprise",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            logger.info("Admin user 'hamza@autotube.com' created successfully!")
        else:
            logger.info("Admin user already exists.")
    except Exception as e:
        logger.error(f"Failed to seed admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
