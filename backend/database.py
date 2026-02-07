"""
Configuración de base de datos
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# URL de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL")

# Si es Railway, reemplazar postgres:// por postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Si no hay DATABASE_URL, usar SQLite local
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./cvanalyzer.db"
    
# Crear engine
engine = create_engine(DATABASE_URL)

# Crear SessionLocal
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para modelos
Base = declarative_base()

# Dependency para obtener DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()