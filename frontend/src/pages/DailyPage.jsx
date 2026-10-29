import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';
import OperatorTables from '../components/OperatorTables';

function parseIndonesianNumber(value) {
    const normalized = value.trim().replace(/\s/g, '');
    if (!normalized) return null;

    const hasComma = normalized.includes(',');
    const isGroupedInteger = /^\d{1,3}(?:\.\d{3})+$/.test(normalized);
    const canonical = hasComma
        ? normalized.replace(/\./g, '').replace(',', '.')
        : isGroupedInteger
            ? normalized.replace(/\./g, '')
            : normalized;
    if (!/^\d+(?:\.\d+)?$/.test(canonical)) return null;

    const parsed = Number(canonical);
    return Number.isFinite(parsed) ? parsed : null;
}

export default function DailyPage() {
    const { dashboard, selectedDate, rangeStartDate, rangeEndDate, refreshDashboard, canEdit } = useOutletContext();
    const [file, setFile] = useState(null);
    const [fileInputKey, setFileInputKey] = useState(0);
    const [notice, setNotice] = useState(null);
    const [busy, setBusy] = useState(false);
    const [previewBusy, setPreviewBusy] = useState(false);
    const [fobSaving, setFobSaving] = useState(false);
    const [editingFob, setEditingFob] = useState(null);
    const [customerMappings, setCustomerMappings] = useState([]);
    const [fobForm, setFobForm] = useState({ date: selectedDate ?? '', customer: '', operator: 'SETU', so: '', actual: '' });
    const [monthlySummary, setMonthlySummary] = useState(null);
    const [summaryError, setSummaryError] = useState('');
    const [summaryLoading, setSummaryLoading] = useState(false);
    const [periodRows, setPeriodRows] = useState([]);
    const [periodError, setPeriodError] = useState('');
    const [periodLoading, setPeriodLoading] = useState(false);
    const isDateRange = Boolean(rangeStartDate && rangeEndDate && rangeStartDate !== rangeEndDate);
    const unmappedCount = customerMappings.filter((item) => !item.operator).length;
    const autoMappedCount = customerMappings.filter((item) => !item.requiresMapping).length;
    const manualMappedCount = customerMappings.filter((item) => item.requiresMapping && item.operator).length;
    const parsedSo = parseIndonesianNumber(fobForm.so);
    const parsedActual = parseIndonesianNumber(fobForm.actual);
    const fobDiff = (parsedActual ?? 0) - (parsedSo ?? 0);
    const formatFobNumber = (value) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(value);

    useEffect(() => {
        if (selectedDate) {
            setFobForm((current) => ({ ...current, date: selectedDate }));
        }
    }, [selectedDate]);

    useEffect(() => {
        const reportDate = dashboard?.report_date;
        if (!reportDate) {
            setMonthlySummary(null);
            setSummaryError('');
            setSummaryLoading(false);
            return undefined;
        }

        let active = true;
        setSummaryLoading(true);
        setSummaryError('');
        setMonthlySummary(null);

        api(`/api/home-summary?month=${encodeURIComponent(reportDate.slice(0, 7))}`)
            .then((summary) => {
                if (active) setMonthlySummary(summary.month_summary);
            })
            .catch((error) => {
                if (active) setSummaryError(error.message || 'Ringkasan bulanan gagal dimuat.');
            })
            .finally(() => {
                if (active) setSummaryLoading(false);
            });

        return () => { active = false; };
    }, [dashboard]);

    useEffect(() => {
        if (!isDateRange) {
            setPeriodRows([]);
            setPeriodError('');
            setPeriodLoading(false);
            return undefined;
        }

        let active = true;
        setPeriodLoading(true);
        setPeriodError('');

        const query = new URLSearchParams({
            start_date: rangeStartDate,
            end_date: rangeEndDate,
        });
        api(`/api/monthly-range?${query.toString()}`)
            .then((result) => {
                if (active) setPeriodRows(result.items || []);
            })
            .catch((error) => {
                if (active) setPeriodError(error.message || 'Data periode gagal dimuat.');
            })
            .finally(() => {
                if (active) setPeriodLoading(false);
            });

        return () => { active = false; };
    }, [isDateRange, rangeStartDate, rangeEndDate]);

    const periodDashboard = useMemo(() => {
        if (!isDateRange || periodLoading || periodError) return null;

        const customers = new Map();
        for (const item of periodRows) {
            const key = `${item.operator}:${item.customer_key}`;
            const customer = customers.get(key) ?? {
                customer: item.customer,
                customer_key: item.customer_key,
                operator: item.operator,
                so: 0,
                actual: 0,
                manual_fob: String(item.customer_key).startsWith('manualfob-'),
            };
            customer.so += Number(item.so) || 0;
            customer.actual += Number(item.actual) || 0;
            customers.set(key, customer);
        }

        const operators = { SETU: [], KHT: [], BLORA: [], WUNUT: [], OFF: [] };
        let totalSo = 0;
        let totalActual = 0;
        for (const customer of customers.values()) {
            customer.diff = customer.actual - customer.so;
            totalSo += customer.so;
            totalActual += customer.actual;
            operators[customer.operator]?.push(customer);
        }

        return {
            operators,
            total_so: totalSo,
            total_actual: totalActual,
            diff: totalActual - totalSo,
        };
    }, [isDateRange, periodRows, periodLoading, periodError]);

    async function selectFile(selectedFile) {
        setFile(selectedFile);
        setCustomerMappings([]);
        setNotice(null);
        if (!selectedFile) return;

        setPreviewBusy(true);
        const body = new FormData();
        body.append('file', selectedFile);
        try {
            const preview = await api('/api/import/preview', { method: 'POST', body });
            setCustomerMappings(preview.customers.map((item) => ({
                ...item,
                requiresMapping: !item.operator,
            })));
        } catch (error) {
            setNotice({ bad: true, text: error.message });
        } finally {
            setPreviewBusy(false);
        }
    }

    async function importFile() {
        if (!file) {
            setNotice({ bad: true, text: 'Pilih file Excel terlebih dahulu.' });
            return;
        }
        if (previewBusy) {
            setNotice({ bad: true, text: 'Tunggu sampai pemeriksaan file selesai.' });
            return;
        }
        if (unmappedCount > 0) {
            setNotice({ bad: true, text: `Impor dibatalkan. Operator belum ditemukan otomatis untuk ${unmappedCount} customer. Periksa daftar customer yang belum terpetakan.` });
            return;
        }

        setBusy(true);
        setNotice(null);

        try {
            const newMappings = customerMappings
                .filter((item) => item.requiresMapping)
                .map(({ customer, operator }) => ({ customer, operator }));
            if (newMappings.length > 0) {
                await api('/api/customer-mapping/bulk', {
                    method: 'POST',
                    body: { mappings: newMappings },
                });
            }
            const body = new FormData();
            body.append('file', file);
            const result = await api('/api/import', { method: 'POST', body });
            setNotice({ bad: false, text: `${result.message} Baris terbaca: ${result.rows_read}; baris disimpan/diperbarui: ${result.rows_saved}.` });
            setFile(null);
            setCustomerMappings([]);
            setFileInputKey((key) => key + 1);
            await refreshDashboard();
        } catch (error) {
            setNotice({ bad: true, text: error.message });
        } finally {
            setBusy(false);
        }
    }

    async function saveManualFob(event) {
        event.preventDefault();
        if (!fobForm.date) {
            setNotice({ bad: true, text: 'Pilih tanggal laporan untuk data FOB.' });
            return;
        }
        if (parsedSo == null || parsedActual == null) {
            setNotice({ bad: true, text: 'SO dan Actual harus berupa angka valid. Gunakan titik untuk ribuan dan koma untuk desimal, contoh: 15.000 atau 1.234,56.' });
            return;
        }
        if (parsedSo < 0 || parsedActual < 0) {
            setNotice({ bad: true, text: 'SO dan Actual tidak boleh bernilai negatif.' });
            return;
        }

        setFobSaving(true);
        setNotice(null);
        try {
            await api(editingFob ? `/api/manual-fob-sales/${editingFob.id}` : '/api/manual-fob-sales', {
                method: editingFob ? 'PUT' : 'POST',
                body: {
                    date: fobForm.date,
                    customer: fobForm.customer,
                    operator: fobForm.operator,
                    so: parsedSo,
                    actual: parsedActual,
                },
            });
            const savedDate = fobForm.date;
            setNotice({ bad: false, text: `Data customer FOB berhasil ${editingFob ? 'diperbarui' : 'disimpan'} untuk ${savedDate}.` });
            setEditingFob(null);
            setFobForm((current) => ({ ...current, customer: '', so: '', actual: '' }));
            try {
                await refreshDashboard(savedDate);
            } catch (error) {
                setNotice({ bad: true, text: `Data FOB tersimpan, tetapi dashboard gagal diperbarui: ${error.message}` });
            }
        } catch (error) {
            setNotice({ bad: true, text: error.message });
        } finally {
            setFobSaving(false);
        }
    }

    function editManualFob(row, operator) {
        setEditingFob({ id: row.manual_fob_id });
        setFobForm({
            date: dashboard?.report_date ?? selectedDate ?? '',
            customer: row.customer,
            operator,
            so: String(row.so ?? ''),
            actual: String(row.actual ?? ''),
        });
        document.querySelector('.manual-fob-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    async function deleteManualFob(row) {
        if (!row.manual_fob_id || !window.confirm(`Hapus data FOB "${row.customer}" pada tanggal ${dashboard?.report_date}?`)) {
            return;
        }

        setFobSaving(true);
        setNotice(null);
        try {
            await api(`/api/manual-fob-sales/${row.manual_fob_id}`, { method: 'DELETE' });
            setNotice({ bad: false, text: `Data FOB "${row.customer}" berhasil dihapus.` });
            await refreshDashboard(dashboard?.report_date);
        } catch (error) {
            setNotice({ bad: true, text: error.message });
        } finally {
            setFobSaving(false);
        }
    }

    function cancelFobEdit() {
        setEditingFob(null);
        setFobForm((current) => ({
            date: dashboard?.report_date ?? selectedDate ?? '',
            customer: '',
            operator: 'SETU',
            so: '',
            actual: '',
        }));
    }

    const formatDateRange = (startDate, endDate) =>
        `${startDate?.split('-').reverse().join('/') ?? ''} - ${endDate?.split('-').reverse().join('/') ?? ''}`;
    const displayedDashboard = isDateRange ? periodDashboard : dashboard;

    return (
        <>
            {isDateRange && periodLoading && (
                <div className="notice" role="status">Memuat data periode...</div>
            )}
            {isDateRange && periodError && (
                <div className="notice bad" role="alert">{periodError}</div>
            )}
            <OperatorTables
                data={displayedDashboard?.operators ?? {}}
                dailySummary={displayedDashboard}
                dailySummaryTitle={isDateRange
                    ? `Penyerapan Periode ${formatDateRange(rangeStartDate, rangeEndDate)}`
                    : undefined}
                monthlySummary={monthlySummary}
                summaryMonth={dashboard?.report_date?.slice(0, 7)}
                summaryError={summaryError}
                summaryLoading={summaryLoading}
                onEditManualFob={canEdit && !isDateRange ? editManualFob : undefined}
                onDeleteManualFob={canEdit && !isDateRange ? deleteManualFob : undefined}
            />
            {canEdit && <>
            <form className="manual-fob-panel" onSubmit={saveManualFob}>
                <div className="manual-fob-heading">
                    <b>{editingFob ? 'Edit Customer FOB' : 'Input Manual Customer FOB'}</b>
                    <small>Isi hanya pada tanggal di bulan yang memiliki customer FOB.</small>
                </div>
                <div className="manual-fob-fields">
                    <label><span>Tanggal Laporan</span><input required type="date" value={fobForm.date} onChange={(event) => setFobForm((current) => ({ ...current, date: event.target.value }))} /></label>
                    <label><span>Nama FOB Customer</span><input required maxLength="150" value={fobForm.customer} onChange={(event) => setFobForm((current) => ({ ...current, customer: event.target.value }))} /></label>
                    <label><span>Pilihan MS</span><select value={fobForm.operator} onChange={(event) => setFobForm((current) => ({ ...current, operator: event.target.value }))}>
                        <option value="SETU">SETU</option><option value="KHT">KHT</option><option value="BLORA">BLORA</option><option value="WUNUT">WUNUT</option>
                    </select></label>
                    <label><span>SO</span><input required type="text" inputMode="decimal" placeholder="Contoh: 15.000" value={fobForm.so} onChange={(event) => setFobForm((current) => ({ ...current, so: event.target.value }))} /></label>
                    <label><span>Actual</span><input required type="text" inputMode="decimal" placeholder="Contoh: 2.065" value={fobForm.actual} onChange={(event) => setFobForm((current) => ({ ...current, actual: event.target.value }))} /></label>
                    <label><span>Diff (Actual − SO)</span><input className={fobDiff < 0 ? 'diff-neg' : 'diff-pos'} readOnly value={formatFobNumber(fobDiff)} /></label>
                    <div className="manual-fob-actions">
                        {editingFob && <button className="secondary" type="button" onClick={cancelFobEdit} disabled={fobSaving}>Batal</button>}
                        <button className="primary" type="submit" disabled={fobSaving}>{fobSaving ? 'Menyimpan...' : editingFob ? 'Simpan Perubahan' : 'Simpan FOB'}</button>
                    </div>
                </div>
            </form>
            <section className="import-panel" id="import-data">
                <label className="dropzone" htmlFor="excelFile">
                    <span className="cloud">☁↑</span><b>Klik untuk memilih file Excel</b><small>Format: .xlsx, .xlsm · Maks. 30 MB</small>
                    <input key={fileInputKey} id="excelFile" type="file" accept=".xlsx,.xlsm" onChange={(event) => selectFile(event.target.files?.[0] ?? null)} />
                </label>
                <div className="file-name">{file?.name ?? 'Belum ada file dipilih'}</div>
                <button className="primary import-btn" type="button" disabled={busy || previewBusy || unmappedCount > 0} onClick={importFile}>{previewBusy ? 'Memeriksa...' : busy ? 'Mengimpor...' : unmappedCount > 0 ? 'Operator Belum Dikenali' : '⟳  IMPOR / UPDATE SALES'}</button>
            </section>
            {customerMappings.length > 0 && <section className="mapping-panel">
                <div className="mapping-panel-heading">
                    <b>Pemetaan Customer</b>
                    <span>{autoMappedCount} otomatis · {manualMappedCount} manual · {unmappedCount} belum dipetakan</span>
                </div>
                {unmappedCount > 0 ? (
                    <>
                        <p className="mapping-complete">Pilih operator atau tandai OFF untuk customer yang tidak aktif. Pemetaan akan disimpan untuk impor berikutnya.</p>
                        <div className="mapping-table-wrap"><table className="mapping-table">
                            <thead><tr><th>Customer Baru</th><th>Operator</th></tr></thead>
                            <tbody>{customerMappings.filter((item) => !item.operator).map((item) => (
                                <tr key={item.customer}>
                                    <td>{item.customer}</td>
                                    <td><select aria-label={`Operator untuk ${item.customer}`} value={item.operator} onChange={(event) => setCustomerMappings((current) => current.map((entry) => entry.customer === item.customer ? { ...entry, operator: event.target.value } : entry))}>
                                        <option value="">Pilih operator</option>
                                        <option value="SETU">SETU</option>
                                        <option value="KHT">KHT</option>
                                        <option value="BLORA">BLORA</option>
                                        <option value="WUNUT">WUNUT</option>
                                        <option value="OFF">OFF (Customer nonaktif)</option>
                                    </select></td>
                                </tr>
                            ))}</tbody>
                        </table></div>
                    </>
                ) : (
                    <p className="mapping-complete">Semua customer sudah memiliki pemetaan. File siap diimpor.</p>
                )}
            </section>}
            </>}
            {notice && <div className={`notice${notice.bad ? ' bad' : ''}`} role="status">{notice.text}</div>}
        </>
    );
}