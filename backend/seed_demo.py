from app import create_app, db
from app.models.patient import User, VaultProfile, VaultAccess, Document, QRScanLog
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Clean existing data first to prevent key conflicts
    db.session.query(Document).delete()
    db.session.query(QRScanLog).delete()
    db.session.query(VaultAccess).delete()
    db.session.query(VaultProfile).delete()
    db.session.query(User).delete()
    db.session.commit()

    print("Wiped existing database test records.")

    # Create demo primary user
    user = User(
        username="kostuk",
        password_hash=generate_password_hash("1234"),
        role="family_member"
    )
    db.session.add(user)
    db.session.flush()

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
    db.session.add(kostuk_vault)
    db.session.flush()

    # Link access rights
    db.session.add(VaultAccess(user_id=user.id, vault_id=kostuk_vault.id, access_type="owner"))
    
    db.session.commit()
    print("SUCCESS: Seeded Kostuk Dey's user and vault profile perfectly!")