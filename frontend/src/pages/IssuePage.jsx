import { useCallback, useEffect, useMemo, useState } from 'react';
import { Doughnut, Line } from 'react-chartjs-2';
import {
    ArcElement,
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
} from 'chart.js';
import { api } from '../api';
import SectionIcon from '../components/SectionIcon';

ChartJS.register(
    ArcElement,
    CategoryScale,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
);

const refreshInterval = 5 * 60 * 1000;
const pageSize = 8;
const statusColors = {
    Open: '#f0a43a',
    'In Progress': '#2685df',
    Closed: '#18a979',
};

function formatDate(value) {
    if (!value) return '—';
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString('id-ID', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
    });
}

function formatDateTime(value) {
    if (!value) return 'Belum tersinkron';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('id-ID', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function statusClass(status) {
    return status.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

function issueLinks(value) {
    return String(value || '')
        .split(/,\s*(?=https?:\/\/)/i)
        .map((url) => url.trim())
        .filter((url) => {
            try {
                return new URL(url).protocol === 'https:';
            } catch {
                return false;
            }
        });
}

function DetailField({ label, children }) {
    return (
        <div className="issue-detail-field">
            <span>{label}</span>
            <div>{children || '—'}</div>
        </div>
    );
}

function MetricCard({ tone, icon, label, value, note }) {
    return (
        <article className={`issue-metric ${tone}`}>
            <span className="issue-metric-icon" aria-hidden="true">{icon}</span>
            <div>
                <small>{label}</small>
                <strong>{value}</strong>
                <span>{note}</span>
            </div>
        </article>
    );
}

export default function IssuePage() {
    const [issues, setIssues] = useState([]);
    const [syncedAt, setSyncedAt] = useState('');
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [customerFilter, setCustomerFilter] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [typeFilter, setTypeFilter] = useState('');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [selectedId, setSelectedId] = useState('');
    const [page, setPage] = useState(1);

    const loadIssues = useCallback(async (forceRefresh = false) => {
        setRefreshing(true);
        try {
            const result = await api(
                `/api/issues${forceRefresh ? '?refresh=true' : ''}`,
                { signal: AbortSignal.timeout(40000) },
            );
            if (!result || !Array.isArray(result.issues)) {
                throw new Error('Format data Issue dari Google Sheets tidak valid.');
            }
            setIssues(result.issues);
            setSyncedAt(result.syncedAt || '');
            setError('');
        } catch (loadError) {
            setError(loadError.message || 'Data Issue gagal dimuat dari Google Sheets.');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        loadIssues(true);
        const timer = window.setInterval(() => loadIssues(false), refreshInterval);
        return () => window.clearInterval(timer);
    }, [loadIssues]);

    const customers = useMemo(
        () => [...new Set(issues.map((issue) => issue.customer).filter(Boolean))]
            .sort((a, b) => a.localeCompare(b, 'id')),
        [issues],
    );
    const types = useMemo(
        () => [...new Set(issues.map((issue) => issue.type).filter(Boolean))]
            .sort((a, b) => a.localeCompare(b, 'id')),
        [issues],
    );

    const visibleIssues = useMemo(() => {
        const query = search.trim().toLocaleLowerCase('id-ID');
        return issues.filter((issue) => {
            if (startDate && issue.date < startDate) return false;
            if (endDate && issue.date > endDate) return false;
            if (customerFilter && issue.customer !== customerFilter) return false;
            if (statusFilter && issue.status !== statusFilter) return false;
            if (typeFilter && issue.type !== typeFilter) return false;
            if (!query) return true;
            return [
                issue.customer,
                issue.customerPic,
                issue.type,
                issue.rootCause,
                issue.impact,
                issue.status,
            ].some((value) => String(value || '').toLocaleLowerCase('id-ID').includes(query));
        });
    }, [issues, search, customerFilter, statusFilter, typeFilter, startDate, endDate]);

    useEffect(() => setPage(1), [search, customerFilter, statusFilter, typeFilter, startDate, endDate]);

    const statusCounts = useMemo(() => visibleIssues.reduce((counts, issue) => {
        counts[issue.status] = (counts[issue.status] || 0) + 1;
        return counts;
    }, {}), [visibleIssues]);

    const trendEndDate = endDate || visibleIssues[0]?.date || issues[0]?.date || '';
    const trendDays = useMemo(() => {
        if (!trendEndDate) return [];
        const end = new Date(`${trendEndDate}T00:00:00Z`);
        return Array.from({ length: 7 }, (_, index) => {
            const day = new Date(end);
            day.setUTCDate(end.getUTCDate() - (6 - index));
            return day.toISOString().slice(0, 10);
        });
    }, [trendEndDate]);

    const trendData = useMemo(() => ({
        labels: trendDays.map((day) => formatDate(day)),
        datasets: Object.entries(statusColors).map(([status, color]) => ({
            label: status,
            data: trendDays.map((day) => visibleIssues.filter(
                (issue) => issue.date === day && issue.status === status,
            ).length),
            borderColor: color,
            backgroundColor: color,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.35,
        })),
    }), [trendDays, visibleIssues]);

    const statusEntries = Object.entries(statusCounts).sort((a, b) => b[1] - a[1]);
    const statusData = {
        labels: statusEntries.map(([status]) => status),
        datasets: [{
            data: statusEntries.map(([, count]) => count),
            backgroundColor: statusEntries.map(([status]) => statusColors[status] || '#82978a'),
            borderWidth: 0,
            hoverOffset: 4,
        }],
    };

    const pageCount = Math.max(1, Math.ceil(visibleIssues.length / pageSize));
    const pageIssues = visibleIssues.slice((page - 1) * pageSize, page * pageSize);
    const selectedIssue = visibleIssues.find((issue) => issue.id === selectedId) || visibleIssues[0];
    const openCount = visibleIssues.filter((issue) => issue.status === 'Open').length;
    const progressCount = visibleIssues.filter((issue) => issue.status === 'In Progress').length;
    const closedCount = visibleIssues.filter((issue) => issue.status === 'Closed').length;
    const firstItem = visibleIssues.length ? (page - 1) * pageSize + 1 : 0;
    const lastItem = Math.min(page * pageSize, visibleIssues.length);

    return (
        <div className="issue-page">
            <div className="issue-main">
                <header className="issue-header">
                    <div className="issue-heading">
                        <span className="issue-brand-icon" aria-hidden="true">▤</span>
                        <div>
                            <h1>Issue Management</h1>
                            <p>Monitoring dan tindak lanjut permasalahan customer</p>
                        </div>
                    </div>
                    <div className="issue-sync">
                        <button type="button" onClick={() => loadIssues(true)} disabled={refreshing}>
                            <span aria-hidden="true">{refreshing ? '◌' : '⟳'}</span>
                            {refreshing ? 'Menyinkronkan...' : 'Sinkronkan Google Sheets'}
                        </button>
                        <small>Terakhir sinkron: {formatDateTime(syncedAt)}</small>
                    </div>
                </header>

                {error && (
                    <div className="issue-alert" role="alert">
                        <span>{error}</span>
                        <button type="button" onClick={() => loadIssues(true)}>Coba lagi</button>
                    </div>
                )}

                <section className="issue-metrics" aria-label="Ringkasan issue">
                    <MetricCard tone="total" icon="▤" label="Total Issue" value={loading ? '…' : visibleIssues.length} note="Berdasarkan filter aktif" />
                    <MetricCard tone="open" icon="!" label="Open" value={loading ? '…' : openCount} note="Perlu ditindaklanjuti" />
                    <MetricCard tone="progress" icon="◷" label="In Progress" value={loading ? '…' : progressCount} note="Sedang ditangani" />
                    <MetricCard tone="closed" icon="✓" label="Closed" value={loading ? '…' : closedCount} note="Sesuai status spreadsheet" />
                </section>

                <section className="issue-charts">
                    <article className="issue-panel issue-trend-panel">
                        <h2>Tren Issue 7 Hari Terakhir</h2>
                        {trendDays.length ? (
                            <div className="issue-trend-chart">
                                <Line
                                    data={trendData}
                                    options={{
                                        responsive: true,
                                        maintainAspectRatio: false,
                                        interaction: { intersect: false, mode: 'index' },
                                        plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 7, boxHeight: 7, padding: 14, font: { size: 10 } } } },
                                        scales: {
                                            x: { grid: { display: false }, ticks: { maxRotation: 0, font: { size: 9 } } },
                                            y: { beginAtZero: true, ticks: { precision: 0, font: { size: 9 } }, grid: { color: '#edf2ee' } },
                                        },
                                    }}
                                />
                            </div>
                        ) : <p className="issue-empty-chart">Belum ada data untuk ditampilkan.</p>}
                    </article>

                    <article className="issue-panel issue-status-panel">
                        <h2>Issue Berdasarkan Status</h2>
                        {statusEntries.length ? (
                            <div className="issue-status-chart">
                                <div className="issue-doughnut">
                                    <Doughnut
                                        data={statusData}
                                        options={{
                                            cutout: '68%',
                                            maintainAspectRatio: true,
                                            plugins: { legend: { display: false }, tooltip: { enabled: true } },
                                        }}
                                    />
                                    <div><strong>{visibleIssues.length}</strong><span>Total Issue</span></div>
                                </div>
                                <div className="issue-status-legend">
                                    {statusEntries.map(([status, count]) => (
                                        <div key={status}>
                                            <i style={{ background: statusColors[status] || '#82978a' }} />
                                            <span>{status}</span>
                                            <b>{count} ({visibleIssues.length ? Math.round(count / visibleIssues.length * 100) : 0}%)</b>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : <p className="issue-empty-chart">Belum ada data untuk ditampilkan.</p>}
                    </article>
                </section>

                <section className="issue-panel issue-list-panel">
                    <div className="issue-list-heading">
                        <div><h2>Daftar Issue</h2><p>Data hanya-baca dari Google Sheets</p></div>
                    </div>
                    <div className="issue-filters">
                        <label className="issue-date-range">
                            <span className="sr-only">Tanggal mulai</span>
                            <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
                            <span aria-hidden="true">–</span>
                            <span className="sr-only">Tanggal akhir</span>
                            <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
                        </label>
                        <select aria-label="Filter customer" value={customerFilter} onChange={(event) => setCustomerFilter(event.target.value)}>
                            <option value="">Semua Customer</option>
                            {customers.map((customer) => <option key={customer} value={customer}>{customer}</option>)}
                        </select>
                        <select aria-label="Filter status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                            <option value="">Semua Status</option>
                            {Object.keys(statusCounts).sort().map((status) => <option key={status} value={status}>{status}</option>)}
                        </select>
                        <select aria-label="Filter jenis issue" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
                            <option value="">Semua Jenis Issue</option>
                            {types.map((type) => <option key={type} value={type}>{type}</option>)}
                        </select>
                        <input
                            className="issue-search"
                            type="search"
                            placeholder="Cari customer atau issue..."
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                        />
                    </div>
                    <div className="issue-table-wrap">
                        <table className="issue-table">
                            <thead>
                                <tr>
                                    <th>No</th>
                                    <th>Tanggal</th>
                                    <th>Customer</th>
                                    <th>Issue / Root Cause</th>
                                    <th>Jenis</th>
                                    <th>Status</th>
                                    <th>Customer PIC</th>
                                    <th>Aksi</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading && !issues.length ? (
                                    <tr><td className="issue-table-message" colSpan="8">Memuat data dari Google Sheets...</td></tr>
                                ) : pageIssues.length ? pageIssues.map((issue, index) => (
                                    <tr key={issue.id} className={selectedIssue?.id === issue.id ? 'selected' : ''}>
                                        <td>{firstItem + index}</td>
                                        <td>{formatDate(issue.date)}</td>
                                        <td className="issue-customer-cell">{issue.customer}</td>
                                        <td className="issue-root-cell" title={issue.rootCause}>{issue.rootCause || '—'}</td>
                                        <td>{issue.type || '—'}</td>
                                        <td><span className={`issue-status-badge ${statusClass(issue.status)}`}>{issue.status}</span></td>
                                        <td>{issue.customerPic || '—'}</td>
                                        <td>
                                            <button
                                                className="issue-view-button"
                                                type="button"
                                                aria-label={`Lihat detail issue ${issue.customer}`}
                                                onClick={() => setSelectedId(issue.id)}
                                            >◉</button>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr><td className="issue-table-message" colSpan="8">{error ? 'Data tidak dapat dimuat.' : 'Tidak ada issue yang sesuai filter.'}</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                    <footer className="issue-pagination">
                        <span>Menampilkan {firstItem}–{lastItem} dari {visibleIssues.length} data</span>
                        <div>
                            <button type="button" aria-label="Halaman sebelumnya" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>‹</button>
                            <span>{page} / {pageCount}</span>
                            <button type="button" aria-label="Halaman berikutnya" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)}>›</button>
                        </div>
                    </footer>
                </section>
            </div>

            <aside className="issue-detail-panel" aria-label="Detail issue">
                {selectedIssue ? (
                    <>
                        <div className="issue-detail-heading">
                            <h2>Detail Issue</h2>
                            <span className={`issue-status-badge ${statusClass(selectedIssue.status)}`}>{selectedIssue.status}</span>
                        </div>
                        <h3>{selectedIssue.type || 'Issue Customer'}</h3>
                        <div className="issue-detail-fields">
                            <DetailField label="Customer">{selectedIssue.customer}</DetailField>
                            <DetailField label="Customer PIC">{selectedIssue.customerPic}</DetailField>
                            <DetailField label="Tanggal Issue">{formatDate(selectedIssue.date)}</DetailField>
                            <DetailField label="Target Date">{selectedIssue.targetDate}</DetailField>
                            <DetailField label="Root Cause">{selectedIssue.rootCause}</DetailField>
                            <DetailField label="Dampak Issue">{selectedIssue.impact}</DetailField>
                            <DetailField label="Tindakan Segera">{selectedIssue.immediateAction}</DetailField>
                            <DetailField label="Update Terakhir">{selectedIssue.latestUpdate}</DetailField>
                            <DetailField label="Tindakan Corrective">{selectedIssue.correctiveAction}</DetailField>
                            <DetailField label="File Pendukung">
                                {issueLinks(selectedIssue.supportingFiles).length ? (
                                    <div className="issue-evidence-links">
                                        {issueLinks(selectedIssue.supportingFiles).map((url, index) => (
                                            <a href={url} key={`${url}-${index}`} target="_blank" rel="noreferrer">Buka file {index + 1}</a>
                                        ))}
                                    </div>
                                ) : selectedIssue.supportingFiles || '—'}
                            </DetailField>
                        </div>
                        <div className="issue-readonly-note">
                            <SectionIcon name="calendar" />
                            Data dikelola di spreadsheet. Perubahan di halaman ini dinonaktifkan.
                        </div>
                    </>
                ) : (
                    <div className="issue-detail-empty">
                        <SectionIcon name="customer" />
                        <h2>Detail Issue</h2>
                        <p>Pilih issue pada tabel untuk melihat detailnya.</p>
                    </div>
                )}
            </aside>
        </div>
    );
}
