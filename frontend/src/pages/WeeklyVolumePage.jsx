import { useEffect, useState } from 'react';
import { Bar, Line } from 'react-chartjs-2';
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip } from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip, Legend);

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT'];
const formatNumber = (value) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(Number(value ?? 0));
const compactNumber = (value) => new Intl.NumberFormat('id-ID', { notation: 'compact', maximumFractionDigits: 1 }).format(value);

const valueLabelsPlugin = {
    id: 'weeklyVolumeValueLabels',
    afterDatasetsDraw(chart) {
        const { ctx } = chart;
        ctx.save();
        ctx.font = '9px "Segoe UI", Arial, sans-serif';
        ctx.fillStyle = '#354b40';
        ctx.textAlign = 'center';

        chart.data.datasets.forEach((dataset, datasetIndex) => {
            const metadata = chart.getDatasetMeta(datasetIndex);
            metadata.data.forEach((element, index) => {
                const value = Number(dataset.data[index] ?? 0);
                if (!Number.isFinite(value) || value === 0) return;
                const { x, y } = element.tooltipPosition();
                if (metadata.type === 'line') {
                    const chartArea = chart.chartArea;
                    const labelBelow = datasetIndex === 1 && y < chartArea.bottom - 22;
                    ctx.textBaseline = labelBelow ? 'top' : 'bottom';
                    const labelY = labelBelow ? y + 9 : y - 9;
                    ctx.fillText(compactNumber(value), x, labelY);
                    return;
                }
                ctx.textBaseline = 'bottom';
                ctx.fillText(formatNumber(value), x, y - 4);
            });
        });

        ctx.restore();
    },
};

function formatDate(dateString, options = { day: '2-digit', month: 'short' }) {
    if (!dateString) return '—';
    return new Date(`${dateString}T00:00:00`).toLocaleDateString('id-ID', options);
}

function sumOperatorWeeks(weeks, operator, key) {
    return weeks.reduce((sum, week) => sum + Number(week.operators?.[operator]?.[key] ?? 0), 0);
}

export default function WeeklyVolumePage() {
    const { rangeStartDate, rangeEndDate } = useOutletContext();
    const [selectedOperator, setSelectedOperator] = useState('ALL');
    const [report, setReport] = useState({ weeks: [], totals: { so: 0, target: 0, actual: 0, diff: 0, achievement: 0 } });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!rangeStartDate || !rangeEndDate) return undefined;
        let active = true;
        setLoading(true);
        setError('');
        const query = new URLSearchParams();
        query.set('start_date', rangeStartDate);
        query.set('end_date', rangeEndDate);
        if (selectedOperator !== 'ALL') query.set('operator', selectedOperator);
        api(`/api/weekly-volume?${query.toString()}`)
            .then((result) => active && setReport(result))
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, [rangeStartDate, rangeEndDate, selectedOperator]);

    const weeks = report.weeks ?? [];
    const detailWeeks = report.detail_weeks ?? weeks;
    const totals = report.totals ?? { so: 0, target: 0, actual: 0, diff: 0, achievement: 0 };
    const operatorTotals = operators.map((operator) => ({
        operator,
        so: sumOperatorWeeks(weeks, operator, 'so'),
        actual: sumOperatorWeeks(weeks, operator, 'actual'),
    }));
    const comparisonData = {
        labels: operatorTotals.map((item) => item.operator),
        datasets: [
            { label: 'SO', data: operatorTotals.map((item) => item.so), backgroundColor: '#1777d1', borderRadius: 3, maxBarThickness: 32 },
            { label: 'Actual', data: operatorTotals.map((item) => item.actual), backgroundColor: '#f0a43a', borderRadius: 3, maxBarThickness: 32 },
        ],
    };
    const totalComparisonData = {
        labels: ['TOTAL'],
        datasets: [
            { label: 'Target', data: [totals.target], backgroundColor: '#18a979', borderRadius: 3, maxBarThickness: 55 },
            { label: 'SO', data: [totals.so], backgroundColor: '#1777d1', borderRadius: 3, maxBarThickness: 55 },
            { label: 'Actual', data: [totals.actual], backgroundColor: '#e64b59', borderRadius: 3, maxBarThickness: 65 },
        ],
    };
    const trendData = {
        labels: detailWeeks.map((week) => [
            week.label,
            `${formatDate(week.start_date)} - ${formatDate(week.end_date)}`,
        ]),
        datasets: [
            { label: 'SO', data: detailWeeks.map((week) => week.so), borderColor: '#1777d1', backgroundColor: '#1777d1', borderWidth: 2, tension: 0.2, pointRadius: 4, pointHoverRadius: 6 },
            { label: 'Actual', data: detailWeeks.map((week) => week.actual), borderColor: '#e64b59', backgroundColor: '#e64b59', borderWidth: 2, tension: 0.2, pointRadius: 4, pointHoverRadius: 6 },
        ],
    };
    const volumeOptions = {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 18 } },
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: { position: 'top', align: 'end', labels: { boxWidth: 9, boxHeight: 9, font: { size: 10 }, usePointStyle: true, pointStyle: 'rect' } },
            tooltip: {
                callbacks: {
                    label: (context) => `${context.dataset.label}: ${formatNumber(context.raw)}`,
                },
            },
        },
        scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 0, autoSkip: false } },
            y: { beginAtZero: true, grid: { color: '#e9f0f6' }, ticks: { display: false } },
        },
    };
    const trendOptions = {
        ...volumeOptions,
        layout: { padding: { top: 18, right: 18, bottom: 8, left: 8 } },
        plugins: {
            ...volumeOptions.plugins,
            tooltip: {
                ...volumeOptions.plugins.tooltip,
                callbacks: {
                    ...volumeOptions.plugins.tooltip.callbacks,
                    title: (items) => {
                        const week = detailWeeks[items[0]?.dataIndex];
                        return week
                            ? `${week.label}: ${formatDate(week.start_date)} - ${formatDate(week.end_date)}`
                            : '';
                    },
                },
            },
        },
        scales: {
            ...volumeOptions.scales,
            x: {
                ...volumeOptions.scales.x,
                ticks: {
                    ...volumeOptions.scales.x.ticks,
                    autoSkip: true,
                    maxTicksLimit: 12,
                    padding: 8,
                },
            },
        },
    };
    return (
        <div className="weekly-volume-page">
            {error && <div className="notice bad" role="alert">{error}</div>}

            <div className="weekly-overview-row">
                <section className="weekly-filter-panel">
                    <div className="weekly-field weekly-operator-field"><span>Pilih MS</span><div className="weekly-operator-options" role="group" aria-label="Pilih MS">
                        <button className={selectedOperator === 'ALL' ? 'selected' : ''} type="button" onClick={() => setSelectedOperator('ALL')}>Semua MS</button>
                        {operators.map((operator) => <button key={operator} className={selectedOperator === operator ? 'selected' : ''} type="button" onClick={() => setSelectedOperator(operator)}>{operator}</button>)}
                    </div></div>
                </section>
            </div>

            <section className="weekly-chart-grid">
                <article className="weekly-chart-panel">
                    <div className="weekly-section-heading"><div><b>PERBANDINGAN VOLUME PER MS</b><small>SO dan actual untuk periode terpilih (Sm³).</small></div></div>
                    <div className="weekly-chart-area">{loading ? <div className="weekly-chart-message">Memuat data...</div> : <Bar data={comparisonData} options={volumeOptions} plugins={[valueLabelsPlugin]} />}</div>
                </article>
                <article className="weekly-chart-panel">
                    <div className="weekly-section-heading"><div><b>TOTAL VOLUME PERIODE</b><small>Target SO dibandingkan actual.</small></div></div>
                    <div className="weekly-chart-area">{loading ? <div className="weekly-chart-message">Memuat data...</div> : <Bar data={totalComparisonData} options={volumeOptions} plugins={[valueLabelsPlugin]} />}</div>
                </article>
            </section>

            <section className="weekly-chart-panel weekly-trend-panel">
                <div className="weekly-section-heading"><div><b>TREND VOLUME MINGGUAN</b><small>SO dan actual per minggu (Sm³).</small></div></div>
                {loading
                    ? <div className="weekly-trend-area"><div className="weekly-chart-message">Memuat data...</div></div>
                    : detailWeeks.length > 0
                        ? <div className="weekly-trend-area">
                            <Line data={trendData} options={trendOptions} plugins={[valueLabelsPlugin]} />
                        </div>
                        : <div className="weekly-trend-area"><div className="weekly-chart-message">Belum ada data pada periode ini.</div></div>}
            </section>

            <section className="weekly-table-panel">
                <div className="weekly-section-heading"><div><b>DETAIL REKAP MINGGUAN</b><small>Ringkasan berdasarkan minggu dan MS yang dipilih.</small></div></div>
                <div className="weekly-table-wrap"><table className="weekly-table">
                    <thead><tr><th>Minggu</th><th>Periode</th><th>SO</th><th>Actual</th><th>Diff</th><th>Pencapaian</th></tr></thead>
                    <tbody>{detailWeeks.length === 0 ? <tr><td colSpan="6" className="empty-row">Belum ada data pada periode ini</td></tr> : detailWeeks.map((week) => <tr key={week.start_date}>
                        <td>{week.label}</td><td>{formatDate(week.start_date)} - {formatDate(week.end_date)}</td><td>{formatNumber(week.so)}</td><td>{formatNumber(week.actual)}</td><td className={week.diff < 0 ? 'diff-neg' : 'diff-pos'}>{formatNumber(week.diff)}</td><td>{Number(week.achievement ?? 0).toLocaleString('id-ID', { maximumFractionDigits: 2 })}%</td>
                    </tr>)}</tbody>
                </table></div>
            </section>
        </div>
    );
}  
