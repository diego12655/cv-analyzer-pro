"""
Modelos de base de datos
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base

class AccessCode(Base):
    """Códigos de acceso para usuarios"""
    __tablename__ = "access_codes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String, unique=True, index=True, nullable=False)
    credits = Column(Integer, default=5)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación con sesiones
    sessions = relationship("Session", back_populates="access_code")

class Session(Base):
    """Sesiones de usuario (un código puede tener una sesión)"""
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    access_code_id = Column(String, ForeignKey("access_codes.id"))
    session_token = Column(String, unique=True, index=True)
    credits_remaining = Column(Integer, default=5)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    access_code = relationship("AccessCode", back_populates="sessions")
    analyses = relationship("CVAnalysis", back_populates="session")

class CVAnalysis(Base):
    """Análisis de CVs realizados"""
    __tablename__ = "cv_analyses"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"))
    
    # Información del CV
    candidate_name = Column(String)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    # Scoring
    overall_score = Column(Float)
    
    # Datos completos en JSON
    full_data = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación
    session = relationship("Session", back_populates="analyses")