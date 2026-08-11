from app.database import SessionLocal, engine, Base
from app.models.patient import User, VaultProfile, VaultAccess, Document, QRScanLog, HealthMetric
from werkzeug.security import generate_password_hash

# Ensure all tables exist
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    # Clean existing data first
    db.query(HealthMetric).delete()
    db.query(Document).delete()
    db.query(QRScanLog).delete()
    db.query(VaultAccess).delete()
    db.query(VaultProfile).delete()
    db.query(User).delete()
    db.commit()

    print("Wiped existing database test records.")

    # Create demo primary user
    user = User(
        username="kostuk",
        password_hash=generate_password_hash("1234"),
        role="family_member"
    )
    db.add(user)
    db.flush()

    # Create Kostuk's vault
    kostuk_vault = VaultProfile(
        owner_user_id=user.id,
        relation="Self",
        full_name="Kostuk Dey",
        blood_group="B+",
        allergies="Peanuts, Penicillin",
        medical_conditions="History of severe headaches",
        medications="Flexon (as needed)",
        personal_contact="+918604530535",
        address="123 Main St, Kanpur, UP",
        emergency_1_name="Parent 1",
        emergency_1_relation="Father",
        emergency_1_phone="+919876543210",
        emergency_2_name="Parent 2",
        emergency_2_relation="Mother",
        emergency_2_phone="+919876543211",
        emergency_3_name="Friend",
        emergency_3_relation="Friend",
        emergency_3_phone="+919876543212",
        is_emergency_ready=True
    )
    db.add(kostuk_vault)
    db.flush()

    # Link access rights
    db.add(VaultAccess(user_id=user.id, vault_id=kostuk_vault.id, access_type="owner"))
    db.commit()
    print("SUCCESS: Seeded Kostuk Dey's user and vault profile perfectly!")
finally:
    db.close()