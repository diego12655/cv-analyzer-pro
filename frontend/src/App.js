import React, { useState, useEffect } from 'react';
import { 
  Upload, Star, AlertCircle, LogOut, Zap, 
  ListOrdered, LayoutDashboard, CheckCircle, Download, Loader2
} from 'lucide-react';
import Login from './Login';
import './App.css';

function App() {
  // --- ESTADOS ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [credits, setCredits] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [jobDescription, setJobDescription] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  // Cambiado a 127.0.0.1 para evitar problemas de DNS en local
  const API_URL = 'http://127.0.0.1:8000';

  // --- CARGA DE SESIÓN ---
  useEffect(() => {
    const savedToken = localStorage.getItem('token');
    if (savedToken) {
      setToken(savedToken);
      setIsAuthenticated(true);
      loadSessionInfo(savedToken);
    }
  }, []);

  const loadSessionInfo = async (authToken) => {
    try {
      const response = await fetch(`${API_URL}/api/session-info`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setCredits(data.credits_remaining);
      }
    } catch (err) {
      console.error("Error cargando créditos:", err);
    }
  };

  const handleLoginSuccess = (newToken, newCredits) => {
    setToken(newToken);
    setCredits(newCredits);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.clear();
    setToken(null);
    setIsAuthenticated(false);
    setResult(null);
  };

  // --- ACCIÓN: ANALIZAR ---
  const handleAnalyze = async () => {
    if (selectedFiles.length === 0 || !jobDescription) {
      setError('Por favor sube CVs y añade la descripción del puesto.');
      return;
    }

    setAnalyzing(true);
    setError('');
    
    const formData = new FormData();
    selectedFiles.forEach(file => formData.append('files', file));
    formData.append('job_description', jobDescription);

    try {
      const response = await fetch(`${API_URL}/api/analyze-batch`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      const data = await response.json();

      if (response.ok) {
        setResult(data);
        setCredits(data.credits_remaining);
      } else {
        setError(data.detail || 'Error en el análisis');
      }
    } catch (err) {
      setError('Error de conexión con el servidor. Verifica que FastAPI esté corriendo.');
    } finally {
      setAnalyzing(false);
    }
  };

  // --- ACCIÓN: EXPORTAR ---
  const handleExportExcel = async () => {
    if (!result || !result.ranking) return;
    setExporting(true);
    try {
      const response = await fetch(`${API_URL}/api/export-excel`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ ranking: result.ranking })
      });
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Ranking_CV_${new Date().getTime()}.xlsx`;
      a.click();
    } catch (err) {
      setError("No se pudo descargar el archivo Excel.");
    } finally {
      setExporting(false);
    }
  };

  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="app-container">
      {/* Navbar */}
      <nav className="navbar">
        <div className="nav-logo">
          <LayoutDashboard size={24} />
          <span><strong>zeptdocs</strong></span>
        </div>
        <div className="nav-actions">
          <div className="credits-display">
            <Zap size={16} fill="#fbbf24" color="#fbbf24" />
            <span>{credits} Créditos</span>
          </div>
          <button onClick={handleLogout} className="logout-btn">
            <LogOut size={18} /> Salir
          </button>
        </div>
      </nav>

      <div className="main-content">
        {!result ? (
          <div className="main-card">
            <div className="section-header">
              <h1><Star size={28} color="#6366f1" /> Nuevo Análisis</h1>
              <p>Sube los CVs de tus candidatos para compararlos.</p>
            </div>

            <div className="input-group">
              <label>Descripción de la Vacante y funciones a realizar</label>
              <textarea 
                className="custom-textarea"
                placeholder="Ej: Buscamos un experto en React..."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
            </div>

            <div className="input-group">
              <label>Subir CVs (PDF)</label>
              <div className="upload-zone" onClick={() => document.getElementById('f').click()}>
                <Upload size={32} color="#94a3b8" />
                <p>{selectedFiles.length > 0 ? `${selectedFiles.length} archivos seleccionados` : "Haz clic para seleccionar PDFs"}</p>
                <input id="f" type="file" multiple accept=".pdf" hidden onChange={(e) => setSelectedFiles(Array.from(e.target.files))} />
              </div>
            </div>

            {error && <div className="error-banner"><AlertCircle size={18} /> {error}</div>}

            <button className="btn-primary" onClick={handleAnalyze} disabled={analyzing}>
              {analyzing ? <Loader2 className="spinner" /> : "Iniciar Ranking Inteligente"}
            </button>
          </div>
        ) : (
          <div className="results-view">
            <div className="results-header">
              <div className="header-info">
                <h2><ListOrdered size={24} /> Ranking de Candidatos</h2>
              </div>
              <div className="header-actions">
                <button onClick={handleExportExcel} className="export-btn" disabled={exporting}>
                  {exporting ? <Loader2 className="spinner" size={18} /> : <Download size={18} />}
                  Exportar Excel
                </button>
                <button onClick={() => setResult(null)} className="btn-secondary">Nueva Búsqueda</button>
              </div>
            </div>

            <div className="table-wrapper">
              <table className="modern-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Nombre</th>
                    <th>Puntaje</th>
                    <th>Ajuste</th>
                    <th>Análisis IA</th>
                  </tr>
                </thead>
                <tbody>
                  {result.ranking?.map((c, i) => (
                    <tr key={i}>
                      <td>{i + 1}</td>
                      <td><strong>{c.nombre}</strong></td>
                      <td><span className="score-badge">{c.puntaje}/100</span></td>
                      <td><span className={`status-tag ${c.ajuste?.toLowerCase()}`}>{c.ajuste}</span></td>
                      <td className="analysis-text">
                        <div className="pros">✅ {c.razon_si}</div>
                        <div className="cons">⚠️ {c.razon_no}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="conclusion-box">
              <h3>Veredicto Final</h3>
              <p>{result.conclusion}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;