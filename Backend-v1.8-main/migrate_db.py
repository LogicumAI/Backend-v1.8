from sqlmodel import Session, text
from app.core.database import engine

def migrate_chat_table():
    with Session(engine) as session:
        # 1. First ensure all tables are created (especially the new V3 ones)
        # This is safe as create_all only creates missing tables
        import app.models
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(engine)
        print("Database schema synchronization complete.")

        # 2. Add user_id to chat table if missing
        try:
            session.exec(text("SELECT user_id FROM chat LIMIT 1"))
            print("user_id column already exists in chat table.")
        except Exception:
            print("Adding user_id column to chat table...")
            try:
                # Use TEXT for UUID compatibility in SQLite
                session.exec(text("ALTER TABLE chat ADD COLUMN user_id TEXT"))
                session.exec(text("CREATE INDEX IF NOT EXISTS ix_chat_user_id ON chat (user_id)"))
                session.commit()
                print("Column 'user_id' successfully added to 'chat' table.")
            except Exception as e:
                print(f"Migration error for 'chat' table: {e}")
                session.rollback()

        # 3. Final verification of all critical columns
        try:
             session.exec(text("SELECT user_id FROM project LIMIT 1"))
             print("Project table verified.")
        except Exception as e:
             print(f"Warning: Project table might be missing user_id: {e}")

if __name__ == "__main__":
    migrate_chat_table()
