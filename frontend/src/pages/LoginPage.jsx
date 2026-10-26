import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function LoginPage({ onLogin }) {
    const navigate = useNavigate();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);

    async function submit(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        try {
            await api('/api/login', { method: 'POST', body: { username, password } });
            onLogin(await api('/api/me'));
            navigate('/beranda', { replace: true });
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setBusy(false);
        }
    }

    return (
        <main className="login-page">
            <section className="login-card">
                <div className="login-mark">↗</div>
                <p className="eyebrow">COMMERCIAL · SALES MONITORING</p>
                <h1>Selamat datang</h1>
                <p className="muted">Masuk untuk membuka Commercial Dashboard.</p>
                <form onSubmit={submit}>
                    <label htmlFor="username">Username</label>
                    <input id="username" autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Masukkan username" />
                    <label htmlFor="password">Password</label>
                    <input id="password" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Masukkan password" />
                    <button className="primary full" type="submit" disabled={busy}>{busy ? 'MEMERIKSA...' : <>MASUK <span>→</span></>}</button>
                    {error && <p className="error" role="alert">{error}</p>}
                </form>
            </section>
        </main>
    );
}