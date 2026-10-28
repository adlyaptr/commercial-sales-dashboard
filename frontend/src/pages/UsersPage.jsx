import { useEffect, useState } from 'react';
import { api } from '../api';

export default function UsersPage() {
    const [users, setUsers] = useState([]);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [passwords, setPasswords] = useState({});
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState('');
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');

    async function loadUsers() {
        setError('');
        try {
            setUsers(await api('/api/users'));
        } catch (requestError) {
            setError(requestError.message || 'Daftar pengguna gagal dimuat.');
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadUsers();
    }, []);

    async function createUser(event) {
        event.preventDefault();
        setBusy('create');
        setError('');
        setNotice('');
        try {
            await api('/api/users', {
                method: 'POST',
                body: { username, password, role: 'user' },
            });
            setUsername('');
            setPassword('');
            setNotice(`Akun User "${username}" berhasil dibuat.`);
            await loadUsers();
        } catch (requestError) {
            setError(requestError.message || 'Akun gagal dibuat.');
        } finally {
            setBusy('');
        }
    }

    async function updatePassword(targetUsername, event) {
        event.preventDefault();
        const nextPassword = passwords[targetUsername] || '';
        setBusy(targetUsername);
        setError('');
        setNotice('');
        try {
            await api(`/api/users/${encodeURIComponent(targetUsername)}/password`, {
                method: 'PUT',
                body: { password: nextPassword },
            });
            setPasswords((current) => ({ ...current, [targetUsername]: '' }));
            setNotice(`Password akun "${targetUsername}" berhasil diperbarui.`);
        } catch (requestError) {
            setError(requestError.message || 'Password gagal diperbarui.');
        } finally {
            setBusy('');
        }
    }

    async function removeUser(targetUsername) {
        if (!window.confirm(`Hapus akun "${targetUsername}"?`)) return;
        setBusy(targetUsername);
        setError('');
        setNotice('');
        try {
            await api(`/api/users/${encodeURIComponent(targetUsername)}`, {
                method: 'DELETE',
            });
            setNotice(`Akun "${targetUsername}" berhasil dihapus.`);
            await loadUsers();
        } catch (requestError) {
            setError(requestError.message || 'Akun gagal dihapus.');
        } finally {
            setBusy('');
        }
    }

    return (
        <div className="users-page">
            <header className="users-heading">
                <div>
                    <h1>Pengelolaan Pengguna</h1>
                    <p>Divisi dapat membuka tautan dashboard langsung untuk melihat Beranda tanpa login. Hanya Admin dan User yang memerlukan akun.</p>
                </div>
            </header>

            {error && <div className="notice bad" role="alert">{error}</div>}
            {notice && <div className="notice good" role="status">{notice}</div>}

            <section className="users-panel">
                <h2>Buat akun User</h2>
                <form className="users-create-form" onSubmit={createUser}>
                    <label>
                        Username
                        <input
                            autoComplete="off"
                            required
                            minLength={3}
                            maxLength={64}
                            pattern="[A-Za-z0-9][A-Za-z0-9._-]{2,63}"
                            value={username}
                            onChange={(event) => setUsername(event.target.value)}
                        />
                    </label>
                    <label>
                        Password sementara
                        <input
                            type="password"
                            autoComplete="new-password"
                            required
                            minLength={12}
                            maxLength={256}
                            value={password}
                            onChange={(event) => setPassword(event.target.value)}
                        />
                    </label>
                    <button className="primary" type="submit" disabled={busy !== ''}>
                        {busy === 'create' ? 'Menyimpan...' : 'Buat akun User'}
                    </button>
                </form>
                <small className="users-help">
                    Username 3-64 karakter. Password minimal 12 karakter.
                </small>
            </section>

            <section className="users-panel">
                <h2>Daftar akun</h2>
                {loading ? (
                    <p className="users-muted">Memuat akun...</p>
                ) : users.length === 0 ? (
                    <p className="users-muted">Belum ada akun pengguna.</p>
                ) : (
                    <div className="users-list">
                        {users.map((user) => (
                            <article className="users-row" key={user.username}>
                                <div className="users-identity">
                                    <strong>{user.username}</strong>
                                    <span className={`users-role ${user.role}`}>
                                        {user.role === 'admin' ? 'Admin' : user.role === 'user' ? 'User' : 'Akun Divisi lama · login nonaktif'}
                                    </span>
                                </div>
                                {user.role === 'user' && (
                                    <div className="users-actions">
                                        <form onSubmit={(event) => updatePassword(user.username, event)}>
                                            <input
                                                type="password"
                                                autoComplete="new-password"
                                                aria-label={`Password baru untuk ${user.username}`}
                                                placeholder="Password baru (min. 12 karakter)"
                                                minLength={12}
                                                maxLength={256}
                                                required
                                                value={passwords[user.username] || ''}
                                                onChange={(event) => setPasswords((current) => ({
                                                    ...current,
                                                    [user.username]: event.target.value,
                                                }))}
                                            />
                                            <button type="submit" disabled={busy !== ''}>
                                                Ganti password
                                            </button>
                                        </form>
                                        <button
                                            className="users-delete"
                                            type="button"
                                            disabled={busy !== ''}
                                            onClick={() => removeUser(user.username)}
                                        >
                                            Hapus
                                        </button>
                                    </div>
                                )}
                                {user.role === 'division' && (
                                    <button
                                        className="users-delete"
                                        type="button"
                                        disabled={busy !== ''}
                                        onClick={() => removeUser(user.username)}
                                    >
                                        Hapus akun lama
                                    </button>
                                )}
                            </article>
                        ))}
                    </div>
                )}
            </section>
        </div>
    );
}
