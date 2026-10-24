import sqlite3

def init_demo_db():
    conn = sqlite3.connect("company.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS employees")
    cursor.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary REAL NOT NULL
        )
    """)
    sample_data = [
        (1, "Alice Smith", "Engineering", 95000),
        (2, "Bob Jones", "Marketing", 62000),
        (3, "Charlie Brown", "Engineering", 82000),
        (4, "Diana Prince", "Finance", 105000),
        (5, "Evan Wright", "Marketing", 54000)
    ]
    cursor.executemany("INSERT INTO employees VALUES (?, ?, ?, ?)", sample_data)
    conn.commit()
    conn.close()
    print("✅ Created company.db with sample employees table.")

if __name__ == "__main__":
    init_demo_db()
