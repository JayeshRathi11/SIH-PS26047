import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from app.core.database import get_engine, Base
import app.models  # Ensures all models are registered

def migrate():
    engine = get_engine()
    db_path = Path(__file__).resolve().parent.parent / "medikiosk_dev.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check patients table for emergency_contact_phone
    cursor.execute("PRAGMA table_info(patients);")
    columns = [c[1] for c in cursor.fetchall()]
    if "emergency_contact_phone" not in columns:
        print("Adding column 'emergency_contact_phone' to 'patients' table...")
        cursor.execute("ALTER TABLE patients ADD COLUMN emergency_contact_phone VARCHAR(20);")
        conn.commit()
        print("Column 'emergency_contact_phone' added successfully.")
    else:
        print("Column 'emergency_contact_phone' already exists in 'patients'.")
    
    conn.close()

    # Create any missing tables (e.g. clinician_red_flag_feedbacks)
    print("Ensuring all model tables exist via Base.metadata.create_all...")
    Base.metadata.create_all(bind=engine)
    print("Database migration completed successfully.")

if __name__ == "__main__":
    migrate()
