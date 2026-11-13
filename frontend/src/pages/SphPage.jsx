import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';
import logoImage from '../assets/reethau.png';
import '../sph.css';

const roleLabels = {
    sales: 'Sales',
    commercial_head: 'Commercial Head',
    director: 'Direksi',
    legal: 'Legal',
};

const statusLabels = {
    draft: 'Draft',
    review: 'Menunggu approval',
    approved: 'Disetujui internal',
    sent: 'Terkirim',
    negotiation: 'Negosiasi',
    customer_approved: 'Disetujui customer',
    active: 'Kontrak aktif',
};

const statusFilters = [
    { key: 'draft', label: statusLabels.draft },
    { key: 'review', label: statusLabels.review },
    { key: 'approved', label: statusLabels.approved },
    { key: 'sent', label: statusLabels.sent },
    { key: 'negotiation', label: statusLabels.negotiation },
    { key: 'customer_approved', label: statusLabels.customer_approved },
    { key: 'active', label: statusLabels.active },
];

const workflow = [
    'draft',
    'review',
    'approved',
    'sent',
    'negotiation',
    'customer_approved',
    'active',
];

const reethauObligationOptions = [
    { label: 'Pengiriman CNG hingga lokasi pabrik customer.', checked: true },
    { label: 'Penyediaan dan pemeliharaan Pressure Reducing System (PRS).', checked: true },
    { label: 'Penyediaan transportasi angkutan CNG tube trailer sesuai dengan kebutuhan customer.', checked: true },
    { label: 'Penyediaan driver dan operator PRS.', checked: true },
    { label: 'Penyediaan management dan monitoring traffic system transportasi CNG. Adapun monitoring traffic system menggunakan layanan GPS tracker.', checked: true },
    { label: 'Layanan customer service 24 Jam.', checked: true },
];

const customerObligationOptions = [
    { label: 'Menyediakan area parkir, sipil (Canopy dan concrete) dan shelter.', checked: true },
    { label: 'Pengadaan dan instalasi pipa internal.', checked: true },
    { label: 'Menyediakan listrik dan air untuk water heater, fire extinguisher & Grounding.', checked: true },
    { label: 'Menyediakan ruangan atau tempat untuk operator RCE.', checked: true },
];

function serializeObligations(options, selectedOptions, otherSelected, otherText) {
    const lines = options
        .filter((option) => selectedOptions.includes(option.label))
        .map((option) => option.label);
    if (otherSelected) lines.push(`Lainnya: ${otherText.trim()}`);
    return lines.join('\n');
}

function parseObligations(value, options) {
    const selected = [];
    const otherLines = [];
    let otherSelected = false;

    for (const line of String(value || '').split(/\r?\n/)) {
        const text = line.trim();
        if (!text) continue;
        const option = options.find((item) => item.label === text);
        if (option) {
            selected.push(option.label);
        } else if (text.startsWith('Lainnya:')) {
            otherSelected = true;
            const essay = text.slice('Lainnya:'.length).trim();
            if (essay) otherLines.push(essay);
        } else {
            otherSelected = true;
            otherLines.push(text);
        }
    }

    return { selected, otherSelected, otherText: otherLines.join('\n') };
}

function blankProposal() {
    return {
        proposalNumber: '',
        customerName: '',
        address: '',
        proposalDate: new Date().toISOString().slice(0, 10),
        volumeMin: '',
        volumeMax: '',
        priceUsd: '',
        topPercent: 90,
        guarantee: 'Cash Deposit',
        dueDay: 20,
        exchangeClause: false,
        contractYears: 2,
        reethauObligations: serializeObligations(
            reethauObligationOptions,
            reethauObligationOptions.filter((option) => option.checked).map((option) => option.label),
            false,
            '',
        ),
        customerObligations: serializeObligations(
            customerObligationOptions,
            customerObligationOptions.filter((option) => option.checked).map((option) => option.label),
            false,
            '',
        ),
    };
}

function formFromProposal(proposal) {
    return {
        proposalNumber: proposal.number || '',
        customerName: proposal.customerName || '',
        address: [proposal.addressLine1, proposal.addressLine2].filter(Boolean).join(' '),
        proposalDate: proposal.proposalDate || '',
        volumeMin: proposal.volumeMin,
        volumeMax: proposal.volumeMax,
        priceUsd: proposal.priceUsd,
        topPercent: proposal.topPercent,
        guarantee: proposal.guarantee,
        dueDay: proposal.dueDay,
        exchangeClause: proposal.exchangeClause,
        contractYears: proposal.contractYears,
        reethauObligations: proposal.reethauObligations || '',
        customerObligations: proposal.customerObligations || '',
    };
}

function formatNumber(value, digits = 0) {
    if (value == null || value === '') return '—';
    return new Intl.NumberFormat('id-ID', {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
    }).format(value);
}

function formatUpdatedAt(value) {
    if (!value) return '—';
    const updatedAt = new Date(value);
    if (Number.isNaN(updatedAt.getTime())) return '—';
    return new Intl.DateTimeFormat('id-ID', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
    }).format(updatedAt);
}

function SphPaperPreview({ form }) {
    const [previewUrl, setPreviewUrl] = useState('');
    const [previewError, setPreviewError] = useState('');
    const [loadingPreview, setLoadingPreview] = useState(false);
    const previewUrlRef = useRef('');
    const previewPayload = JSON.stringify({
        proposalNumber: form.proposalNumber,
        customerName: form.customerName,
        addressLine1: form.address,
        addressLine2: '',
        proposalDate: form.proposalDate,
        volumeMin: form.volumeMin,
        volumeMax: form.volumeMax,
        priceUsd: form.priceUsd,
        topPercent: form.topPercent,
        guarantee: form.guarantee,
        dueDay: form.dueDay,
        exchangeClause: form.exchangeClause,
        contractYears: form.contractYears,
        reethauObligations: form.reethauObligations,
        customerObligations: form.customerObligations,
    });

    useEffect(() => {
        const controller = new AbortController();
        const timeout = setTimeout(async () => {
            setLoadingPreview(true);
            setPreviewError('');
            try {
                const response = await fetch('/api/sph/proposals/preview/pdf', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        Accept: 'application/pdf',
                        'Content-Type': 'application/json',
                    },
                    body: previewPayload,
                    signal: controller.signal,
                });
                if (!response.ok) {
                    const payload = await response.json().catch(() => ({}));
                    throw new Error(payload.detail || 'Pratinjau PDF gagal dibuat.');
                }
                const url = URL.createObjectURL(await response.blob());
                if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
                previewUrlRef.current = url;
                setPreviewUrl(url);
            } catch (requestError) {
                if (requestError.name !== 'AbortError') {
                    setPreviewError(requestError.message || 'Pratinjau PDF gagal dibuat.');
                }
            } finally {
                if (!controller.signal.aborted) setLoadingPreview(false);
            }
        }, 350);

        return () => {
            clearTimeout(timeout);
            controller.abort();
        };
    }, [previewPayload]);

    useEffect(() => () => {
        if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    }, []);

    return (
        <section className="sph-document-preview" aria-label="Pratinjau surat penawaran">
            <div className="sph-document-preview-heading">
                <strong>Pratinjau surat</strong>
                <span>{loadingPreview ? 'Membuat PDF…' : 'PDF resmi · mengikuti input'}</span>
            </div>
            {previewError && <p className="sph-preview-error" role="alert">{previewError}</p>}
            {previewUrl ? (
                <iframe className="sph-pdf-preview-frame" src={previewUrl} title="Pratinjau PDF surat penawaran" />
            ) : !previewError ? (
                <div className="sph-pdf-preview-placeholder">Lengkapi data wajib untuk membuat pratinjau surat.</div>
            ) : null}
        </section>
    );
}

function nextAction(proposal) {
    if (proposal.status === 'draft') return { action: 'submit', role: 'sales', label: 'Kirim untuk review' };
    if (proposal.status === 'review') {
        const role = proposal.approvalRoute?.[proposal.approvals?.length || 0];
        return role ? { action: 'approve', role, label: `Setujui sebagai ${roleLabels[role]}` } : null;
    }
    if (proposal.status === 'approved') return { action: 'mark_sent', role: 'sales', label: 'Tandai telah dikirim' };
    if (proposal.status === 'sent') return { action: 'customer_approved', role: 'sales', label: 'Pelanggan menyetujui' };
    if (proposal.status === 'negotiation') return { action: 'revise', role: 'sales', label: 'Buat revisi' };
    if (proposal.status === 'customer_approved') return { action: 'activate', role: 'admin', label: 'Aktifkan pelanggan (Admin)' };
    return null;
}

function TextField({ label, className = '', ...props }) {
    return (
        <label className={`sph-field ${className}`}>
            <span>{label}</span>
            <input {...props} />
        </label>
    );
}

function ObligationChecklist({ title, value, options, onChange }) {
    const parsed = parseObligations(value, options);

    function updateSelection(label, checked) {
        const selected = checked
            ? [...parsed.selected, label]
            : parsed.selected.filter((item) => item !== label);
        onChange(serializeObligations(
            options,
            selected,
            parsed.otherSelected,
            parsed.otherText,
        ));
    }

    function updateOther(checked) {
        onChange(serializeObligations(
            options,
            parsed.selected,
            checked,
            checked ? parsed.otherText : '',
        ));
    }

    return (
        <fieldset className="sph-obligation-group">
            <legend>{title}</legend>
            <div className="sph-obligation-options">
                {options.map((option) => (
                    <label className="sph-obligation-option" key={option.label}>
                        <input
                            type="checkbox"
                            checked={parsed.selected.includes(option.label)}
                            onChange={(event) => updateSelection(option.label, event.target.checked)}
                        />
                        <span>{option.label}</span>
                    </label>
                ))}
                <label className="sph-obligation-option">
                    <input
                        type="checkbox"
                        checked={parsed.otherSelected}
                        onChange={(event) => updateOther(event.target.checked)}
                    />
                    <span>Lainnya</span>
                </label>
            </div>
            {parsed.otherSelected && (
                <label className="sph-field sph-obligation-essay">
                    <span>Jelaskan kewajiban lainnya</span>
                    <textarea
                        rows="3"
                        maxLength={10000}
                        value={parsed.otherText}
                        onChange={(event) => onChange(serializeObligations(
                            options,
                            parsed.selected,
                            parsed.otherSelected,
                            event.target.value,
                        ))}
                    />
                </label>
            )}
        </fieldset>
    );
}

export default function SphPage({ user, onLogout }) {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [proposals, setProposals] = useState([]);
    const [sphUsers, setSphUsers] = useState([]);
    const [usersLoading, setUsersLoading] = useState(false);
    const [proposal, setProposal] = useState(null);
    const [form, setForm] = useState(blankProposal);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [returnReason, setReturnReason] = useState('');
    const [actualVolume, setActualVolume] = useState('');
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');

    const isSales = user.sphRole === 'sales';
    const isCommercialHead = user.sphRole === 'commercial_head';
    async function loadProposals() {
        setError('');
        try {
            setProposals(await api('/api/sph/proposals'));
        } catch (requestError) {
            setError(requestError.message || 'Daftar SPH gagal dimuat.');
        } finally {
            setLoading(false);
        }
    }

    async function loadSphUsers() {
        setUsersLoading(true);
        setError('');
        try {
            setSphUsers(await api('/api/sph/users'));
        } catch (requestError) {
            setError(requestError.message || 'Daftar pengguna SPH gagal dimuat.');
        } finally {
            setUsersLoading(false);
        }
    }

    async function openTab(tab) {
        setActiveTab(tab);
        if (tab === 'access') await loadSphUsers();
    }

    async function updateSphRole(targetUsername, sphRole) {
        setBusy(true);
        setError('');
        setNotice('');
        try {
            await api(`/api/sph/users/${encodeURIComponent(targetUsername)}/role`, {
                method: 'PUT',
                body: { sphRole: sphRole || null },
            });
            setNotice(
                sphRole
                    ? `Role SPH ${roleLabels[sphRole]} diberikan kepada "${targetUsername}".`
                    : `Akses SPH CNG untuk "${targetUsername}" dinonaktifkan.`,
            );
            await loadSphUsers();
        } catch (requestError) {
            setError(requestError.message || 'Role SPH gagal diperbarui.');
        } finally {
            setBusy(false);
        }
    }

    useEffect(() => {
        loadProposals();
    }, []);

    async function openProposal(id, tab = 'process') {
        setBusy(true);
        setError('');
        setNotice('');
        try {
            const selected = await api(`/api/sph/proposals/${id}`);
            setProposal(selected);
            setForm(formFromProposal(selected));
            setReturnReason('');
            setActualVolume(selected.actualVolume ?? '');
            setActiveTab(tab);
        } catch (requestError) {
            setError(requestError.message || 'Detail SPH gagal dimuat.');
        } finally {
            setBusy(false);
        }
    }

    function startNewProposal() {
        setProposal(null);
        setForm(blankProposal());
        setError('');
        setNotice('');
        setActiveTab('editor');
    }

    function updateField(event) {
        const { name, value, type, checked } = event.target;
        setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
    }

    async function saveDraft(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        setNotice('');
        const payload = {
            ...form,
            addressLine1: form.address.trim(),
            addressLine2: '',
            volumeMin: Number(form.volumeMin),
            volumeMax: Number(form.volumeMax),
            priceUsd: Number(form.priceUsd),
            topPercent: Number(form.topPercent),
            dueDay: Number(form.dueDay),
            contractYears: Number(form.contractYears),
        };
        try {
            const saved = proposal
                ? await api(`/api/sph/proposals/${proposal.id}`, { method: 'PUT', body: payload })
                : await api('/api/sph/proposals', { method: 'POST', body: payload });
            setProposal(saved);
            setForm(formFromProposal(saved));
            setNotice('Draft SPH berhasil disimpan.');
            await loadProposals();
        } catch (requestError) {
            setError(requestError.message || 'Draft SPH gagal disimpan.');
        } finally {
            setBusy(false);
        }
    }

    async function performAction(action, extra = {}) {
        if (!proposal) return;
        setBusy(true);
        setError('');
        setNotice('');
        try {
            const updated = await api(`/api/sph/proposals/${proposal.id}/actions`, {
                method: 'POST',
                body: { action, ...extra },
            });
            setProposal(updated);
            setForm(formFromProposal(updated));
            setReturnReason('');
            setNotice(`Status SPH diperbarui: ${statusLabels[updated.status]}.`);
            await loadProposals();
        } catch (requestError) {
            setError(requestError.message || 'Tindakan SPH gagal diproses.');
        } finally {
            setBusy(false);
        }
    }

    async function logout() {
        setBusy(true);
        setError('');
        try {
            await api('/api/logout', { method: 'POST' });
            onLogout();
        } catch (requestError) {
            setError(requestError.message || 'Gagal keluar dari aplikasi.');
        } finally {
            setBusy(false);
        }
    }

    const visibleProposals = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('id-ID');
        return proposals.filter((item) => {
            const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
            const matchesSearch = !query
                || `${item.number} ${item.customerName} ${item.status} ${statusLabels[item.status] || ''}`
                    .toLocaleLowerCase('id-ID')
                    .includes(query);
            return matchesStatus && matchesSearch;
        });
    }, [proposals, search, statusFilter]);

    const statusCounts = proposals.reduce((counts, item) => {
        if (Object.prototype.hasOwnProperty.call(counts, item.status)) {
            counts[item.status] += 1;
        }
        return counts;
    }, {
        draft: 0,
        review: 0,
        approved: 0,
        sent: 0,
        negotiation: 0,
        customer_approved: 0,
        active: 0,
    });
    const activeProposals = proposals.filter((item) => item.status === 'active');
    const averagePrice = proposals.length
        ? proposals.reduce((total, item) => total + Number(item.priceUsd || 0), 0) / proposals.length
        : 0;
    const action = proposal ? nextAction(proposal) : null;
    const canApprove = proposal?.status === 'review'
        && proposal.approvalRoute?.[proposal.approvals?.length || 0] === user.sphRole;

    return (
        <main className="sph-app">
            <header className="sph-topbar">
                <a className="sph-brand" href="/sph" aria-label="SPH CNG Reethau">
                    <img src={logoImage} alt="Reethau Clean Energy" />
                </a>
                <div className="sph-topbar-right">
                    <span className="sph-user-chip">
                        <strong>{user.username}</strong>
                        <small>
                            {user.role === 'admin' && !user.sphRole
                                ? 'Admin · akses lihat'
                                : `${user.role === 'admin' ? 'Admin · ' : ''}${roleLabels[user.sphRole]}`}
                        </small>
                    </span>
                    <button className="sph-logout" type="button" onClick={logout} disabled={busy}>Keluar</button>
                </div>
            </header>

            <section className="sph-main">
                <header className="sph-page-heading">
                    <div>
                        <p className="sph-eyebrow">MARKETING &amp; CONTRACT MANAGEMENT</p>
                        <h1>SPH CNG Reethau</h1>
                        <p>Pengelolaan penawaran harga, persetujuan, dan proses kontrak pelanggan.</p>
                    </div>
                    {isSales && (
                        <button className="sph-primary" type="button" onClick={startNewProposal}>
                            <span aria-hidden="true">＋</span> Buat SPH baru
                        </button>
                    )}
                </header>

                <nav className="sph-tabs" aria-label="Navigasi SPH">
                    {[
                        ['dashboard', 'Dashboard'],
                        ['editor', 'Editor SPH'],
                        ['process', 'Alur proses'],
                        ...(user.role === 'admin' ? [['access', 'Akses pengguna']] : []),
                    ].map(([tab, label]) => (
                        <button
                            key={tab}
                            type="button"
                            className={activeTab === tab ? 'active' : ''}
                            onClick={() => openTab(tab)}
                        >
                            {label}
                        </button>
                    ))}
                </nav>

                {error && <div className="sph-alert error" role="alert">{error}</div>}
                {notice && <div className="sph-alert success" role="status">{notice}</div>}

                {activeTab === 'access' && user.role === 'admin' && (
                    <section className="sph-panel">
                        <div className="sph-panel-heading">
                            <div>
                                <h2>Pengaturan akses SPH</h2>
                                <p>Tetapkan role proses atau nonaktifkan akses SPH untuk akun Admin dan User.</p>
                            </div>
                        </div>
                        {usersLoading ? (
                            <p className="sph-empty">Memuat daftar pengguna...</p>
                        ) : sphUsers.length === 0 ? (
                            <p className="sph-empty">Belum ada akun yang dapat diatur.</p>
                        ) : (
                            <div className="sph-table-wrap">
                                <table className="sph-table">
                                    <thead><tr><th>Username</th><th>Jenis akun</th><th>Akses SPH</th></tr></thead>
                                    <tbody>
                                        {sphUsers.map((sphUser) => (
                                            <tr key={sphUser.username}>
                                                <td><strong>{sphUser.username}</strong></td>
                                                <td>{sphUser.role === 'admin' ? 'Admin' : 'User'}</td>
                                                <td>
                                                    <label className="sph-field">
                                                        <span className="sr-only">Role SPH untuk {sphUser.username}</span>
                                                        <select
                                                            value={['sales', 'commercial_head'].includes(sphUser.sph_role) ? sphUser.sph_role : ''}
                                                            disabled={busy}
                                                            aria-label={`Role SPH untuk ${sphUser.username}`}
                                                            onChange={(event) => updateSphRole(sphUser.username, event.target.value)}
                                                        >
                                                            <option value="">Tidak ditugaskan</option>
                                                            <option value="sales">Sales</option>
                                                            <option value="commercial_head">Commercial Head</option>
                                                        </select>
                                                    </label>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </section>
                )}

                {activeTab === 'dashboard' && (
                    <section className="sph-dashboard">
                        <section className="sph-panel">
                            <div className="sph-list-heading">
                                <h2>DAFTAR SPH</h2>
                                <p>Klik Buka untuk mengedit atau PDF untuk melihat hasil export</p>
                            </div>
                            <label className="sph-search-field">
                                <span>Cari customer atau nomor</span>
                                <input
                                    aria-label="Cari customer atau nomor SPH"
                                    placeholder="Contoh: Excel atau MKT-003"
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                />
                            </label>
                            <div className="sph-status-filters" aria-label="Filter status SPH">
                                <button
                                    type="button"
                                    className={statusFilter === 'all' ? 'active' : ''}
                                    aria-pressed={statusFilter === 'all'}
                                    onClick={() => setStatusFilter('all')}
                                >
                                    Semua {proposals.length}
                                </button>
                                {statusFilters.map((filter) => (
                                    <button
                                        key={filter.key}
                                        type="button"
                                        className={statusFilter === filter.key ? 'active' : ''}
                                        aria-pressed={statusFilter === filter.key}
                                        onClick={() => setStatusFilter(filter.key)}
                                    >
                                        {filter.label} {statusCounts[filter.key]}
                                    </button>
                                ))}
                            </div>
                            {loading ? (
                                <p className="sph-empty">Memuat daftar SPH...</p>
                            ) : visibleProposals.length === 0 ? (
                                <div className="sph-empty">
                                    <span className="sph-empty-mark">SPH</span>
                                    <strong>{proposals.length ? 'Tidak ada hasil yang sesuai' : 'Belum ada data SPH'}</strong>
                                    <p>{proposals.length ? 'Coba kata kunci atau filter status lain.' : 'Data akan muncul setelah draft SPH pertama dibuat. Tidak ada data contoh yang dimasukkan.'}</p>
                                    {isSales && proposals.length === 0 && (
                                        <button className="sph-primary" type="button" onClick={startNewProposal}>Buat SPH pertama</button>
                                    )}
                                </div>
                            ) : (
                                <div className="sph-table-wrap">
                                    <table className="sph-table">
                                        <thead>
                                            <tr>
                                                <th>No SPH</th>
                                                <th>Customer</th>
                                                <th>Volume (MMBTU)</th>
                                                <th>USD/MMBTU</th>
                                                <th>Nilai/bln (min)</th>
                                                <th>Status</th>
                                                <th>Update</th>
                                                <th aria-label="Tindakan" />
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {visibleProposals.map((item) => (
                                                <tr key={item.id}>
                                                    <td>
                                                        <strong className="sph-proposal-number">
                                                            {item.number}{item.version > 0 ? ` · Rev.${item.version}` : ''}
                                                        </strong>
                                                    </td>
                                                    <td>{item.customerName}</td>
                                                    <td className="sph-number-cell">{formatNumber(item.volumeMin)} - {formatNumber(item.volumeMax)}</td>
                                                    <td className="sph-number-cell">{formatNumber(item.priceUsd, 2)}</td>
                                                    <td className="sph-number-cell">{formatNumber(Number(item.volumeMin) * Number(item.priceUsd))}</td>
                                                    <td><span className={`sph-status sph-status-pill ${item.status}`}>{statusLabels[item.status]}</span></td>
                                                    <td className="sph-updated-cell">{formatUpdatedAt(item.updatedAt)}</td>
                                                    <td>
                                                        <div className="sph-row-actions">
                                                            <button className="sph-row-button" type="button" disabled={busy} onClick={() => openProposal(item.id, 'process')}>Alur</button>
                                                            <button className="sph-row-button" type="button" disabled={busy} onClick={() => openProposal(item.id, isSales ? 'editor' : 'process')}>Buka</button>
                                                            <a className="sph-row-button" href={`/api/sph/proposals/${item.id}/pdf`}>PDF</a>
                                                        </div>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </section>

                        <section className="sph-panel sph-active-contracts">
                            <div className="sph-panel-heading">
                                <div>
                                    <h2>KONTRAK AKTIF: REALISASI DAN MINIMUM TOP</h2>
                                    <p>Bandingkan realisasi tercatat dengan ambang TOP dan volume minimum kontrak.</p>
                                </div>
                                <span>Volume MMBTU/hari</span>
                            </div>
                            {activeProposals.length === 0 ? (
                                <p className="sph-empty">Belum ada kontrak aktif.</p>
                            ) : (
                                <div className="sph-active-contract-list">
                                    {activeProposals.map((item) => {
                                        const minimum = Number(item.volumeMin || 0);
                                        const maximum = Number(item.volumeMax || minimum);
                                        const top = minimum * Number(item.topPercent || 0) / 100;
                                        const actual = item.actualVolume == null ? null : Number(item.actualVolume);
                                        const scale = Math.max(maximum, actual || 0, 1);
                                        const topPosition = Math.min((top / scale) * 100, 100);
                                        const minimumPosition = Math.min((minimum / scale) * 100, 100);
                                        const actualWidth = actual == null ? 0 : Math.min((actual / scale) * 100, 100);
                                        const belowTop = actual != null && actual < top;
                                        return (
                                            <article className="sph-active-contract" key={item.id}>
                                                <div className="sph-contract-heading">
                                                    <strong>{item.customerName}</strong>
                                                    <span>{item.number}</span>
                                                </div>
                                                <div className="sph-contract-scale">
                                                    <div className={`sph-contract-fill ${belowTop ? 'below-top' : ''}`} style={{ width: `${actualWidth}%` }} />
                                                    <span className="sph-contract-marker top" style={{ left: `${topPosition}%` }} />
                                                    <span className="sph-contract-marker minimum" style={{ left: `${minimumPosition}%` }} />
                                                </div>
                                                <div className="sph-contract-markers">
                                                    <span style={{ left: `${topPosition}%` }}>TOP {formatNumber(top)}</span>
                                                    <span style={{ left: `${minimumPosition}%` }}>Min {formatNumber(minimum)}</span>
                                                </div>
                                                <div className="sph-contract-result">
                                                    {actual == null ? (
                                                        <span className="sph-contract-unrecorded">Belum ada realisasi yang dicatat.</span>
                                                    ) : (
                                                        <>
                                                            <strong className={belowTop ? 'below-top' : 'meets-top'}>
                                                                {belowTop ? 'Di bawah TOP' : 'Mencapai TOP'}
                                                            </strong>
                                                            <span>Realisasi {formatNumber(actual)} MMBTU/hari · TOP {formatNumber(top)} MMBTU/hari</span>
                                                        </>
                                                    )}
                                                </div>
                                            </article>
                                        );
                                    })}
                                </div>
                            )}
                        </section>
                    </section>
                )}

                {activeTab === 'editor' && (
                    <section className="sph-panel sph-editor-panel">
                        <div className="sph-panel-heading">
                            <div>
                                <h2>{proposal ? `Editor SPH · ${proposal.number}` : 'Editor SPH baru'}</h2>
                                <p>
                                    {proposal
                                        ? proposal.status === 'draft'
                                            ? 'Ubah data penawaran pada Draft.'
                                            : 'Perubahan akan membuat versi baru dan mengembalikan SPH ke Draft untuk diajukan ulang.'
                                        : 'Lengkapi informasi pelanggan dan ketentuan penawaran.'}
                                </p>
                            </div>
                            {proposal && <span className={`sph-status ${proposal.status}`}>{statusLabels[proposal.status]}</span>}
                        </div>
                        {!proposal && !isSales ? (
                            <div className="sph-empty"><strong>Pilih SPH untuk melihat detail</strong><p>Akun Anda tidak memiliki role Sales untuk membuat draft.</p></div>
                        ) : proposal && (!isSales || proposal.status === 'active') ? (
                            <div className="sph-readonly">
                                <strong>
                                    {proposal.status === 'active'
                                        ? 'SPH berstatus Aktif tidak dapat diedit.'
                                        : 'Role Sales diperlukan untuk mengedit SPH.'}
                                </strong>
                                <p>Buka tab Alur proses untuk melihat tahapan, persetujuan, dan riwayat.</p>
                                <button className="sph-secondary" type="button" onClick={() => setActiveTab('process')}>Lihat alur proses</button>
                            </div>
                        ) : (
                            <div className="sph-editor-layout">
                            <form className="sph-form" onSubmit={saveDraft}>
                                <div className="sph-form-section">
                                    <h3>Informasi pelanggan</h3>
                                    <div className="sph-form-grid">
                                        <TextField label="Nomor surat *" name="proposalNumber" value={form.proposalNumber} onChange={updateField} required maxLength={80} placeholder="Contoh: SPH-2026-11-MKT-000" />
                                        <TextField label="Nama pelanggan *" name="customerName" value={form.customerName} onChange={updateField} required maxLength={255} />
                                        <TextField label="Tanggal penawaran *" name="proposalDate" type="date" value={form.proposalDate} onChange={updateField} required />
                                        <TextField label="Alamat" name="address" value={form.address} onChange={updateField} maxLength={2000} placeholder="Jalan Akses Tol Cibitung No.82, Gandasari, Kecamatan Cikarang Barat, Kabupaten Bekasi, Jawa Barat 17530" />
                                    </div>
                                </div>
                                <div className="sph-form-section">
                                    <h3>Volume dan harga</h3>
                                    <div className="sph-form-grid">
                                        <TextField label="Volume minimum (MMBTU/hari) *" name="volumeMin" type="number" min="0.01" step="0.01" value={form.volumeMin} onChange={updateField} required />
                                        <TextField label="Volume maksimum (MMBTU/hari) *" name="volumeMax" type="number" min="0.01" step="0.01" value={form.volumeMax} onChange={updateField} required />
                                        <TextField label="Harga (USD/MMBTU) *" name="priceUsd" type="number" min="0.01" step="0.01" value={form.priceUsd} onChange={updateField} required />
                                        <TextField label="Take-or-pay (%)" name="topPercent" type="number" min="0" max="100" step="0.01" value={form.topPercent} onChange={updateField} required />
                                    </div>
                                    <p className="sph-form-hint">Semua penawaran memerlukan persetujuan Commercial Head.</p>
                                </div>
                                <div className="sph-form-section">
                                    <h3>Ketentuan kontrak</h3>
                                    <div className="sph-form-grid">
                                        <label className="sph-field"><span>Jaminan</span><select name="guarantee" value={form.guarantee} onChange={updateField}><option>Cash Deposit</option><option>Bank Guarantee</option><option>Parent Company Guarantee</option><option>N/A</option></select></label>
                                        <TextField label="Tanggal pembayaran setiap bulan" name="dueDay" type="number" min="1" max="28" value={form.dueDay} onChange={updateField} required />
                                        <TextField label="Jangka waktu (tahun)" name="contractYears" type="number" min="1" max="15" value={form.contractYears} onChange={updateField} required />
                                        <label className="sph-checkbox"><input type="checkbox" name="exchangeClause" checked={form.exchangeClause} onChange={updateField} /><span>Klausul tukar menukar berlaku</span></label>
                                    </div>
                                    <div className="sph-form-grid sph-form-grid-single">
                                        <ObligationChecklist
                                            title="Kewajiban PT Reethau Cipta Energi (C)"
                                            value={form.reethauObligations}
                                            options={reethauObligationOptions}
                                            onChange={(value) => setForm((current) => ({ ...current, reethauObligations: value }))}
                                        />
                                        <ObligationChecklist
                                            title="Kewajiban Customer (D)"
                                            value={form.customerObligations}
                                            options={customerObligationOptions}
                                            onChange={(value) => setForm((current) => ({ ...current, customerObligations: value }))}
                                        />
                                    </div>
                                </div>
                                <div className="sph-form-actions">
                                    <button className="sph-primary" type="submit" disabled={busy}>{busy ? 'Menyimpan...' : proposal ? 'Simpan perubahan' : 'Simpan draft'}</button>
                                </div>
                            </form>
                            <SphPaperPreview form={form} />
                            </div>
                        )}
                    </section>
                )}

                {activeTab === 'process' && (
                    <section className="sph-panel sph-process-panel">
                        {!proposal ? (
                            <div className="sph-empty"><strong>Pilih penawaran untuk melihat alur proses</strong><p>Gunakan Dashboard untuk memilih SPH.</p><button className="sph-secondary" type="button" onClick={() => setActiveTab('dashboard')}>Ke Dashboard</button></div>
                        ) : (
                            <>
                                <div className="sph-panel-heading">
                                    <div>
                                        <p className="sph-eyebrow">ALUR PENAWARAN</p>
                                        <h2>{proposal.number}{proposal.version > 0 ? ` · Revisi ${proposal.version}` : ''}</h2>
                                        <p>{proposal.customerName} · {proposal.proposalDate}</p>
                                    </div>
                                    <span className={`sph-status ${proposal.status}`}>{statusLabels[proposal.status]}</span>
                                </div>
                                <div className="sph-process-summary">
                                    <div><span>Volume</span><strong>{formatNumber(proposal.volumeMin)}–{formatNumber(proposal.volumeMax)} MMBTU/hari</strong></div>
                                    <div><span>Harga</span><strong>USD {formatNumber(proposal.priceUsd, 2)}/MMBTU</strong></div>
                                    <div><span>TOP</span><strong>{formatNumber(proposal.topPercent, 2)}%</strong></div>
                                    <div><span>Persetujuan</span><strong>{proposal.approvalRoute.map((role) => roleLabels[role]).join(' → ')}</strong></div>
                                </div>
                                <div className="sph-flow">
                                    {workflow.map((status, index) => {
                                        const completedIndex = workflow.indexOf(proposal.status);
                                        const completed = completedIndex >= index;
                                        return (
                                            <div className={`sph-flow-step ${completed ? 'complete' : ''} ${proposal.status === status ? 'current' : ''}`} key={status}>
                                                <span>{completed ? '✓' : String(index + 1).padStart(2, '0')}</span>
                                                <strong>{statusLabels[status]}</strong>
                                            </div>
                                        );
                                    })}
                                </div>

                                <div className="sph-action-area">
                                    {proposal.status !== 'active' && isSales && (
                                        <button
                                            className="sph-secondary"
                                            type="button"
                                            disabled={busy}
                                            onClick={() => setActiveTab('editor')}
                                        >
                                            Edit SPH
                                        </button>
                                    )}
                                    {action && (
                                        action.action !== 'approve' || canApprove
                                    ) && (
                                        (action.role === 'admin' && user.role === 'admin')
                                        || user.sphRole === action.role
                                    ) && (
                                        <button className="sph-primary" type="button" disabled={busy} onClick={() => performAction(action.action)}>
                                            {action.label}
                                        </button>
                                    )}
                                    {proposal.status === 'review' && canApprove && (
                                        <div className="sph-return-action">
                                            <input value={returnReason} onChange={(event) => setReturnReason(event.target.value)} placeholder="Alasan mengembalikan ke Sales" maxLength={2000} />
                                            <button className="sph-secondary" type="button" disabled={busy || !returnReason.trim()} onClick={() => performAction('return', { reason: returnReason })}>Kembalikan</button>
                                        </div>
                                    )}
                                    {proposal.status === 'sent' && isSales && (
                                        <button className="sph-secondary" type="button" disabled={busy} onClick={() => performAction('negotiation')}>Mulai negosiasi</button>
                                    )}
                                    {proposal.status === 'active' && isCommercialHead && (
                                        <div className="sph-return-action">
                                            <input type="number" min="0" step="0.01" value={actualVolume} onChange={(event) => setActualVolume(event.target.value)} placeholder="Volume aktual MMBTU/hari" />
                                            <button className="sph-secondary" type="button" disabled={busy || actualVolume === ''} onClick={() => performAction('record_actual', { actualVolume: Number(actualVolume) })}>Catat realisasi</button>
                                        </div>
                                    )}
                                    {proposal.status === 'active' && (
                                        <span className="sph-actual-volume">Realisasi tercatat: {formatNumber(proposal.actualVolume)} MMBTU/hari</span>
                                    )}
                                    <a className="sph-secondary sph-pdf-link" href={`/api/sph/proposals/${proposal.id}/pdf`}>Unduh PDF{proposal.status === 'draft' ? ' · Draft' : ''}</a>
                                </div>

                                <div className="sph-history">
                                    <h3>Riwayat aktivitas</h3>
                                    {proposal.history.length === 0 ? <p>Belum ada aktivitas.</p> : (
                                        <ol>
                                            {proposal.history.map((item, index) => (
                                                <li key={`${item.createdAt}-${index}`}>
                                                    <span className="sph-history-dot" />
                                                    <div><strong>{item.message}</strong><small>{item.actor} · {item.actorRoleLabel} · {new Date(item.createdAt).toLocaleString('id-ID')}</small></div>
                                                </li>
                                            ))}
                                        </ol>
                                    )}
                                </div>
                            </>
                        )}
                    </section>
                )}
            </section>
        </main>
    );
}
