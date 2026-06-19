from app import db, create_app
from app.models.patient import User, VaultProfile, VaultAccess, Document, QRScanLog

app = create_app()

with app.app_context():
    try:
        # Delete dependent tables first in correct order
        num_docs = db.session.query(Document).delete()
        num_logs = db.session.query(QRScanLog).delete()
        num_access = db.session.query(VaultAccess).delete()
        num_vaults = db.session.query(VaultProfile).delete()
        num_users = db.session.query(User).delete()
        
        db.session.commit()
        print(f"CLEARED: Wiped database records successfully.")
        
        print(f" - Documents: {num_docs}")
        print(f" - Logs: {num_logs}")
        print(f" - Access: {num_access}")
        print(f" - Vaults: {num_vaults}")
        print(f" - Users: {num_users}")
        
    except Exception as e:
        db.session.rollback()
        print(f"FAILED: {e}")