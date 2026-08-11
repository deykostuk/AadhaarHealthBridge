from app.database import SessionLocal, engine, Base
from app.models.patient import User, VaultProfile, VaultAccess, Document, QRScanLog, HealthMetric

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    num_metrics = db.query(HealthMetric).delete()
    num_docs = db.query(Document).delete()
    num_logs = db.query(QRScanLog).delete()
    num_access = db.query(VaultAccess).delete()
    num_vaults = db.query(VaultProfile).delete()
    num_users = db.query(User).delete()
    
    db.commit()
    print("CLEARED: Wiped database records successfully.")
    print(f" - HealthMetrics: {num_metrics}")
    print(f" - Documents: {num_docs}")
    print(f" - Logs: {num_logs}")
    print(f" - Access: {num_access}")
    print(f" - Vaults: {num_vaults}")
    print(f" - Users: {num_users}")
except Exception as e:
    db.rollback()
    print(f"FAILED: {e}")
finally:
    db.close()