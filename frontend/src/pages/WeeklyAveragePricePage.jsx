import React, { useEffect, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT'];
const regions = ['JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR'];
const comparisonAreas = [
    { key: 'JAWA BARAT', label: 'Jawa Barat', regions: ['JAWA BARAT'] },
    { key: 'JAWA TENGAH', label: 'Jawa Tengah', regions: ['JAWA TENGAH'] },
    { key: 'JAWA TIMUR', label: 'Jawa Timur', regions: ['JAWA TIMUR'] },
    { key: 'ALL_EXCEPT_JATIM', label: 'All Area (exc. Jatim)', regions: ['JAWA BARAT', 'JAWA TENGAH'] },
];
const formatInteger = (value) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(Number(value ?? 0));
const formatDecimal = (value, digits = 2) => new Intl.NumberFormat('id-ID', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value ?? 0));
const formatDifference = (value) => value < 0
    ? `(${formatInteger(Math.abs(value))})`
    : formatInteger(value);

const comparisonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 9, boxHeight: 9, font: { size: 10 } } },
        tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatInteger(context.raw)} Rp/Sm³` } },
    },
    scales: {
        x: { grid: { display: false }, ticks: { font: { size: 9 } } },
        y: { beginAtZero: true, ticks: { font: { size: 9 }, callback: formatInteger } },
    },
};

function monthLabel(value) {
    if (!value) return 'Pilih bulan';
    const [year, month] = value.split('-').map(Number);
    return new Date(year, month - 1, 1).toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
}

export default function WeeklyAveragePricePage() {
    const { averagePriceMonth, rangeStartDate } = useOutletContext();
    const selectedMonth = averagePriceMonth || rangeStartDate?.slice(0, 7) || '';
    const [report, setReport] = useState({ rows: [], operator_factors: {}, exchange_rate: 0, targets: {}, totals: {} });
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');

    useEffect(() => {
        if (!selectedMonth) return undefined;
        let active = true;
        setLoading(true);
        setError('');
        api(`/api/monthly-average-price?month=${encodeURIComponent(selectedMonth)}`)
            .then((data) => active && setReport(data))
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, [selectedMonth]);

    function updateRow(customerKey, field, value) {
        setReport((current) => ({
            ...current,
            rows: current.rows.map((row) => row.customer_key === customerKey
                ? { ...row, [field]: value }
                : row),
        }));
    }

    function updateFactor(operator, value) {
        setReport((current) => ({
            ...current,
            operator_factors: { ...current.operator_factors, [operator]: value },
        }));
    }

    function updateTarget(area, value) {
        setReport((current) => ({
            ...current,
            targets: { ...current.targets, [area]: value },
        }));
    }

    async function saveReport(event) {
        event.preventDefault();
        if (!selectedMonth) return;
        setSaving(true);
        setError('');
        setNotice('');
        try {
            await api('/api/monthly-average-price', {
                method: 'POST',
                body: {
                    month: selectedMonth,
                    operator_factors: Object.fromEntries(operators.map((operator) => [
                        operator,
                        Number(report.operator_factors[operator] || 0),
                    ])),
                    exchange_rate: Number(report.exchange_rate || 0),
                    targets: Object.fromEntries(comparisonAreas.map(({ key }) => [
                        key,
                        report.targets[key] === '' || report.targets[key] == null
                            ? null
                            : Number(report.targets[key]),
                    ])),
                    entries: report.rows.map((row) => ({
                        customer_key: row.customer_key,
                        region: row.region || '',
                        price_unit: row.price_unit || 'USD_MMBTU',
                        price_usd_per_mmbtu: row.price_unit === 'IDR_SM3'
                            ? 0
                            : Number(row.price_usd_per_mmbtu || 0),
                        price_rp_per_sm3: row.price_unit === 'IDR_SM3'
                            ? Number(row.price_rp_per_sm3 || 0)
                            : 0,
                    })),
                },
            });
            const refreshed = await api(`/api/monthly-average-price?month=${encodeURIComponent(selectedMonth)}`);
            setReport(refreshed);
            setNotice(`Data Average Price ${monthLabel(selectedMonth)} berhasil disimpan.`);
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSaving(false);
        }
    }

    const displayRows = report.rows.map((row) => {
        const sm3 = Number(row.so_sm3 || 0) + Number(row.actual_sm3 || 0);
        const factor = Number(report.operator_factors[row.operator] || 0);
        const volumeMmbtu = factor > 0 ? sm3 / factor : 0;
        const priceUnit = row.price_unit || 'USD_MMBTU';
        const priceUsd = Number(row.price_usd_per_mmbtu || 0);
        const priceRp = Number(row.price_rp_per_sm3 || 0);
        const exchangeRate = Number(report.exchange_rate || 0);
        const totalRp = priceUnit === 'IDR_SM3'
            ? sm3 * priceRp
            : volumeMmbtu * priceUsd * exchangeRate;
        const totalUsd = priceUnit === 'IDR_SM3'
            ? (exchangeRate > 0 ? totalRp / exchangeRate : 0)
            : volumeMmbtu * priceUsd;
        return {
            ...row,
            price_unit: priceUnit,
            sm3,
            volume_mmbtu: volumeMmbtu,
            total_usd: totalUsd,
            rupiah: totalRp,
        };
    });
    const totals = displayRows.reduce((sum, row) => ({
        sm3: sum.sm3 + row.sm3,
        mmbtu: sum.mmbtu + row.volume_mmbtu,
        usd: sum.usd + row.total_usd,
        rupiah: sum.rupiah + row.rupiah,
    }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
    const comparisonRows = comparisonAreas.map((area) => {
        const eligibleRows = displayRows.filter((row) =>
            area.regions.includes(row.region)
            && row.sm3 > 0
            && (row.price_unit === 'IDR_SM3'
                ? Number(row.price_rp_per_sm3) > 0
                : Number(row.sm3_per_mmbtu) > 0
                    && Number(row.price_usd_per_mmbtu) > 0
                    && Number(report.exchange_rate) > 0));
        const volume = eligibleRows.reduce((sum, row) => sum + row.sm3, 0);
        const rupiah = eligibleRows.reduce((sum, row) => sum + row.rupiah, 0);
        const targetValue = report.targets[area.key];
        const target = targetValue == null || targetValue === '' ? null : Number(targetValue);
        const prognosis = volume > 0 ? rupiah / volume : null;
        return {
            ...area,
            target,
            prognosis,
            difference: target != null && prognosis != null ? prognosis - target : null,
        };
    });
    const comparisonChartData = {
        labels: comparisonRows.map((row) => row.label),
        datasets: [
            {
                label: 'Target',
                data: comparisonRows.map((row) => row.target),
                backgroundColor: '#56843d',
                borderRadius: 2,
                maxBarThickness: 28,
            },
            {
                label: 'Prognosa',
                data: comparisonRows.map((row) => row.prognosis),
                backgroundColor: '#a8d184',
                borderRadius: 2,
                maxBarThickness: 28,
            },
        ],
    };

    return (
        <div className="weekly-average-page">
            <section className="average-filter-panel">
                <div className="average-filter-field">
                    <span>Bulan Average Price (mengikuti tanggal awal)</span>
                    <strong>{monthLabel(selectedMonth)}</strong>
                </div>
            </section>

            {error && <div className="notice bad" role="alert">{error}</div>}
            {notice && <div className="notice good" role="status">{notice}</div>}

            <section className="average-kpi-grid">
                <article className="average-kpi average-kpi-blue"><span className="average-kpi-icon">▤</span><div><small>TOTAL SM³</small><strong>{formatInteger(totals.sm3)}</strong><span>SO + Actual</span></div></article>
                <article className="average-kpi average-kpi-green"><span className="average-kpi-icon">◆</span><div><small>TOTAL MMBTU</small><strong>{formatDecimal(totals.mmbtu, 3)}</strong><span>Sm³ ÷ faktor operator</span></div></article>
                <article className="average-kpi average-kpi-red"><span className="average-kpi-icon">$</span><div><small>TOTAL USD</small><strong>{formatDecimal(totals.usd, 2)}</strong><span>Harga per MMBtu</span></div></article>
                <article className="average-kpi average-kpi-achievement"><span className="average-kpi-icon">Rp</span><div><small>TOTAL RUPIAH</small><strong>{formatInteger(totals.rupiah)}</strong><span>Kurs bulan terpilih</span></div></article>
            </section>

            <section className="average-data-panel">
                <div className="average-data-heading">
                    <div className="average-panel-heading">
                        <b>1. Data Average Price Customer</b>
                        <small>{monthLabel(selectedMonth)} · Sm³ = SO + Actual · Gulir tabel untuk semua customer</small>
                    </div>
                </div>
                <form onSubmit={saveReport}>
                    <div className="average-table-wrap average-customer-table-wrap" role="region" aria-label="Tabel data Average Price Customer" tabIndex="0">
                        <table className="average-data-table">
                            <thead><tr><th>No</th><th>Wilayah</th><th>Customer</th><th>Operator</th><th>Sm³ (SO + Actual)</th><th>MMBTU</th><th>Satuan Harga</th><th>Harga</th><th>Total (USD)</th><th>Total (Rp)</th></tr></thead>
                            <tbody>
                                {displayRows.length === 0
                                    ? <tr><td colSpan="10" className="empty-row">{loading ? 'Memuat data...' : 'Belum ada data sales untuk bulan ini.'}</td></tr>
                                    : displayRows.map((row, index) => <tr key={row.customer_key}>
                                        <td>{index + 1}</td>
                                        <td>
                                            <select aria-label={`Wilayah ${row.customer}`} value={row.region || ''} onChange={(event) => updateRow(row.customer_key, 'region', event.target.value)}>
                                                <option value="">Pilih wilayah</option>
                                                {regions.map((region) => <option key={region} value={region}>{region}</option>)}
                                            </select>
                                        </td>
                                        <td>{row.customer}</td>
                                        <td>{row.operator}</td>
                                        <td>{formatInteger(row.sm3)}</td>
                                        <td>{formatDecimal(row.volume_mmbtu, 3)}</td>
                                        <td>
                                            <select
                                                aria-label={`Satuan harga ${row.customer}`}
                                                value={row.price_unit || 'USD_MMBTU'}
                                                onChange={(event) => updateRow(row.customer_key, 'price_unit', event.target.value)}
                                            >
                                                <option value="USD_MMBTU">USD/MMBTU</option>
                                                <option value="IDR_SM3">Rp/Sm³</option>
                                            </select>
                                        </td>
                                        <td>
                                            <input
                                                aria-label={`Harga ${row.price_unit === 'IDR_SM3' ? 'Rupiah per Sm3' : 'USD per MMBtu'} ${row.customer}`}
                                                type="number"
                                                min="0"
                                                step={row.price_unit === 'IDR_SM3' ? '1' : '0.0001'}
                                                value={row.price_unit === 'IDR_SM3'
                                                    ? row.price_rp_per_sm3 || ''
                                                    : row.price_usd_per_mmbtu || ''}
                                                onChange={(event) => updateRow(
                                                    row.customer_key,
                                                    row.price_unit === 'IDR_SM3' ? 'price_rp_per_sm3' : 'price_usd_per_mmbtu',
                                                    event.target.value
                                                )}
                                            />
                                        </td>
                                        <td>{formatDecimal(row.total_usd, 2)}</td>
                                        <td>Rp {formatInteger(row.rupiah)}</td>
                                    </tr>)}
                            </tbody>
                            {displayRows.length > 0 && <tfoot><tr>
                                <th colSpan="4">TOTAL</th>
                                <th>{formatInteger(totals.sm3)}</th>
                                <th>{formatDecimal(totals.mmbtu, 3)}</th>
                                <th colSpan="2">—</th>
                                <th>{formatDecimal(totals.usd, 2)}</th>
                                <th>Rp {formatInteger(totals.rupiah)}</th>
                            </tr></tfoot>}
                        </table>
                    </div>

                    <div className="average-data-heading average-conversion-heading">
                        <div className="average-panel-heading">
                            <b>2. Faktor Konversi Operator dan Kurs</b>
                            <small>Faktor dan kurs berlaku untuk seluruh customer pada {monthLabel(selectedMonth)}.</small>
                        </div>
                        <label className="average-filter-field">
                            <span>Kurs Rp/USD</span>
                            <input aria-label="Kurs Rupiah per USD" type="number" min="0" step="1" value={report.exchange_rate || ''} onChange={(event) => setReport((current) => ({ ...current, exchange_rate: event.target.value }))} />
                        </label>
                    </div>
                    <div className="average-table-wrap">
                        <table className="average-data-table average-conversion-table">
                            <thead><tr><th>No</th><th>Operator</th><th>Faktor Sm³ per MMBTU</th><th>Contoh</th></tr></thead>
                            <tbody>{operators.map((operator, index) => <tr key={operator}>
                                <td>{index + 1}</td>
                                <td>{operator}</td>
                                <td><input aria-label={`Faktor konversi ${operator}`} type="number" min="0" step="0.0001" value={report.operator_factors[operator] || ''} onChange={(event) => updateFactor(operator, event.target.value)} /></td>
                                <td>MMBTU = Sm³ ÷ faktor</td>
                            </tr>)}</tbody>
                        </table>
                    </div>
                    <div className="average-data-note">
                        <span>i</span>
                        Rumus: harga USD/MMBTU → Total USD = MMBTU × harga, lalu Total Rp = Total USD × kurs; harga Rp/Sm³ → Total Rp = Sm³ × harga, lalu ekuivalen USD = Total Rp ÷ kurs.
                    </div>
                    <div className="average-data-heading average-comparison-heading">
                        <div className="average-panel-heading">
                            <b>3. Target Harga dan Prognosa (Rp/Sm³)</b>
                            <small>{monthLabel(selectedMonth)} · Selisih = Prognosa − Target</small>
                        </div>
                    </div>
                    <div className="average-comparison-chart">
                        <Bar data={comparisonChartData} options={comparisonChartOptions} />
                    </div>
                    <div className="average-table-wrap">
                        <table className="average-data-table average-comparison-table">
                            <thead><tr><th>Area</th><th>Target (Rp/Sm³)</th><th>Prognosa (Rp/Sm³)</th><th>Selisih (Rp/Sm³)</th></tr></thead>
                            <tbody>{comparisonRows.map((row) => (
                                <tr key={row.key}>
                                    <td>{row.label}</td>
                                    <td>
                                        <input
                                            aria-label={`Target harga ${row.label}`}
                                            type="number"
                                            min="0"
                                            step="1"
                                            placeholder="Input target"
                                            value={report.targets[row.key] ?? ''}
                                            onChange={(event) => updateTarget(row.key, event.target.value)}
                                        />
                                    </td>
                                    <td>{row.prognosis == null ? '—' : formatInteger(row.prognosis)}</td>
                                    <td className={row.difference == null ? '' : row.difference < 0 ? 'diff-neg' : 'diff-pos'}>
                                        {row.difference == null ? '—' : formatDifference(row.difference)}
                                    </td>
                                </tr>
                            ))}</tbody>
                        </table>
                    </div>
                    <div className="average-data-note">
                        <span>i</span>
                        Prognosa adalah total Rupiah customer pada area dibagi total Sm³ customer yang memiliki harga dan kurs valid. All Area (exc. Jatim) menggabungkan Jawa Barat dan Jawa Tengah.
                    </div>
                    <div className="average-toolbar average-monthly-save">
                        <button className="average-add-button" type="submit" disabled={saving || loading || !selectedMonth}>
                            {saving ? 'Menyimpan...' : 'Simpan Data Bulan Ini'}
                        </button>
                    </div>
                </form>
            </section>
        </div>
    );
}
