"""
Seed admin user directly using passlib with bcrypt error suppressed.
Run from: c:\\Projects\\RTP\\backend\\
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Suppress passlib bcrypt warning
import warnings
warnings.filterwarnings("ignore")

from passlib.context import CryptContext
from backend.database import SessionLocal, User, Base, engine

# Ensure tables exist
Base.metadata.create_all(bind=engine)

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "mirai2024")

db = SessionLocal()
try:
    existing = db.query(User).filter(User.username == ADMIN_USER).first()
    if existing:
        print(f"Admin '{ADMIN_USER}' already exists.")
    else:
        hashed = pwd.hash(ADMIN_PASS)
        admin = User(username=ADMIN_USER, hashed_password=hashed, role="admin", disabled=False)
        db.add(admin)
        db.commit()
        print(f"✅ Admin '{ADMIN_USER}' created successfully.")

    all_users = db.query(User).all()
    print(f"Total users in DB: {len(all_users)}")
    for u in all_users:
        print(f"  - {u.username} ({u.role})")
finally:
    db.close()
