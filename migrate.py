import sqlite3
import traceback

def migrate_database():
    db_file = 'bot_data.db'
    print(f"Starting migration for database: {db_file}")

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # Check if the 'params' column already exists in the 'orders' table
        cursor.execute("PRAGMA table_info(orders)")
        columns = [info[1] for info in cursor.fetchall()]

        if 'params' not in columns:
            print("Column 'params' not found in 'orders' table. Adding it...")
            # Add the 'params' column. It will be TEXT and can be NULL.
            cursor.execute("ALTER TABLE orders ADD COLUMN params TEXT")
            conn.commit()
            print("Column 'params' added successfully.")
        else:
            print("Column 'params' already exists in 'orders' table. No migration needed.")

        conn.close()
        print("Migration process completed successfully.")

    except sqlite3.Error as e:
        print(f"An error occurred during database migration: {e}")
        print(traceback.format_exc())

if __name__ == '__main__':
    migrate_database()
