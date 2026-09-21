#!/usr/bin/env python3
"""
MediKiosk Demo Data Seeding Script

Populates demo accounts and realistic clinical encounters:
- Doctor: doctor@aiia.gov.in / doctor123
- Staff: staff@aiia.gov.in / staff123
- Admin: admin@aiia.gov.in / admin123
- 4 OPD patients (Emergency chest pain, Metformin contradiction, AYUSH Mandagni, Migraine completed)

Usage:
  PYTHONPATH=backend python backend/scripts/seed_demo_data.py
"""
import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# If DATABASE_URL is not set, default to a local SQLite database for ease of demo/local testing
if not os.environ.get("DATABASE_URL") and not os.environ.get("POSTGRES_DB"):
    os.environ["DATABASE_URL"] = f"sqlite:///{backend_dir / 'medikiosk_dev.db'}"

from app.core.database import get_session_factory, get_engine, Base
from app.api.demo import seed_database_demo_data
import app.models  # Ensure all models are registered


def main():
    print("=" * 60)
    print(" MediKiosk: Seeding Demo Clinical & Authentication Data")
    print("=" * 60)

    # Ensure tables exist
    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    session_factory = get_session_factory()
    db = session_factory()
    try:
        result = seed_database_demo_data(db)
        print("\n[OK] Seeding Completed Successfully!")
        print("\n--- Demo Accounts ---")
        for u in result["users"]:
            print(f"  * {u['role']:<8}: {u['email']}")
        print("  Default Password: doctor123 / staff123 / admin123")

        print("\n--- Seeded OPD Queue ---")
        for p in result["patients"]:
            print(f"  * Token {p['token']:<6}: {p['name']:<18} [{p['priority']:<9}] - Status: {p['status']}")

        print("\nReady! You can now log into Doctor Dashboard (screen5) or launch Analytics (screen6).")
        print("=" * 60)
    finally:
        db.close()


if __name__ == "__main__":
    main()
