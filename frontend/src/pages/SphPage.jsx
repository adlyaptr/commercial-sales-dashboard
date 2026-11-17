import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api';
import logoImage from '../assets/reethau.png';
import '../sph.css';

const roleLabels = {
    admin: 'Admin',
};

const statusLabels = {
    draft: 'Draft',
    review: 'Menunggu approval',
    approved: 'Disetujui internal',
    sent: 'Terkirim',
    negotiation: 'Negosiasi',
    customer_approved: 'Disetujui customer',
    active: 'Kontrak aktif',
    inactive: 'Tidak aktif',
};

const statusFilters = [
    { key: 'draft', label: statusLabels.draft },
    { key: 'review', label: statusLabels.review },
    { key: 'approved', label: statusLabels.approved },
    { key: 'sent', label: statusLabels.sent },
    { key: 'negotiation', label: statusLabels.negotiation },
    { key: 'customer_approved', label: statusLabels.customer_approved },
    { key: 'active', label: statusLabels.active },
    { key: 'inactive', label: statusLabels.inactive },
];

const workflow = [
    'draft',
    'review',
    'approved',
    'sent',
    'negotiation',
    'customer_approved',
    'active',
    'inactive',
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

const paymentTermOptions = [
    { label: 'Pembayaran akan dilakukan dalam mata uang Rupiah (IDR) sesuai dengan volume penyerapan bulanan.', checked: true },
    { label: 'Pembayaran dilakukan oleh Pihak Kedua paling lambat 14 (Empat Belas) hari setelah diterimanya tagihan dari Pihak Pertama, untuk setiap 30 (Tiga Puluh) hari atau 1 (Satu) bulan pengambilan CNG.', checked: true },
    { label: 'Jaminan dengan perhitungan: Volume Bulanan x Harga x Nilai Kurs = Nilai Jaminan.', checked: true },
];

const advantageOptions = [
    { label: 'Merupakan salah satu industri energi combine (LNG, CNG & Biomass) terkemuka di nusantara.', checked: true },
    { label: 'Reethau adalah salah satu industri CNG yang memiliki Mother Station terbanyak (4 Mother Station):\n- MS. KHT - Indramayu (Jawa Barat)\n- MS. SETU - Bekasi (Jawa Barat)\n- MS. ADK - Blora (Jawa Tengah)\n- MS Wunut - Sidoarjo (Jawa Timur)', checked: true },
    { label: 'Meliliki fasilitas suply atau armada yang lebih banyak serta telah terpasang aplikasi GPS Tracking:\n- Tube Skid 40 ft: 58 Unit, 20 ft: 45 Unit, 10 ft: 15 Unit\n- Head Truck 40 ft: 21 Unit, 20 ft: 21 Unit, 10 ft: 18 Unit', checked: true },
    { label: 'Memiliki aplikasi smart PRS yaitu Telemetri. Sebuah aplikasi yang bisa melihat load PRS dan data nya real time yang bisa di upload dan di lihat setiap saat.', checked: true },
    { label: 'Memiliki perizinan yang lengkap serta sesuai dengan kebutuhan industri kemudian memiliki sertifikasi ISO dan K3 yang terdaftar.', checked: true },
];

const otherTermOptions = [
    { label: 'Draft PJBG akan didiskusikan 1 bulan setelah penawaran ini disetujui.', checked: true },
];

const preparationOptions = [
    { label: '30 hari setelah surat penawaran ini di approved atau sesuai dengan kesepakatan.', checked: true },
];

function serializeObligations(options, selectedOptions, otherSelected, otherText) {
    const lines = options
        .filter((option) => selectedOptions.includes(option.label))
        .map((option) => option.label);
    if (otherSelected) lines.push(`Lainnya: ${otherText.trim()}`);
    return lines.join('\n');
}

function serializeTermChecklist(options, selectedOptions, otherSelected, otherText) {
    const items = options.map((option) => ({
        label: option.label,
        checked: selectedOptions.includes(option.label),
    }));
    if (otherSelected) {
        items.push({ label: `Lainnya: ${otherText.trim()}`, checked: true });
    }
    return JSON.stringify(items);
}

function parseObligations(value, options) {
    const selected = [];
    const otherLines = [];
    let otherSelected = false;
    const raw = String(value || '');

    try {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.every((item) => (
            item
            && typeof item.label === 'string'
            && typeof item.checked === 'boolean'
        ))) {
            for (const item of parsed) {
                if (!item.checked || !item.label.trim()) continue;
                const label = item.label.trim();
                if (label.startsWith('Lainnya:')) {
                    otherSelected = true;
                    const text = label.slice('Lainnya:'.length).trim();
                    if (text) otherLines.push(text);
                    continue;
                }
                const option = options.find((candidate) => candidate.label === label);
                if (option) selected.push(option.label);
                else otherLines.push(label);
            }
            return {
                selected,
                otherSelected: otherLines.length > 0,
                otherText: otherLines.join('\n'),
            };
        }
    } catch {
        // Existing proposals store these fields as plain text.
    }

    const lines = raw.split(/\r?\n/);
    const orderedOptions = [...options].sort(
        (left, right) => right.label.split(/\r?\n/).length - left.label.split(/\r?\n/).length,
    );
    for (let index = 0; index < lines.length;) {
        const option = orderedOptions.find((item) => (
            lines.slice(index, index + item.label.split(/\r?\n/).length).join('\n') === item.label
        ));
        if (option) {
            selected.push(option.label);
            index += option.label.split(/\r?\n/).length;
            continue;
        }
        const text = lines[index].trim();
        if (!text) {
            index += 1;
            continue;
        }
        if (text.startsWith('Lainnya:')) {
            otherSelected = true;
            const essay = text.slice('Lainnya:'.length).trim();
            if (essay) otherLines.push(essay);
        } else {
            otherSelected = true;
            otherLines.push(text);
        }
        index += 1;
    }

    return { selected, otherSelected, otherText: otherLines.join('\n') };
}

function addressFields(value) {
    const [addressLine1 = '', ...addressLines] = String(value || '').split(/\r?\n/);
    return {
        addressLine1: addressLine1.trim(),
        addressLine2: addressLines.join('\n').trim(),
    };
}

function blankProposal() {
    return {
        proposalNumber: '',
        templateKey: 'standard',
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
        contractDuration: 2,
        contractDurationUnit: 'year',
        durationDetails: '',
        attentionTo: '',
        motherStation: '',
        plantName: '',
        plantAddress: '',
        supplyPattern: '',
        deliveryPoint: '',
        startDate: '',
        endDate: '',
        volumeDetails: '',
        priceDetails: '',
        paymentTerms: serializeTermChecklist(paymentTermOptions, paymentTermOptions.map((option) => option.label), false, ''),
        advantages: serializeTermChecklist(advantageOptions, advantageOptions.map((option) => option.label), false, ''),
        otherTerms: serializeTermChecklist(otherTermOptions, otherTermOptions.map((option) => option.label), false, ''),
        preparation: serializeTermChecklist(preparationOptions, preparationOptions.map((option) => option.label), false, ''),
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
        templateKey: proposal.templateKey || 'standard',
        customerName: proposal.customerName || '',
        address: [proposal.addressLine1, proposal.addressLine2].filter(Boolean).join('\n'),
        proposalDate: proposal.proposalDate || '',
        volumeMin: proposal.volumeMin,
        volumeMax: proposal.volumeMax,
        priceUsd: proposal.priceUsd,
        topPercent: proposal.topPercent,
        guarantee: proposal.guarantee,
        dueDay: proposal.dueDay,
        exchangeClause: proposal.exchangeClause,
        contractDuration: proposal.contractDuration ?? proposal.contractYears ?? 2,
        contractDurationUnit: proposal.contractDurationUnit || 'year',
        durationDetails: proposal.durationDetails || '',
        attentionTo: proposal.attentionTo || '',
        motherStation: proposal.motherStation || '',
        plantName: proposal.plantName || '',
        plantAddress: proposal.plantAddress || '',
        supplyPattern: proposal.supplyPattern || '',
        deliveryPoint: proposal.deliveryPoint || '',
        startDate: proposal.startDate || '',
        endDate: proposal.endDate || '',
        volumeDetails: proposal.volumeDetails || '',
        priceDetails: proposal.priceDetails || '',
        paymentTerms: proposal.paymentTerms || '',
        advantages: proposal.advantages || '',
        otherTerms: proposal.otherTerms || '',
        preparation: proposal.preparation || '',
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
        templateKey: form.templateKey,
        customerName: form.customerName,
        ...addressFields(form.address),
        proposalDate: form.proposalDate,
        volumeMin: form.volumeMin,
        volumeMax: form.volumeMax,
        priceUsd: form.priceUsd,
        topPercent: form.topPercent,
        guarantee: form.guarantee,
        dueDay: form.dueDay,
        exchangeClause: form.exchangeClause,
        contractDuration: form.contractDuration,
        contractDurationUnit: form.contractDurationUnit,
        durationDetails: form.durationDetails,
        attentionTo: form.attentionTo,
        motherStation: form.motherStation,
        plantName: form.plantName,
        plantAddress: form.plantAddress,
        supplyPattern: form.supplyPattern,
        deliveryPoint: form.deliveryPoint,
        startDate: form.startDate,
        endDate: form.endDate,
        volumeDetails: form.volumeDetails,
        priceDetails: form.priceDetails,
        paymentTerms: form.paymentTerms,
        advantages: form.advantages,
        otherTerms: form.otherTerms,
        preparation: form.preparation,
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
    if (proposal.status === 'draft') return { action: 'submit', label: 'Kirim untuk persetujuan Admin' };
    if (proposal.status === 'review') {
        const role = proposal.approvalRoute?.includes('admin')
            && !proposal.approvals?.includes('admin')
            ? 'admin'
            : null;
        return role ? { action: 'approve', label: `Setujui sebagai ${roleLabels[role]}` } : null;
    }
    if (proposal.status === 'approved') return { action: 'mark_sent', label: 'Tandai telah dikirim' };
    if (proposal.status === 'sent') return { action: 'customer_approved', label: 'Pelanggan menyetujui' };
    if (proposal.status === 'negotiation') return { action: 'revise', label: 'Buat revisi' };
    if (proposal.status === 'customer_approved') return { action: 'activate', label: 'Aktifkan pelanggan' };
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

function TextAreaField({ label, rows = 3, ...props }) {
    return (
        <label className="sph-field">
            <span>{label}</span>
            <textarea rows={rows} {...props} />
        </label>
    );
}

function ObligationChecklist({
    title,
    value,
    options,
    onChange,
    otherPrompt = 'Jelaskan kewajiban lainnya',
    otherMaxLength = 10000,
    structured = false,
}) {
    const parsed = parseObligations(value, options);
    const serialize = (selected, otherSelected, otherText) => (
        structured
            ? serializeTermChecklist(options, selected, otherSelected, otherText)
            : serializeObligations(options, selected, otherSelected, otherText)
    );

    function updateSelection(label, checked) {
        const selected = checked
            ? [...parsed.selected, label]
            : parsed.selected.filter((item) => item !== label);
        onChange(serialize(
            selected,
            parsed.otherSelected,
            parsed.otherText,
        ));
    }

    function updateOther(checked) {
        onChange(serialize(
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
                    <span>{otherPrompt}</span>
                    <textarea
                        rows="3"
                        maxLength={otherMaxLength}
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
    const [proposal, setProposal] = useState(null);
    const [form, setForm] = useState(blankProposal);
    const [search, setSearch] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [returnReason, setReturnReason] = useState('');
    const [actualVolume, setActualVolume] = useState('');
    const [renewalTerms, setRenewalTerms] = useState({
        startDate: '',
        endDate: '',
        contractDuration: '',
        contractDurationUnit: 'year',
    });
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');

    const isAdmin = user.role === 'admin';
    const isTermTemplate = form.templateKey === 'term_description';
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
            setRenewalTerms({
                startDate: '',
                endDate: '',
                contractDuration: selected.contractDuration || '',
                contractDurationUnit: selected.contractDurationUnit || 'year',
            });
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

    function updateRenewalField(event) {
        const { name, value } = event.target;
        setRenewalTerms((current) => ({ ...current, [name]: value }));
    }

    async function saveDraft(event) {
        event.preventDefault();
        setBusy(true);
        setError('');
        setNotice('');
        const payload = {
            ...form,
            ...addressFields(form.address),
            volumeMin: Number(form.volumeMin),
            volumeMax: Number(form.volumeMax),
            priceUsd: Number(form.priceUsd),
            topPercent: Number(form.topPercent),
            dueDay: Number(form.dueDay),
            contractDuration: Number(form.contractDuration),
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
            setRenewalTerms({
                startDate: '',
                endDate: '',
                contractDuration: updated.contractDuration || '',
                contractDurationUnit: updated.contractDurationUnit || 'year',
            });
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
        inactive: 0,
    });
    const activeProposals = proposals.filter((item) => item.status === 'active');
    const contractsNeedingAttention = activeProposals.filter(
        (item) => item.contractExpired || item.contractDatesMissing,
    );
    const averagePrice = proposals.length
        ? proposals.reduce((total, item) => total + Number(item.priceUsd || 0), 0) / proposals.length
        : 0;
    const action = proposal ? nextAction(proposal) : null;
    const canApprove = proposal?.status === 'review'
        && isAdmin
        && proposal.approvalRoute?.includes('admin')
        && !proposal.approvals?.includes('admin');

    return (
        <main className="sph-app">
            <header className="sph-topbar">
                <a className="sph-brand" href="/sph" aria-label="SPH CNG Reethau">
                    <img src={logoImage} alt="Reethau Clean Energy" />
                </a>
                <div className="sph-topbar-right">
                    <span className="sph-user-chip">
                        <strong>{user.username}</strong>
                        <small>Admin</small>
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
                    {isAdmin && (
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
                    ].map(([tab, label]) => (
                        <button
                            key={tab}
                            type="button"
                            className={activeTab === tab ? 'active' : ''}
                            onClick={() => setActiveTab(tab)}
                        >
                            {label}
                        </button>
                    ))}
                </nav>

                {error && <div className="sph-alert error" role="alert">{error}</div>}
                {notice && <div className="sph-alert success" role="status">{notice}</div>}

                {activeTab === 'dashboard' && (
                    <section className="sph-dashboard">
                        {contractsNeedingAttention.length > 0 && (
                            <section className="sph-alert error" role="alert">
                                <strong>Perhatian masa kontrak</strong>
                                {contractsNeedingAttention.map((item) => (
                                    <p key={item.id}>
                                        <strong>{item.customerName} · {item.number}</strong>
                                        {' — '}
                                        {item.contractExpired
                                            ? `Kontrak berakhir ${formatUpdatedAt(item.endDate)}.`
                                            : 'Tanggal kontrak belum lengkap.'}
                                        {item.contractDatesMissing && item.contractExpired
                                            ? ' Tanggal mulai juga belum diisi.'
                                            : ''}
                                        {' '}
                                        <button className="sph-row-button" type="button" disabled={busy} onClick={() => openProposal(item.id, 'process')}>Tinjau</button>
                                    </p>
                                ))}
                            </section>
                        )}
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
                                    {isAdmin && proposals.length === 0 && (
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
                                                            <button className="sph-row-button" type="button" disabled={busy} onClick={() => openProposal(item.id, isAdmin ? 'editor' : 'process')}>Buka</button>
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
                                                    <span>{item.number} · {formatUpdatedAt(item.startDate)} – {formatUpdatedAt(item.endDate)}</span>
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
                        {proposal?.status === 'active' ? (
                            <div className="sph-readonly">
                                <strong>SPH berstatus Aktif tidak dapat diedit.</strong>
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
                                        <label className="sph-field"><span>Template surat</span><select name="templateKey" value={form.templateKey} onChange={updateField}><option value="standard">Template Standar</option><option value="term_description">Template Term / Deskripsi (PDF contoh)</option></select></label>
                                        <TextField label={isTermTemplate ? 'Pembeli / Kepada Yth *' : 'Nama pelanggan *'} name="customerName" value={form.customerName} onChange={updateField} required maxLength={255} />
                                        <TextField label="Tanggal penawaran *" name="proposalDate" type="date" value={form.proposalDate} onChange={updateField} required />
                                        {isTermTemplate
                                            ? <TextAreaField label="Alamat penerima" name="address" rows={3} value={form.address} onChange={updateField} maxLength={2000} placeholder="Nama jalan, kota, dan provinsi; gunakan baris baru untuk alamat terpisah" />
                                            : <TextField label="Alamat" name="address" value={form.address} onChange={updateField} maxLength={2000} placeholder="Jalan Akses Tol Cibitung No.82, Gandasari, Kecamatan Cikarang Barat, Kabupaten Bekasi, Jawa Barat 17530" />}
                                        {isTermTemplate && (
                                            <TextField label="Perhatian (Up)" name="attentionTo" value={form.attentionTo} onChange={updateField} maxLength={255} placeholder="Nama penerima surat" />
                                        )}
                                    </div>
                                </div>
                                <div className="sph-form-section">
                                    <h3>{isTermTemplate ? 'Volume dan Harga CNG' : 'Volume dan harga'}</h3>
                                    <div className="sph-form-grid">
                                        <TextField label={isTermTemplate ? 'Volume minimum internal (MMBTU/hari) *' : 'Volume minimum (MMBTU/hari) *'} name="volumeMin" type="number" min="0.01" step="0.01" value={form.volumeMin} onChange={updateField} required />
                                        <TextField label={isTermTemplate ? 'Volume maksimum internal (MMBTU/hari) *' : 'Volume maksimum (MMBTU/hari) *'} name="volumeMax" type="number" min="0.01" step="0.01" value={form.volumeMax} onChange={updateField} required />
                                        <TextField label="Harga (USD/MMBTU) *" name="priceUsd" type="number" min="0.01" step="0.01" value={form.priceUsd} onChange={updateField} required />
                                        {!isTermTemplate && <TextField label="Take-or-pay (%)" name="topPercent" type="number" min="0" max="100" step="0.01" value={form.topPercent} onChange={updateField} required />}
                                    </div>
                                    <p className="sph-form-hint">
                                        {isTermTemplate
                                            ? 'PDF memakai Rincian Volume. Jika Rincian Harga sudah mencantumkan harga dasar, nilainya tidak ditambahkan ulang. Produk dan penjual tetap.'
                                            : 'Semua penawaran memerlukan persetujuan Admin.'}
                                    </p>
                                </div>
                                <div className="sph-form-section">
                                    <h3>Ketentuan kontrak</h3>
                                    <div className="sph-form-grid">
                                        {!isTermTemplate && (
                                            <>
                                                <label className="sph-field"><span>Jaminan</span><select name="guarantee" value={form.guarantee} onChange={updateField}><option>Cash Deposit</option><option>Bank Guarantee</option><option>Parent Company Guarantee</option><option>N/A</option></select></label>
                                                <TextField label="Tanggal pembayaran setiap bulan" name="dueDay" type="number" min="1" max="28" value={form.dueDay} onChange={updateField} required />
                                            </>
                                        )}
                                        <label className="sph-field sph-duration-control">
                                            <span>Jangka waktu</span>
                                            <div>
                                                <input
                                                    aria-label="Nilai jangka waktu"
                                                    name="contractDuration"
                                                    type="number"
                                                    min="1"
                                                    max={form.contractDurationUnit === 'year' ? 15 : 5475}
                                                    step="1"
                                                    value={form.contractDuration}
                                                    onChange={updateField}
                                                    required
                                                />
                                                <select
                                                    aria-label="Satuan jangka waktu"
                                                    name="contractDurationUnit"
                                                    value={form.contractDurationUnit}
                                                    onChange={updateField}
                                                >
                                                    <option value="year">Tahun</option>
                                                    <option value="day">Hari</option>
                                                </select>
                                            </div>
                                        </label>
                                        <TextField label="Tanggal mulai kontrak" name="startDate" type="date" value={form.startDate} onChange={updateField} />
                                        <TextField label="Tanggal selesai kontrak" name="endDate" type="date" value={form.endDate} onChange={updateField} />
                                        <label className="sph-checkbox"><input type="checkbox" name="exchangeClause" checked={form.exchangeClause} onChange={updateField} /><span>Klausul tukar menukar berlaku</span></label>
                                    </div>
                                    <p className="sph-form-hint">Tanggal mulai dan selesai digunakan untuk memantau masa kontrak. Keduanya wajib dilengkapi sebelum pelanggan diaktifkan.</p>
                                </div>
                                {isTermTemplate ? (
                                    <div className="sph-form-section">
                                        <h3>Term / Deskripsi pada PDF</h3>
                                        <div className="sph-form-grid sph-form-grid-single">
                                            <TextField label="Lokasi Mother Station" name="motherStation" value={form.motherStation} onChange={updateField} maxLength={500} placeholder="Contoh: Wunut - Sidoarjo, Jawa Timur" />
                                            <TextAreaField label="Pola Supply" name="supplyPattern" value={form.supplyPattern} onChange={updateField} maxLength={2000} placeholder="Cara dan pola pasokan CNG" />
                                            <TextAreaField label="Titik Penyerahan" name="deliveryPoint" value={form.deliveryPoint} onChange={updateField} maxLength={2000} placeholder="Lokasi penyerahan gas" />
                                            <TextField label="Nama plant customer" name="plantName" value={form.plantName} onChange={updateField} maxLength={255} placeholder="Contoh: Plant Gresik" />
                                            <TextAreaField label="Alamat plant supply" name="plantAddress" value={form.plantAddress} onChange={updateField} maxLength={2000} placeholder="Alamat lokasi plant, pisahkan baris sesuai format surat" />
                                            <TextAreaField label="Rincian Volume (lokasi / periode / satuan)" name="volumeDetails" value={form.volumeDetails} onChange={updateField} maxLength={5000} placeholder="Lokasi, jumlah, satuan, atau periode pasokan" />
                                            <TextAreaField label="Evaluasi / Ketentuan Jangka Waktu" name="durationDetails" value={form.durationDetails} onChange={updateField} maxLength={5000} placeholder="Ketentuan evaluasi selama jangka waktu kontrak" />
                                            <TextAreaField label="Rincian Harga (terbilang / komponen / pajak)" name="priceDetails" value={form.priceDetails} onChange={updateField} maxLength={5000} placeholder="Contoh: harga terbilang, fasilitas yang termasuk, serta pajak yang belum termasuk" />
                                            <ObligationChecklist
                                                title="Pembayaran"
                                                value={form.paymentTerms}
                                                options={paymentTermOptions}
                                                structured
                                                otherPrompt="Jelaskan ketentuan pembayaran lainnya"
                                                otherMaxLength={5000}
                                                onChange={(value) => setForm((current) => ({ ...current, paymentTerms: value }))}
                                            />
                                            <ObligationChecklist
                                                title="Keunggulan"
                                                value={form.advantages}
                                                options={advantageOptions}
                                                structured
                                                otherPrompt="Jelaskan keunggulan lainnya"
                                                onChange={(value) => setForm((current) => ({ ...current, advantages: value }))}
                                            />
                                            <ObligationChecklist
                                                title="Ketentuan Lain"
                                                value={form.otherTerms}
                                                options={otherTermOptions}
                                                structured
                                                otherPrompt="Jelaskan ketentuan lainnya"
                                                onChange={(value) => setForm((current) => ({ ...current, otherTerms: value }))}
                                            />
                                            <ObligationChecklist
                                                title="Preparation"
                                                value={form.preparation}
                                                options={preparationOptions}
                                                structured
                                                otherPrompt="Jelaskan preparation lainnya"
                                                otherMaxLength={5000}
                                                onChange={(value) => setForm((current) => ({ ...current, preparation: value }))}
                                            />
                                        </div>
                                    </div>
                                ) : (
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
                                )}
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
                                    <div><span>Periode kontrak</span><strong>{formatUpdatedAt(proposal.startDate)} – {formatUpdatedAt(proposal.endDate)}</strong></div>
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

                                {proposal.status === 'active' && isAdmin && (proposal.contractExpired || proposal.contractDatesMissing) && (
                                    <section className="sph-expiry-panel" aria-live="polite">
                                        <h3>{proposal.contractExpired ? 'Kontrak telah melewati tanggal selesai' : 'Tanggal kontrak belum lengkap'}</h3>
                                        <p>
                                            {proposal.contractExpired
                                                ? 'Pilih untuk memperpanjang atau menonaktifkan kontrak. Perpanjangan menyimpan periode dan jangka waktu baru.'
                                                : 'Lengkapi tanggal kontrak lama agar sistem dapat memantau masa berlakunya.'}
                                        </p>
                                        {proposal.contractDatesMissing && (
                                            <div className="sph-contract-date-fields">
                                                <TextField label="Tanggal mulai kontrak" name="startDate" type="date" value={form.startDate} onChange={updateField} />
                                                <TextField label="Tanggal selesai kontrak" name="endDate" type="date" value={form.endDate} onChange={updateField} />
                                                <button
                                                    className="sph-secondary"
                                                    type="button"
                                                    disabled={busy || !form.startDate || !form.endDate}
                                                    onClick={() => performAction('record_contract_dates', {
                                                        startDate: form.startDate,
                                                        endDate: form.endDate,
                                                    })}
                                                >
                                                    Simpan tanggal kontrak
                                                </button>
                                            </div>
                                        )}
                                        {proposal.contractExpired && (
                                            <div className="sph-contract-date-fields">
                                                <TextField label="Tanggal mulai perpanjangan *" name="startDate" type="date" value={renewalTerms.startDate} onChange={updateRenewalField} />
                                                <TextField label="Tanggal selesai perpanjangan *" name="endDate" type="date" value={renewalTerms.endDate} onChange={updateRenewalField} />
                                                <label className="sph-field sph-duration-control">
                                                    <span>Jangka waktu baru *</span>
                                                    <div>
                                                        <input
                                                            name="contractDuration"
                                                            type="number"
                                                            min="1"
                                                            max={renewalTerms.contractDurationUnit === 'year' ? 15 : 5475}
                                                            value={renewalTerms.contractDuration}
                                                            onChange={updateRenewalField}
                                                        />
                                                        <select name="contractDurationUnit" value={renewalTerms.contractDurationUnit} onChange={updateRenewalField}>
                                                            <option value="year">Tahun</option>
                                                            <option value="day">Hari</option>
                                                        </select>
                                                    </div>
                                                </label>
                                                <button
                                                    className="sph-primary"
                                                    type="button"
                                                    disabled={busy || !renewalTerms.startDate || !renewalTerms.endDate || !renewalTerms.contractDuration}
                                                    onClick={() => performAction('renew_contract', renewalTerms)}
                                                >
                                                    Perpanjang kontrak
                                                </button>
                                                <button className="sph-secondary" type="button" disabled={busy} onClick={() => performAction('deactivate_contract')}>
                                                    Tidak diperpanjang
                                                </button>
                                            </div>
                                        )}
                                    </section>
                                )}

                                <div className="sph-action-area">
                                    {proposal.status !== 'active' && isAdmin && (
                                        <button
                                            className="sph-secondary"
                                            type="button"
                                            disabled={busy}
                                            onClick={() => setActiveTab('editor')}
                                        >
                                            Edit SPH
                                        </button>
                                    )}
                                    {action?.action === 'activate' && isAdmin && (
                                        <div className="sph-contract-date-fields">
                                            <TextField label="Tanggal mulai kontrak *" name="startDate" type="date" value={form.startDate} onChange={updateField} />
                                            <TextField label="Tanggal selesai kontrak *" name="endDate" type="date" value={form.endDate} onChange={updateField} />
                                            <button
                                                className="sph-primary"
                                                type="button"
                                                disabled={busy || !form.startDate || !form.endDate}
                                                onClick={() => performAction('activate', {
                                                    startDate: form.startDate,
                                                    endDate: form.endDate,
                                                })}
                                            >
                                                Aktifkan pelanggan
                                            </button>
                                        </div>
                                    )}
                                    {action && action.action !== 'activate' && isAdmin && (action.action !== 'approve' || canApprove) && (
                                        <button className="sph-primary" type="button" disabled={busy} onClick={() => performAction(action.action)}>
                                            {action.label}
                                        </button>
                                    )}
                                    {proposal.status === 'review' && canApprove && (
                                        <div className="sph-return-action">
                                            <input value={returnReason} onChange={(event) => setReturnReason(event.target.value)} placeholder="Alasan pengembalian" maxLength={2000} />
                                            <button className="sph-secondary" type="button" disabled={busy || !returnReason.trim()} onClick={() => performAction('return', { reason: returnReason })}>Kembalikan</button>
                                        </div>
                                    )}
                                    {proposal.status === 'sent' && isAdmin && (
                                        <button className="sph-secondary" type="button" disabled={busy} onClick={() => performAction('negotiation')}>Mulai negosiasi</button>
                                    )}
                                    {proposal.status === 'active' && isAdmin && (
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
