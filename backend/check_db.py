import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres.iexgbjrgyqxjocidztwz:Ashok%409453$@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"

try:
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Executing query...")
    result = session.execute("SELECT id, session_id, student_id, frame_path FROM detections ORDER BY id DESC LIMIT 5").fetchall()
    print("Recent detections:")
    for row in result:
        print(f"ID: {row[0]}, Session: {row[1]}, Student: {row[2]}, Frame Path: {row[3]}")
    
except Exception as e:
    print("Error:", e)
