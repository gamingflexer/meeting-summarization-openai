from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Optional
 
dbcon = 'sqlite:///fastapidb.sqlite3'
 
engine = create_engine(dbcon)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
Base.metadata.create_all(bind=engine)
 
 
DATABASE_URL: Optional[str] = None
SECRET_KEY: Optional[str] = "cairocoders"
 
def sess_db():
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()