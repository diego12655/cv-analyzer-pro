"""
CV Analyzer Pro - Backend con sistema de códigos de acceso
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
import anthropic
import json
import os
from dotenv import load_dotenv
import PyPDF2
import io

# Importar módulos locales
from database import engine, get_db, Base
from models import AccessCode, Session as DBSession, CVAnalysis
from auth import generate_access_code, generate_session_token, create_jwt_token, verify_jwt_token

# Cargar variables de entorno
load_dotenv()

# Crear tablas en la base de datos
Base.metadata.create_all(bind=engine)

# Crear app
app = FastAPI(title="CV Analyzer API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cv-analyzer-pro-alpha.vercel.app",  # <--- Tu nueva URL de Vercel
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cliente de Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
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

class GenerateCodesRequest(BaseModel):
    quantity: int = 1
    credits: int = 5

class SessionInfo(BaseModel):
    credits_remaining: int
    analyses_count: int

class AnalysisResult(BaseModel):
    name: str
    email: str = None
    phone: str = None
    score: float
    strengths: list
    improvements: list

# =====================================================
# FUNCIONES HELPER
# =====================================================

def get_current_session(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Obtener sesión actual desde el token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    
    token = authorization.replace("Bearer ", "")
    
    # Verificar token JWT
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    
    # Buscar sesión
    session_id = payload.get("session_id")
    session = db.query(DBSession).filter(DBSession.id == session_id).first()
    
    if not session:
        raise HTTPException(status_code=401, detail="Sesión no encontrada")
    
    return session

# =====================================================
# ENDPOINTS DE AUTENTICACIÓN
# =====================================================

@app.post("/api/validate-code", response_model=CodeValidationResponse)
async def validate_code(data: CodeValidation, db: Session = Depends(get_db)):
    """Validar código de acceso"""
    
    # Buscar código
    access_code = db.query(AccessCode).filter(AccessCode.code == data.code.upper()).first()
    
    if not access_code:
        return CodeValidationResponse(
            valid=False,
            message="Código no válido"
        )
    
    if access_code.used:
        # Si ya fue usado, buscar la sesión existente
        existing_session = db.query(DBSession).filter(
            DBSession.access_code_id == access_code.id
        ).first()
        
        if existing_session:
            # Generar nuevo token para la sesión existente
            token = create_jwt_token({"session_id": existing_session.id})
            
            return CodeValidationResponse(
                valid=True,
                token=token,
                credits=existing_session.credits_remaining,
                message="Sesión recuperada"
            )
    
    # Crear nueva sesión
    session_token = generate_session_token()
    new_session = DBSession(
        access_code_id=access_code.id,
        session_token=session_token,
        credits_remaining=access_code.credits
    )
    
    db.add(new_session)
    access_code.used = True
    db.commit()
    db.refresh(new_session)
    
    # Crear JWT token
    token = create_jwt_token({"session_id": new_session.id})
    
    return CodeValidationResponse(
        valid=True,
        token=token,
        credits=new_session.credits_remaining,
        message="Código validado correctamente"
    )

@app.get("/api/session-info", response_model=SessionInfo)
async def get_session_info(
    current_session: DBSession = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """Obtener información de la sesión actual"""
    
    analyses_count = db.query(CVAnalysis).filter(
        CVAnalysis.session_id == current_session.id
    ).count()
    
    return SessionInfo(
        credits_remaining=current_session.credits_remaining,
        analyses_count=analyses_count
    )

# =====================================================
# ENDPOINTS DE ADMIN
# =====================================================

@app.post("/api/admin/generate-codes")
async def generate_codes(
    data: GenerateCodesRequest,
    admin_key: str = Header(None),
    db: Session = Depends(get_db)
):
    """Generar códigos de acceso (solo admin)"""
    
    # Verificar clave de admin
    if admin_key != "mi-clave-admin-super-secreta-123":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    codes = []
    for _ in range(data.quantity):
        code = generate_access_code()
        
        new_code = AccessCode(
            code=code,
            credits=data.credits
        )
        
        db.add(new_code)
        codes.append(code)
    
    db.commit()
    
    return {
        "success": True,
        "codes": codes,
        "quantity": data.quantity,
        "credits_per_code": data.credits
    }

@app.get("/api/admin/codes")
async def list_codes(
    admin_key: str = Header(None),
    db: Session = Depends(get_db)
):
    """Listar todos los códigos (solo admin)"""
    
    if admin_key != "mi-clave-admin-super-secreta-123":
        raise HTTPException(status_code=403, detail="No autorizado")
    
    codes = db.query(AccessCode).all()
    
    result = []
    for code in codes:
        session = db.query(DBSession).filter(
            DBSession.access_code_id == code.id
        ).first()
        
        result.append({
            "code": code.code,
            "credits": code.credits,
            "used": code.used,
            "credits_remaining": session.credits_remaining if session else code.credits,
            "created_at": code.created_at.isoformat()
        })
    
    return {"codes": result}

# =====================================================
# ENDPOINTS DE ANÁLISIS
# =====================================================

@app.post("/api/analyze")
async def analyze_cv(
    file: UploadFile = File(...),
    current_session: DBSession = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """Analizar un CV (requiere autenticación)"""
    
    # Verificar créditos
    if current_session.credits_remaining <= 0:
        raise HTTPException(
            status_code=403,
            detail="No tienes créditos disponibles. El código ha expirado."
        )
    
    # Validar tipo de archivo
    file_extension = file.filename.split('.')[-1].lower()
    if file_extension not in ['pdf', 'jpg', 'jpeg', 'png', 'txt']:
        raise HTTPException(400, "Formato no válido. Usa PDF, JPG, PNG o TXT")
    
    # Leer archivo
    file_content = await file.read()
    
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(400, "Archivo muy grande. Máximo 10MB")
    
    # Determinar media type
    media_types = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'txt': 'text/plain'
    }
    media_type = media_types.get(file_extension)
    
    # Prompt para Claude
    prompt = """Analiza este CV y responde SOLO con un JSON (sin markdown) con esta estructura:

{
  "nombre_completo": "string",
  "email": "string o null",
  "telefono": "string o null",
  "score_general": 85,
  "fortalezas": [
    "Fortaleza 1",
    "Fortaleza 2",
    "Fortaleza 3"
  ],
  "mejoras": [
    "Sugerencia 1",
    "Sugerencia 2",
    "Sugerencia 3"
  ]
}

El score debe ser de 0-100. Sé específico en fortalezas y mejoras."""

    # Llamar a Claude
    try:
        if media_type == 'application/pdf':
            pdf_file = io.BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
            
            if not text_content.strip():
                raise HTTPException(400, "No se pudo extraer texto del PDF")
            
            message = claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": f"Analiza este CV:\n\n{text_content}\n\n{prompt}"
                    }
                ]
            )
        
        elif media_type in ['image/jpeg', 'image/png']:
            import base64
            base64_content = base64.standard_b64encode(file_content).decode('utf-8')
            
            content_block = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_content
                }
            }
            
            message = claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            content_block,
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
            )
        
        elif media_type == 'text/plain':
            text_content = file_content.decode('utf-8', errors='ignore')
            
            message = claude_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": f"Analiza este CV:\n\n{text_content}\n\n{prompt}"
                    }
                ]
            )
        
        else:
            raise HTTPException(400, "Formato no soportado")
        
        # Parsear respuesta
        response_text = message.content[0].text
        
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        
        data = json.loads(response_text.strip())
        
        # Guardar análisis en BD
        new_analysis = CVAnalysis(
            session_id=current_session.id,
            candidate_name=data.get("nombre_completo", "Sin nombre"),
            email=data.get("email"),
            phone=data.get("telefono"),
            overall_score=data.get("score_general", 0),
            full_data=json.dumps(data)
        )
        
        db.add(new_analysis)
        
        # Descontar crédito
        current_session.credits_remaining -= 1
        
        db.commit()
        
        # Retornar resultado
        return {
            "success": True,
            "name": data.get("nombre_completo", "Sin nombre"),
            "email": data.get("email"),
            "phone": data.get("telefono"),
            "score": data.get("score_general", 0),
            "strengths": data.get("fortalezas", []),
            "improvements": data.get("mejoras", []),
            "credits_remaining": current_session.credits_remaining
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error al analizar CV: {str(e)}")

@app.get("/api/analyses")
async def get_analyses(
    current_session: DBSession = Depends(get_current_session),
    db: Session = Depends(get_db)
):
    """Obtener historial de análisis"""
    
    analyses = db.query(CVAnalysis).filter(
        CVAnalysis.session_id == current_session.id
    ).order_by(CVAnalysis.created_at.desc()).all()
    
    return {
        "analyses": [
            {
                "id": a.id,
                "candidate_name": a.candidate_name,
                "score": a.overall_score,
                "created_at": a.created_at.isoformat()
            }
            for a in analyses
        ]
    }

# =====================================================
# ENDPOINTS BÁSICOS
# =====================================================

@app.get("/")
async def root():
    return {
        "message": "CV Analyzer API",
        "status": "running",
        "version": "2.0 - Access Codes System"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

# =====================================================
# EJECUTAR SERVIDOR
# =====================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"""
    ╔══════════════════════════════════════╗
    ║   CV Analyzer API - CORRIENDO ✅     ║
    ║   http://localhost:{port}              ║
    ║   Docs: http://localhost:{port}/docs   ║
    ╚══════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)