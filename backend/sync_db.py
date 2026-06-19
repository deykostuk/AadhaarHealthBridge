from app import create_app, db

app = create_app()
with app.app_context():
    try:
        print("Wiping existing structures to drop cached NOT NULL constraints...")
        
        # Drop the orphaned patient_metrics table first if it exists
        db.session.execute(db.text("DROP TABLE IF EXISTS patient_metrics CASCADE;"))
        db.session.commit()
        
        # 1. Drop old relational schemas completely
        db.drop_all()
        
        print("Rebuilding clean database tables from modified Patient models...")
        
        # 2. Re-create all tables based on our new design
        db.create_all()
        
        print("SUCCESS: PostgreSQL database tables and constraints rebuilt perfectly!")
    except Exception as e:
        db.session.rollback()
        print(f"Rebuild Engine Exception: {str(e)}")