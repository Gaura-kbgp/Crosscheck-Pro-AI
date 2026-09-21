from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    db.execute(text("ALTER TYPE itemcategory ADD VALUE IF NOT EXISTS 'COMMERCIAL_CHARGE';"))
    db.commit()
    print("Postgres enum altered successfully!")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
