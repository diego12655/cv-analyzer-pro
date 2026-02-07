import React, { useState, useEffect } from 'react';
import { Upload, FileText, Star, CheckCircle, AlertCircle, LogOut, Zap } from 'lucide-react';
import Login from './Login';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [credits, setCredits] = useState(0);
  const [selectedFile, setSelectedFile] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  // Verificar si hay token al cargar
  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    const savedCredits = localStorage.getItem('credits');
    
    if (savedToken) {
      setToken(savedToken);
      setCredits(parseInt(savedCredits) || 0);
      setIsAuthenticated(true);
      loadSessionInfo(savedToken);
    }
  }, []);

  const loadSessionInfo = async (authToken) => {
    try {
      const response = await fetch(`${API_URL}/api/session-info`, {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setCredits(data.credits_remaining);
        localStorage.setItem('credits', data.credits_remaining);
      }
    } catch (err) {
      console.error('Error loading session:', err);
    }
  };

  const handleLoginSuccess = (newToken, newCredits) => {
    setToken(newToken);
    setCredits(newCredits);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('credits');
    setToken(null);
    setCredits(0);
    setIsAuthenticated(false);
    setResult(null);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setError('');
      setResult(null);
    }
  };

  const analyzeCV = async () => {
    if (!selectedFile) return;

    setAnalyzing(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch(`${API_URL}/api/analyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Error al analizar el CV');
      }

      const data = await response.json();
      setResult(data);
      setCredits(data.credits_remaining);
      localStorage.setItem('credits', data.credits_remaining);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const reset = () => {
    setSelectedFile(null);
    setResult(null);
    setError('');
  };

  // Si no está autenticado, mostrar login
  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  // Vista principal (igual que antes pero con créditos)
  return (
    <div className="App">
      {/* Badge de créditos */}
      <div className={`credits-badge ${credits <= 1 ? 'low' : ''}`}>
        <Zap size={18} />
        {credits} crédito{credits !== 1 ? 's' : ''} restante{credits !== 1 ? 's' : ''}
      </div>

      {/* Botón de logout */}
      <button onClick={handleLogout} className="logout-btn">
        <LogOut size={18} />
      </button>

      <div className="container">
        <header className="header">
          <div className="logo">
            <FileText size={40} />
          </div>
          <h1>CV Analyzer Pro</h1>
          <p>Analiza CVs con Inteligencia Artificial</p>
        </header>

        {!result ? (
          <div className="upload-section">
            <div className="upload-box" onClick={() => document.getElementById('fileInput').click()}>
              <Upload size={64} />
              <h2>Sube tu CV</h2>
              <p>PDF, JPG, PNG o TXT (Máx. 10MB)</p>
              <input
                id="fileInput"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.txt"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
            </div>

            {selectedFile && (
              <div className="file-preview">
                <FileText size={24} />
                <div>
                  <p className="file-name">{selectedFile.name}</p>
                  <p className="file-size">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                </div>
                <button onClick={() => setSelectedFile(null)} className="btn-remove">✕</button>
              </div>
            )}

            {error && (
              <div className="error-box">
                <AlertCircle size={20} />
                <p>{error}</p>
              </div>
            )}

            {selectedFile && (
              <button onClick={analyzeCV} disabled={analyzing || credits <= 0} className="btn-analyze">
                {analyzing ? '⏳ Analizando...' : credits <= 0 ? '❌ Sin créditos' : '🚀 Analizar CV'}
              </button>
            )}

            {credits <= 0 && (
              <div className="error-box" style={{marginTop: '20px'}}>
                <AlertCircle size={20} />
                <p>Has agotado tus créditos. Solicita un nuevo código de acceso.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="results">
            <div className="result-header">
              <h2>✅ Análisis Completado</h2>
              <button onClick={reset} className="btn-secondary">Analizar Otro</button>
            </div>

            <div className="score-section">
              <div className="score-circle">
                <div className="score-value">{result.score}</div>
                <div className="score-label">de 100</div>
              </div>
            </div>

            <div className="info-grid">
              <div className="info-card">
                <h3>Nombre</h3>
                <p>{result.name}</p>
              </div>
              {result.email && (
                <div className="info-card">
                  <h3>Email</h3>
                  <p>{result.email}</p>
                </div>
              )}
              {result.phone && (
                <div className="info-card">
                  <h3>Teléfono</h3>
                  <p>{result.phone}</p>
                </div>
              )}
            </div>

            <div className="section">
              <h3><CheckCircle size={20} /> Fortalezas</h3>
              <div className="list">
                {result.strengths.map((item, idx) => (
                  <div key={idx} className="list-item success">
                    <Star size={16} />
                    <p>{item}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="section">
              <h3><AlertCircle size={20} /> Sugerencias de Mejora</h3>
              <div className="list">
                {result.improvements.map((item, idx) => (
                  <div key={idx} className="list-item warning">
                    <AlertCircle size={16} />
                    <p>{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;