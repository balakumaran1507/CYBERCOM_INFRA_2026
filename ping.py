"""
Script for checking that a database server is available.
Essentially a cross-platform, database agnostic mysqladmin.

Enhanced with:
- Retry logic with exponential backoff
- Verification that database can accept queries (not just TCP connection)
- Extended post-connection wait for fresh database initialization
"""
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

from CTFd.config import Config

url = make_url(Config.DATABASE_URL)

# Ignore sqlite databases
if url.drivername.startswith("sqlite"):
    exit(0)

# Null out the database so raw_connection doesnt error if it doesnt exist
# CTFd will create the database if it doesnt exist
url_without_db = url._replace(database=None)

# Wait for the database server to be available
engine = create_engine(url_without_db)
print(f"[DB PING] Waiting for {url.host} to be ready...")

max_retries = 60  # 60 retries = ~2 minutes max wait
retry_count = 0
backoff = 1

while retry_count < max_retries:
    try:
        conn = engine.raw_connection()
        conn.close()
        break
    except Exception as e:
        retry_count += 1
        if retry_count >= max_retries:
            print(f"[DB PING] ERROR: Database connection failed after {max_retries} retries")
            print(f"[DB PING] Last error: {e}")
            sys.exit(1)

        print(f"[DB PING] Waiting {backoff}s for database connection (attempt {retry_count}/{max_retries})")
        time.sleep(backoff)

        # Exponential backoff (1s, 2s, 4s, then cap at 5s)
        backoff = min(backoff * 2, 5)

print(f"[DB PING] ✅ {url.host} TCP connection established")

# CRITICAL: Additional wait for fresh database initialization
# MySQL/MariaDB accepts connections before InnoDB is fully initialized
# This prevents "Table doesn't exist" errors on fresh clones
print("[DB PING] Waiting for database to be fully initialized...")

# Try to verify database can execute queries
test_engine = create_engine(url_without_db)
for attempt in range(10):
    try:
        with test_engine.connect() as conn:
            # Simple query to verify database is accepting commands
            conn.execute(text("SELECT 1"))
        print(f"[DB PING] ✅ Database is accepting queries")
        break
    except Exception as e:
        if attempt == 9:
            print(f"[DB PING] WARNING: Database query test failed, proceeding anyway: {e}")
        time.sleep(1)

# Extended wait for fresh database initialization
# This is critical for fresh clones where MariaDB needs time to:
# - Initialize system tables
# - Set up InnoDB
# - Prepare for DDL statements
print("[DB PING] Post-connection stabilization wait (5 seconds)...")
time.sleep(5)

print(f"[DB PING] ✅ {url.host} is ready for migrations")
