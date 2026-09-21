import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sqlite3
from app.core.database import get_engine, Base
import app.models  # load all models

engine = get_engine()
conn = sqlite3.connect('medikiosk_dev.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
existing_tables = set(r[0] for r in cursor.fetchall())

model_tables = set(Base.metadata.tables.keys())
missing_tables = model_tables - existing_tables
print('Missing tables:', missing_tables)

for table_name, table in Base.metadata.tables.items():
    if table_name in existing_tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        db_cols = set(c[1] for c in cursor.fetchall())
        model_cols = set(c.name for c in table.columns)
        missing_cols = model_cols - db_cols
        if missing_cols:
            print(f"Table '{table_name}' is missing columns:", missing_cols)

conn.close()
