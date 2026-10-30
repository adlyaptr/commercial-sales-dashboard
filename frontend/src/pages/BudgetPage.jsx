import { useCallback, useEffect, useMemo, useState } from 'react';
import { Bar, Line } from 'react-chartjs-2';
import {
    BarElement,
    CategoryScale,
    Chart as ChartJS,
    Filler,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
} from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

ChartJS.register(
    BarElement,
    CategoryScale,
    Filler,
    Legend,
    LinearScale,
    LineElement,
    PointElement,
    Tooltip,
);

const refreshInterval = 5 * 60 * 1000;
const currency = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 });
const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];

function formatCurrency(value) {
    return `Rp ${currency.format(Number(value) || 0)}`;
}

function formatCompactCurrency(value) {
    const millions = Number(value) / 1_000_000;
    return `${millions.toLocaleString('id-ID', { maximumFractionDigits: 1 })} jt`;
}

function formatPercent(value) {
    return `${Number(value || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 })}%`;
}

function wrapChartLabel(label, maxLength = 18) {
    const lines = [];
    let line = '';
    for (const word of label.split(' ')) {
        const nextLine = line ? `${line} ${word}` : word;
        if (line && nextLine.length > maxLength) {
            lines.push(line);
            line = word;
        } else {
            line = nextLine;
        }
    }
    if (line) lines.push(line);
    return lines;
}

function MetricCard({ icon, label, value, note, tone }) {
    return (
        <article className={`budget-metric ${tone}`}>
            <span className="budget-metric-icon" aria-hidden="true">{icon}</span>
            <div className="budget-metric-content">
                <small>{label}</small>
                <strong>{value}</strong>
                <span>{note}</span>
            </div>
        </article>
    );
}

function BudgetChart({ title, children, className = '' }) {
    return (
        <article className={`budget-panel budget-chart-panel ${className}`}>
            <h2>{title}</h2>
            <div className="budget-chart">{children}</div>
        </article>
    );
}

export default function BudgetPage() {
    const { selectedDate } = useOutletContext();
    const [budget, setBudget] = useState(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const [search, setSearch] = useState('');
    const [categoryFilter, setCategoryFilter] = useState('');

    const loadBudget = useCallback(async (forceRefresh = false) => {
        setRefreshing(true);
        try {
            const result = await api(
                `/api/budget${forceRefresh ? '?refresh=true' : ''}`,
                { signal: AbortSignal.timeout(40000) },
            );
            if (!result || !Array.isArray(result.months) || !Array.isArray(result.records)) {
                throw new Error('Format data Budget dari Google Sheets tidak valid.');
            }
            setBudget(result);
            setError('');
        } catch (loadError) {
            setError(loadError.message || 'Data Budget gagal dimuat dari Google Sheets.');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    useEffect(() => {
        loadBudget(true);
        const timer = window.setInterval(() => loadBudget(false), refreshInterval);
        return () => window.clearInterval(timer);
    }, [loadBudget]);

    const periodMonth = selectedDate?.slice(0, 7) ?? '';
    const selectedMonth = periodMonth;
    const monthRecords = useMemo(
        () => (budget?.records ?? []).filter((row) => row.month === selectedMonth),
        [budget, selectedMonth],
    );
    const categories = useMemo(
        () => [...new Set((budget?.records ?? []).map((row) => row.category))],
        [budget],
    );
    const totals = useMemo(() => monthRecords.reduce((summary, row) => ({
        target: summary.target + Number(row.target || 0),
        actual: summary.actual + Number(row.actual || 0),
    }), { target: 0, actual: 0 }), [monthRecords]);
    const monthlyTrend = useMemo(() => (budget?.months ?? []).map((month) => ({
        ...month,
        actual: Number(month.actual || 0),
    })).filter((month) => month.value <= selectedMonth), [budget, selectedMonth]);
    const visibleRows = useMemo(() => monthRecords.filter((row) => {
        const matchesSearch = row.category.toLocaleLowerCase('id-ID')
            .includes(search.trim().toLocaleLowerCase('id-ID'));
        return matchesSearch && (!categoryFilter || row.category === categoryFilter);
    }), [monthRecords, search, categoryFilter]);
    const selectedMonthLabel = budget?.months.find((month) => month.value === selectedMonth)?.label ?? '';
    const realizationPercent = totals.target ? totals.actual / totals.target * 100 : 0;
    const remaining = totals.target - totals.actual;

    const categoryChartData = {
        labels: monthRecords.map((row) => row.category),
        datasets: [
            {
                type: 'bar',
                label: 'Target',
                data: monthRecords.map((row) => row.target),
                backgroundColor: 'rgba(242, 199, 67, 0.78)',
                borderRadius: 3,
                maxBarThickness: 42,
                order: 2,
            },
            {
                type: 'line',
                label: 'Aktual',
                data: monthRecords.map((row) => row.actual),
                borderColor: '#f04438',
                backgroundColor: '#f04438',
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                pointBackgroundColor: '#f04438',
                tension: 0.2,
                order: 1,
            },
        ],
    };
    const monthlyChartData = {
        labels: monthlyTrend.map((month) => monthLabels[Number(month.value.slice(5, 7)) - 1]),
        datasets: [{
            label: 'Realisasi',
            data: monthlyTrend.map((month) => month.actual),
            borderColor: '#15986a',
            backgroundColor: 'rgba(21, 152, 106, 0.14)',
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: '#15986a',
        }],
    };
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top', align: 'end', labels: { usePointStyle: true, boxWidth: 7, font: { size: 10 } } },
            tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatCurrency(context.raw)}` } },
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: { callback: (value) => formatCompactCurrency(value), font: { size: 9 } },
                grid: { color: '#edf2ef' },
            },
            x: {
                ticks: { maxRotation: 0, font: { size: 9 } },
                grid: { display: false },
            },
        },
    };
    const categoryChartOptions = {
        ...chartOptions,
        scales: {
            ...chartOptions.scales,
            x: {
                ...chartOptions.scales.x,
                ticks: {
                    ...chartOptions.scales.x.ticks,
                    autoSkip: false,
                    callback: (_value, index) => wrapChartLabel(categoryChartData.labels[index]),
                },
            },
        },
    };

    return (
        <main className="budget-page">
            <header className="budget-header">
                <div className="budget-title">
                    <span className="budget-title-icon" aria-hidden="true">▣</span>
                    <div>
                        <h1>Budget Monitoring</h1>
                        <p>Pemantauan anggaran dan realisasi keuangan</p>
                    </div>
                </div>
                <div className="budget-toolbar">
                    <button className="budget-sync-button" type="button" onClick={() => loadBudget(true)} disabled={refreshing}>
                        <span aria-hidden="true">⟳</span>{refreshing ? 'Menyinkronkan...' : 'Sinkronkan Google Sheets'}
                    </button>
                    <small className="budget-sync-time">
                        {budget?.syncedAt ? `Terakhir sinkron: ${new Date(budget.syncedAt).toLocaleString('id-ID')}` : 'Belum tersinkron'}
                    </small>
                </div>
            </header>

            {error && <div className="budget-alert" role="alert">{error}<button type="button" onClick={() => loadBudget(true)}>Coba lagi</button></div>}

            {loading && !budget ? (
                <div className="budget-loading" role="status">Memuat data Budget dari Google Sheets...</div>
            ) : budget && (
                <>
                    <section className="budget-metrics" aria-label="Ringkasan budget">
                        <MetricCard icon="▤" label="Total Budget" value={formatCurrency(totals.target)} note={`Target untuk ${selectedMonthLabel}`} tone="target" />
                        <MetricCard icon="◴" label="Total Realisasi" value={formatCurrency(totals.actual)} note={`${formatPercent(realizationPercent)} dari total budget`} tone="actual" />
                        <MetricCard icon="▣" label="Sisa Budget" value={formatCurrency(remaining)} note={remaining < 0 ? 'Melebihi anggaran' : 'Sisa anggaran periode ini'} tone="remaining" />
                        <MetricCard icon="%" label="Persentase Realisasi" value={formatPercent(realizationPercent)} note="dari total budget" tone="percentage" />
                    </section>

                    <section className="budget-charts">
                        <BudgetChart title="Target vs Aktual per Kategori">
                            {monthRecords.length
                                ? <Bar data={categoryChartData} options={categoryChartOptions} />
                                : <p className="budget-empty">Belum ada data untuk periode ini.</p>}
                        </BudgetChart>
                        <BudgetChart title="Realisasi Budget per Bulan">
                            <Line data={monthlyChartData} options={{ ...chartOptions, plugins: { ...chartOptions.plugins, legend: { display: false } } }} />
                        </BudgetChart>
                    </section>

                    <section className="budget-panel budget-detail-panel">
                        <div className="budget-detail-heading">
                            <h2>Rincian Budget - {selectedMonthLabel}</h2>
                            <div className="budget-filters">
                                <input type="search" aria-label="Cari kategori budget" placeholder="Cari kategori..." value={search} onChange={(event) => setSearch(event.target.value)} />
                                <select aria-label="Filter kategori budget" value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
                                    <option value="">Semua Kategori</option>
                                    {categories.map((category) => <option key={category} value={category}>{category}</option>)}
                                </select>
                            </div>
                        </div>
                        <div className="budget-table-wrap">
                            <table className="budget-table">
                                <thead><tr><th>No</th><th>Kategori</th><th>Target (Rp)</th><th>Realisasi (Rp)</th><th>Sisa (Rp)</th><th>Persentase</th><th>Status</th></tr></thead>
                                <tbody>
                                    {visibleRows.length ? visibleRows.map((row, index) => {
                                        const balance = Number(row.target) - Number(row.actual);
                                        const percentage = row.target ? Number(row.actual) / Number(row.target) * 100 : 0;
                                        const overBudget = balance < 0;
                                        return (
                                            <tr key={row.category}>
                                                <td>{index + 1}</td>
                                                <td>{row.category}</td>
                                                <td>{formatCurrency(row.target)}</td>
                                                <td>{formatCurrency(row.actual)}</td>
                                                <td className={overBudget ? 'budget-over' : ''}>{formatCurrency(balance)}</td>
                                                <td>{formatPercent(percentage)}</td>
                                                <td><span className={`budget-status ${overBudget ? 'over' : 'track'}`}>{overBudget ? 'Over Budget' : 'On Track'}</span></td>
                                            </tr>
                                        );
                                    }) : <tr><td className="budget-empty" colSpan="7">Tidak ada kategori yang sesuai.</td></tr>}
                                </tbody>
                                <tfoot><tr>
                                    <th colSpan="2">Total</th>
                                    <td>{formatCurrency(totals.target)}</td>
                                    <td>{formatCurrency(totals.actual)}</td>
                                    <td className={remaining < 0 ? 'budget-over' : ''}>{formatCurrency(remaining)}</td>
                                    <td>{formatPercent(realizationPercent)}</td>
                                    <td>{remaining < 0 ? 'Over Budget' : '—'}</td>
                                </tr></tfoot>
                            </table>
                        </div>
                        <footer className="budget-table-footer">Menampilkan {visibleRows.length} dari {monthRecords.length} kategori</footer>
                    </section>
                </>
            )}
        </main>
    );
}
