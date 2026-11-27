import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { api } from '../api';
import '../cooperation.css';

const leadingColumns = [
    { key: 'code', label: 'Code' },
    { key: 'customer', label: 'Customer' },
    { key: 'address', label: 'Address' },
    { key: 'mother_station', label: 'Mother Station' },
    { key: 'forms_of_cooperation', label: 'Forms of cooperation' },
    { key: 'agreement_number', label: 'Agreement Number' },
];

const volumeColumns = [
    { key: 'volume_min_mmbtu', label: 'Min MMBTU' },
    { key: 'volume_max_mmbtu', label: 'Max MMBTU' },
    { key: 'volume_min_sm3', label: 'Min Sm3' },
    { key: 'volume_max_sm3', label: 'Max Sm3' },
    { key: 'volume_min_nm3', label: 'Min Nm3' },
    { key: 'volume_max_nm3', label: 'Max Nm3' },
];

const priceColumns = [
    { key: 'price_usd_mmbtu', label: '$/MMBTU' },
    { key: 'price_usd_m3', label: '$/m3' },
    { key: 'price_idr_m3', label: 'Rp/m3' },
];

const trailingColumns = [
    { key: 'kurs', label: 'KURS' },
    { key: 'invoicing', label: 'Invoicing' },
    { key: 'terms_of_payment', label: 'Terms of Payment' },
    { key: 'contract_signed', label: 'Contrac Signed' },
    { key: 'gas_in', label: 'Gas In' },
    { key: 'end_of_contract', label: 'End of Contrac' },
    { key: 'remarks', label: 'Remarks' },
    { key: 'pic_customer', label: 'PIC Customer' },
    { key: 'telephone', label: 'Telepon' },
];

const contractFields = [
    ...leadingColumns,
    ...volumeColumns,
    ...priceColumns,
    ...trailingColumns,
].map(({ key }) => key);

const noWrapFields = new Set([
    ...volumeColumns.map(({ key }) => key),
    ...priceColumns.map(({ key }) => key),
    'kurs',
    'contract_signed',
    'gas_in',
    'end_of_contract',
    'telephone',
]);

const statusFilters = [
    { key: 'all', label: 'Semua' },
    { key: 'active', label: 'Aktif' },
    { key: 'soon', label: 'Segera berakhir' },
    { key: 'ended', label: 'Berakhir' },
    { key: 'undated', label: 'Tanggal akhir kosong' },
];

function MetricCard({ label, value, caption, tone }) {
    return (
        <article className={`cooperation-metric ${tone || ''}`}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{caption}</small>
        </article>
    );
}

function PageHeader({ eyebrow, title, description, children }) {
    return (
        <header className="cooperation-page-heading">
            <div>
                <p className="cooperation-eyebrow">{eyebrow}</p>
                <h1>{title}</h1>
                <p>{description}</p>
            </div>
            {children}
        </header>
    );
}

function getCounts(contracts) {
    return contracts.reduce((counts, contract) => {
        counts.all += 1;
        if (contract.status === 'undated') counts.undated += 1;
        if (contract.status === 'ended') counts.ended += 1;
        if (contract.status === 'active') {
            counts.active += 1;
            if (contract.days_remaining <= 90) counts.soon += 1;
        }
        return counts;
    }, { all: 0, active: 0, soon: 0, ended: 0, undated: 0 });
}

function getCustomerKey(contract) {
    const customer = String(contract.customer || '').trim();
    if (customer) return `customer:${customer.toLocaleLowerCase('id-ID')}`;

    const code = String(contract.code || '').trim();
    if (code) return `code:${code.toLocaleLowerCase('id-ID')}`;

    return `contract:${contract.id}`;
}

function getUniqueCustomerCounts(contracts) {
    return {
        all: new Set(contracts.map(getCustomerKey)).size,
        ended: new Set(
            contracts.filter((contract) => contract.status === 'ended').map(getCustomerKey),
        ).size,
    };
}

function CooperationList({ contracts, loading, error, canEdit, onImport, importing }) {
    const [activeFilter, setActiveFilter] = useState('all');
    const [search, setSearch] = useState('');
    const fileInput = useRef(null);
    const counts = useMemo(() => getCounts(contracts), [contracts]);
    const customerCounts = useMemo(() => getUniqueCustomerCounts(contracts), [contracts]);
    const pics = useMemo(() => [...new Set(
        contracts.map((contract) => contract.pic_customer).filter(Boolean),
    )].sort((a, b) => a.localeCompare(b, 'id-ID')), [contracts]);
    const [pic, setPic] = useState('all');
    const rows = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('id-ID');
        return contracts.filter((contract) => {
            const matchesText = !query || contractFields
                .some((field) => String(contract[field] || '').toLocaleLowerCase('id-ID').includes(query));
            const matchesStatus = activeFilter === 'all'
                || contract.status === activeFilter
                || (activeFilter === 'soon' && contract.status === 'active' && contract.days_remaining <= 90);
            return matchesText && matchesStatus && (pic === 'all' || contract.pic_customer === pic);
        });
    }, [activeFilter, contracts, pic, search]);

    return (
        <section className="cooperation-page">
            <PageHeader
                eyebrow="KERJA SAMA CUSTOMER"
                title="Daftar Kerja Sama"
                description="Data kontrak mengikuti kolom pada workbook sumber. Nilai yang kosong tetap kosong."
            >
                {canEdit && (
                    <>
                        <input
                            ref={fileInput}
                            className="cooperation-file-input"
                            type="file"
                            accept=".xlsx"
                            aria-label="Pilih workbook kerja sama"
                            onChange={(event) => {
                                const file = event.target.files?.[0];
                                event.target.value = '';
                                if (file) onImport(file);
                            }}
                        />
                        <button
                            className="cooperation-import-button"
                            type="button"
                            disabled={importing}
                            onClick={() => fileInput.current?.click()}
                        >
                            {importing ? 'Mengimpor...' : 'Impor workbook Excel'}
                        </button>
                    </>
                )}
            </PageHeader>

            {error && <div className="cooperation-error" role="alert">{error}</div>}
            <section className="cooperation-metrics" aria-label="Ringkasan kerja sama">
                <MetricCard label="TOTAL KONTRAK" value={customerCounts.all} caption="Customer unik" tone="blue" />
                <MetricCard label="AKTIF" value={counts.active} caption="Tanggal akhir belum lewat" tone="green" />
                <MetricCard label="SEGERA BERAKHIR" value={counts.soon} caption="Dalam 90 hari" tone="orange" />
                <MetricCard label="BERAKHIR" value={customerCounts.ended} caption="Customer unik dengan kontrak berakhir" tone="red" />
            </section>

            <section className="cooperation-panel cooperation-register">
                <div className="cooperation-status-tabs" aria-label="Filter status kerja sama">
                    {statusFilters.map((filter) => (
                        <button
                            key={filter.key}
                            type="button"
                            className={activeFilter === filter.key ? 'active' : ''}
                            aria-pressed={activeFilter === filter.key}
                            onClick={() => setActiveFilter(filter.key)}
                        >
                            {filter.label} <span>{counts[filter.key]}</span>
                        </button>
                    ))}
                </div>
                <div className="cooperation-filters">
                    <label className="cooperation-search">
                        <span className="sr-only">Cari isi data kerja sama</span>
                        <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Cari customer, kode, alamat, nomor perjanjian..."
                        />
                    </label>
                    <label>
                        <span className="sr-only">PIC Customer</span>
                        <select value={pic} onChange={(event) => setPic(event.target.value)}>
                            <option value="all">Semua PIC</option>
                            {pics.map((name) => <option key={name} value={name}>{name}</option>)}
                        </select>
                    </label>
                </div>
                <div className="cooperation-table-scroll">
                    <table className="cooperation-table">
                        <thead>
                            <tr>
                                {leadingColumns.map((column) => (
                                    <th key={column.key} rowSpan="2">{column.label}</th>
                                ))}
                                <th colSpan={volumeColumns.length}>Volume</th>
                                <th colSpan={priceColumns.length}>Price</th>
                                {trailingColumns.map((column) => (
                                    <th key={column.key} rowSpan="2">{column.label}</th>
                                ))}
                            </tr>
                            <tr>
                                {volumeColumns.map((column) => <th key={column.key}>{column.label}</th>)}
                                {priceColumns.map((column) => <th key={column.key}>{column.label}</th>)}
                            </tr>
                        </thead>
                        <tbody>
                            {loading && <tr><td className="cooperation-empty" colSpan="24">Memuat data kerja sama...</td></tr>}
                            {!loading && rows.map((contract) => (
                                <tr key={contract.id}>
                                    {contractFields.map((field) => {
                                        const value = contract[field] || '';
                                        return (
                                            <td key={field}>
                                                <span
                                                    className={`cooperation-cell-text${noWrapFields.has(field) ? ' no-wrap' : ''}`}
                                                    title={value || undefined}
                                                >
                                                    {value}
                                                </span>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                            {!loading && rows.length === 0 && (
                                <tr>
                                    <td className="cooperation-empty" colSpan="24">
                                        {contracts.length ? 'Tidak ada data yang sesuai dengan filter.' : 'Belum ada data. Admin dapat mengimpor workbook Excel untuk memuat daftar kerja sama.'}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="cooperation-table-foot">
                    <span>Menampilkan {rows.length} dari {contracts.length} kontrak</span>
                    <span>Tanggal akhir kosong: {counts.undated}</span>
                </div>
            </section>
        </section>
    );
}

function ExpiryDashboard({ contracts, loading }) {
    const counts = useMemo(() => getCounts(contracts), [contracts]);
    const customerCounts = useMemo(() => getUniqueCustomerCounts(contracts), [contracts]);
    const months = useMemo(() => {
        const now = new Date();
        return Array.from({ length: 6 }, (_, index) => {
            const month = new Date(now.getFullYear(), now.getMonth() + index, 1);
            const key = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}`;
            const monthContracts = contracts
                .filter((contract) => contract.end_contract_date?.slice(0, 7) === key)
                .sort((a, b) => a.end_contract_date.localeCompare(b.end_contract_date));
            return {
                key,
                label: new Intl.DateTimeFormat('id-ID', { month: 'short', year: 'numeric' }).format(month),
                detailLabel: new Intl.DateTimeFormat('id-ID', { month: 'long', year: 'numeric' }).format(month),
                contracts: monthContracts,
                value: monthContracts.length,
            };
        });
    }, [contracts]);
    const maxMonthCount = Math.max(1, ...months.map((month) => month.value));

    return (
        <section className="cooperation-page">
            <PageHeader
                eyebrow="PEMANTAUAN KONTRAK"
                title="Masa Berlaku"
                description="Tanggal akhir berupa bulan dan tahun dihitung sampai hari terakhir bulan tersebut."
            />
            <section className="cooperation-metrics" aria-label="Ringkasan masa berlaku">
                <MetricCard label="TOTAL KONTRAK" value={customerCounts.all} caption="Customer unik" tone="blue" />
                <MetricCard label="AKTIF" value={counts.active} caption="Tanggal akhir belum lewat" tone="green" />
                <MetricCard label="SEGERA BERAKHIR" value={counts.soon} caption="Dalam 90 hari" tone="orange" />
                <MetricCard label="BERAKHIR" value={customerCounts.ended} caption="Customer unik dengan kontrak berakhir" tone="red" />
            </section>
            {loading ? (
                <div className="cooperation-panel cooperation-dashboard-empty">Memuat data kerja sama...</div>
            ) : contracts.length === 0 ? (
                <div className="cooperation-panel cooperation-dashboard-empty">Belum ada data kerja sama. Admin dapat mengimpor workbook dari halaman Daftar Kerja Sama.</div>
            ) : (
                <div className="cooperation-expiry-grid">
                    <section className="cooperation-panel cooperation-chart-panel">
                        <div className="cooperation-panel-heading">
                            <h2>Dokumen berakhir per bulan</h2>
                            <span>6 bulan ke depan</span>
                        </div>
                        <div className="cooperation-bars" role="img" aria-label="Jumlah kontrak yang berakhir dalam enam bulan ke depan">
                            {months.map((month) => (
                                <div className="cooperation-bar-column" key={month.key}>
                                    <strong>{month.value}</strong>
                                    <div className="cooperation-bar-track">
                                        <span style={{ height: `${month.value ? Math.max((month.value / maxMonthCount) * 92, 8) : 3}px` }} />
                                    </div>
                                    <small>{month.label}</small>
                                </div>
                            ))}
                        </div>
                    </section>
                    <section className="cooperation-panel cooperation-monthly-details">
                        <div className="cooperation-panel-heading">
                            <h2>Rincian dokumen berakhir per bulan</h2>
                            <span>Pilih bulan untuk melihat dokumennya</span>
                        </div>
                        <div className="cooperation-month-breakdown">
                            {months.map((month, index) => (
                                <details
                                    className="cooperation-month-detail"
                                    key={month.key}
                                    open={index === 0 && month.value > 0}
                                >
                                    <summary>
                                        <strong>{month.detailLabel}</strong>
                                        <span>{month.value} dokumen</span>
                                    </summary>
                                    {month.value ? (
                                        <div className="cooperation-attention-list">
                                            {month.contracts.map((contract) => (
                                                <article key={contract.id}>
                                                    <div>
                                                        <strong>{contract.customer || contract.code || 'Customer tidak tercatat'}</strong>
                                                        <small>{contract.agreement_number || contract.code || 'Nomor perjanjian tidak tercatat'}</small>
                                                    </div>
                                                    <span className="cooperation-month-contract-date">
                                                        {contract.end_of_contract || contract.end_contract_date}
                                                    </span>
                                                </article>
                                            ))}
                                        </div>
                                    ) : (
                                        <p className="cooperation-month-empty">Tidak ada dokumen yang berakhir pada bulan ini.</p>
                                    )}
                                </details>
                            ))}
                        </div>
                    </section>
                </div>
            )}
        </section>
    );
}

export default function CooperationPage() {
    const location = useLocation();
    const navigate = useNavigate();
    const { canEdit } = useOutletContext();
    const [contracts, setContracts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [noticeError, setNoticeError] = useState(false);
    const [importing, setImporting] = useState(false);
    const isExpiry = location.pathname.endsWith('/masa-berlaku');

    const refreshContracts = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            setContracts(await api('/api/cooperation/contracts'));
            return true;
        } catch (requestError) {
            setError(requestError.message || 'Data kerja sama gagal dimuat.');
            return false;
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (!canEdit && !isExpiry) return;
        refreshContracts();
    }, [canEdit, isExpiry, refreshContracts]);

    async function importWorkbook(file) {
        if (!window.confirm('Impor workbook ini dan mengganti seluruh data kerja sama yang tersimpan?')) return;
        setImporting(true);
        setNotice('');
        setNoticeError(false);
        try {
            const formData = new FormData();
            formData.append('file', file);
            const result = await api('/api/cooperation/import', {
                method: 'POST',
                body: formData,
                signal: AbortSignal.timeout(60000),
            });
            if (await refreshContracts()) {
                setNotice(`${result.imported} kontrak berhasil diimpor dari ${result.filename}.`);
            } else {
                setNotice('Data berhasil diimpor, tetapi daftar tidak dapat dimuat ulang. Muat ulang halaman.');
                setNoticeError(true);
            }
        } catch (requestError) {
            setNotice(requestError.message || 'Impor workbook gagal.');
            setNoticeError(true);
        } finally {
            setImporting(false);
        }
    }

    if (!canEdit && !isExpiry) {
        return <Navigate to="/kerja-sama/masa-berlaku" replace />;
    }

    return (
        <div className="cooperation-workspace">
            {canEdit && (
                <nav className="cooperation-tabs" aria-label="Navigasi kerja sama">
                    <button
                        type="button"
                        className={!isExpiry ? 'active' : ''}
                        onClick={() => navigate('/kerja-sama')}
                    >
                        Daftar kerja sama
                    </button>
                    <button
                        type="button"
                        className={isExpiry ? 'active' : ''}
                        onClick={() => navigate('/kerja-sama/masa-berlaku')}
                    >
                        Masa berlaku
                    </button>
                </nav>
            )}
            {notice && (
                <div className={`cooperation-notice${noticeError ? ' error' : ''}`} role={noticeError ? 'alert' : 'status'}>
                    {notice}
                </div>
            )}
            {isExpiry
                ? <ExpiryDashboard contracts={contracts} loading={loading} />
                : (
                    <CooperationList
                        contracts={contracts}
                        loading={loading}
                        error={error}
                        canEdit={canEdit}
                        onImport={importWorkbook}
                        importing={importing}
                    />
                )}
        </div>
    );
}
