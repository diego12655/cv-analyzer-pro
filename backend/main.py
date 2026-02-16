"""
CV Analyzer Pro - Backend B2B (Multi-CV + Ranking + Export)
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
import anthropic
import json
import os
import io
import pandas as pd
import secrets
from dotenv import load_dotenv
import PyPDF2

# Importar módulos locales
from database import engine, get_db, Base
from models import AccessCode, Session as DBSession, CVAnalysis
from auth import generate_access_code, generate_session_token, create_jwt_token, verify_jwt_token

# 1. Cargar variables de entorno
load_dotenv()

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CV Analyzer API - B2B Edition")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://cv-analyzer-pro-alpha.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Configuración de Claves (Corregido para coincidir con tu .env) 
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ADMIN_SECRET_KEY = os.getenv("ADMIN_KEY") 
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# =====================================================
# MODELOS PYDANTIC
# =====================================================

class CodeValidation(BaseModel):
    code: str

class CodeValidationResponse(BaseModel):
    valid: bool
    token: str = None
    credits: int = 0
    message: str = ""

class ExportData(BaseModel):
    ranking: List[dict]

# =====================================================
# DEPENDENCIAS
# =====================================================

def get_current_session(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    
    token = authorization.replace("Bearer ", "")
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    session = db.query(DBSession).filter(DBSession.id == payload.get("session_id")).first()
    if not session:
        raise HTTPException(status_code=401, detail="Sesión no encontrada")
    
    return session

# =====================================================
# ENDPOINTS DE AUTENTICACIÓN Y SESIÓN
# =====================================================

@app.post("/api/validate-code", response_model=CodeValidationResponse)
async def validate_code(data: CodeValidation, db: Session = Depends(get_db)):
    access_code = db.query(AccessCode).filter(AccessCode.code == data.code.upper()).first()
    
    if not access_code:
        return CodeValidationResponse(valid=False, message="Código no válido")
    
    existing_session = db.query(DBSession).filter(DBSession.access_code_id == access_code.id).first()
    
    if existing_session:
        token = create_jwt_token({"session_id": existing_session.id})
        return CodeValidationResponse(valid=True, token=token, credits=existing_session.credits_remaining, message="Sesión recuperada")
    
    new_session = DBSession(access_code_id=access_code.id, session_token=generate_session_token(), credits_remaining=access_code.credits)
    db.add(new_session)
    access_code.used = True
    db.commit()
    db.refresh(new_session)
    
    token = create_jwt_token({"session_id": new_session.id})
    return CodeValidationResponse(valid=True, token=token, credits=new_session.credits_remaining)

@app.get("/api/session-info")
async def get_session_info(current_session: DBSession = Depends(get_current_session)):
    return {
        "credits_remaining": current_session.credits_remaining,
        "session_id": current_session.id
    }

# =====================================================
# PROCESAMIENTO Y EXPORTACIÓN
# =====================================================

@app.post("/api/analyze-batch")
async def analyze_batch(
    files: List[UploadFile] = File(...),
    job_description: str = Form(...),
    current_session: DBSession = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    num_files = len(files)
    if current_session.credits_remaining < num_files:
        raise HTTPException(status_code=403, detail=f"Créditos insuficientes.")

    all_cvs_data = ""
    for idx, file in enumerate(files):
        content = await file.read()
        text = ""
        if file.filename.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        else:
            text = content.decode('utf-8', errors='ignore')
        
        all_cvs_data += f"\n--- CANDIDATO #{idx+1} (Archivo: {file.filename}) ---\n{text}\n"

    prompt = f"""
    Eres un Headhunter Senior. Evalúa estos {num_files} CVs para la siguiente vacante:
    DESCRIPCIÓN DEL PUESTO: {job_description}
    DATOS DE LOS CANDIDATOS: {all_cvs_data}

    TAREA: Genera un ranking profesional. Responde ÚNICAMENTE con un JSON puro:
    {{
      "ranking": [
        {{ "nombre": "Nombre Real", "puntaje": 0-100, "ajuste": "Excelente/Bueno/Regular", "razon_si": "...", "razon_no": "..." }}
      ],
      "conclusion_global": "..."
    }}
    """

    try:
        message = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        raw_text = message.content[0].text
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0]
        
        analysis_data = json.loads(raw_text.strip())

        current_session.credits_remaining -= num_files
        db.commit()

        return {
            "success": True,
            "ranking": analysis_data["ranking"],
            "conclusion": analysis_data["conclusion_global"],
            "credits_remaining": current_session.credits_remaining
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error: {str(e)}")

@app.post("/api/export-excel")
async def export_excel(data: ExportData, current_session: DBSession = Depends(get_current_session)):
    try:
        df = pd.DataFrame(data.ranking)
        column_mapping = {
            "nombre": "Candidato",
            "puntaje": "Puntaje (0-100)",
            "ajuste": "Nivel de Ajuste",
            "razon_si": "Fortalezas",
            "razon_no": "Riesgos/Debilidades"
        }
        df = df.rename(columns=column_mapping)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Ranking')
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=ranking_talento.xlsx"}
        )
    except Exception as e:
        raise HTTPException(500, f"Error al generar Excel: {str(e)}")

# =====================================================
# ADMIN (RESTAURADO Y PROTEGIDO)
# =====================================================

@app.post("/api/admin/generate-codes")
async def generate_codes(
    quantity: int = 1, 
    credits: int = 5, 
    admin_key: str = Header(..., alias="X-Admin-Key"), # Los '...' lo hacen obligatorio 
    db: Session = Depends(get_db)
):
    # 1. BLOQUEO DE SEGURIDAD REAL
    if not ADMIN_SECRET_KEY or admin_key != ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=403, 
            detail="Acceso denegado: Clave incorrecta"
        )
    
    # 2. GENERACIÓN REAL (Ya no hay "debug_info")
    codes = []
    for _ in range(quantity):
        code = generate_access_code()
        db.add(AccessCode(code=code, credits=credits))
        codes.append(code)
    
    db.commit() # Esto guarda los cambios en cvanalyzer.db 
    
    return {
        "status": "success",
        "codes": codes # Aquí verás tus códigos nuevos 
    }
    
    # 2. Generación real de códigos en la base de datos 
    codes = []
    for _ in range(quantity):
        code = generate_access_code()
        db.add(AccessCode(code=code, credits=credits))
        codes.append(code)
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Se han generado {len(codes)} códigos con éxito",
        "codes": codes
    }

@app.get("/")
async def root():
    return {"message": "CV Analyzer B2B Engine Running", "version": "3.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))