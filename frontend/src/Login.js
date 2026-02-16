import React, { useState } from 'react';
import { ShieldCheck, AlertCircle, Loader2, CheckCircle } from 'lucide-react';

function Login({ onLoginSuccess }) {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isShaking, setIsShaking] = useState(false);

  const API_URL = 'http://127.0.0.1:8000';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setIsShaking(false);

    try {
      const response = await fetch(`${API_URL}/api/validate-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code.toUpperCase().trim() })
      });

      const data = await response.json();

      if (response.ok && data.valid) {
        localStorage.setItem('token', data.token);
        onLoginSuccess(data.token, data.credits);
      } else {
        setError(data.message || 'Código de acceso incorrecto');
        setIsShaking(true);
        setTimeout(() => setIsShaking(false), 500);
      }
    } catch (err) {
      setError('Error de conexión con el servidor');
      setIsShaking(true);
      setTimeout(() => setIsShaking(false), 500);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className={`login-card ${isShaking ? 'shake-error' : ''}`}>
        
        {/* Cabecera con Logo */}
        <div className="login-brand">
          <div className="brand-logo">
            <ShieldCheck size={32} />
          </div>
          <h1><span>zeptdocs</span></h1>
          <p>Intelligence-driven recruitment ranking</p>
        </div>

        {/* Formulario de Entrada */}
        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label>Código de Acceso</label>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="XXXX-XXXX-XXXX"
              className="login-input"
              required
              disabled={loading}
            />
          </div>

          {error && (
            <div className="error-banner">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={loading || code.length < 4}>
            {loading ? <Loader2 className="spinner" size={20} /> : 'Entrar al Dashboard'}
          </button>
        </form>

        {/* Footer de información */}
        <div className="login-footer">
          <div className="info-badge">
            <CheckCircle size={14} />
            <span>Incluye 5 análisis gratuitos</span>
          </div>
          <p>¿Necesitas soporte? <a href="mailto:soporte@ejemplo.com">Contactar</a></p>
        </div>

      </div>
    </div>
  );
}

export default Login;