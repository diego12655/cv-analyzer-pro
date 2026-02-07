import React, { useState } from 'react';
import { Lock, CheckCircle, AlertCircle } from 'lucide-react';

function Login({ onLoginSuccess }) {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_URL}/api/validate-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code: code.toUpperCase() })
      });

      const data = await response.json();

      if (data.valid) {
        // Guardar token en localStorage
        localStorage.setItem('token', data.token);
        localStorage.setItem('credits', data.credits);
        onLoginSuccess(data.token, data.credits);
      } else {
        setError(data.message || 'Código inválido');
      }
    } catch (err) {
      setError('Error al validar código. Verifica tu conexión.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-icon">
          <Lock size={48} />
        </div>
        
        <h1>CV Analyzer Pro</h1>
        <p className="subtitle">Análisis profesional de CVs con IA</p>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label>Código de Acceso</label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="XXXX-XXXX-XXXX"
              className="code-input"
              maxLength={14}
              required
            />
          </div>

          {error && (
            <div className="error-message">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <button 
            type="submit" 
            className="btn-login"
            disabled={loading || code.length < 10}
          >
            {loading ? 'Validando...' : 'Acceder'}
          </button>
        </form>

        <div className="info-box">
          <CheckCircle size={16} />
          <p>Cada código incluye 5 análisis de CV gratuitos</p>
        </div>

        <div className="help-text">
          <p>¿No tienes código? <a href="mailto:contacto@cvanalyzer.com">Solicítalo aquí</a></p>
        </div>
      </div>
    </div>
  );
}

export default Login;