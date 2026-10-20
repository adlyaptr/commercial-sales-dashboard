import React, { useEffect, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from 'chart.js';
import { useOutletContext } from 'react-router-dom';
import { api } from '../api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const operators = ['SETU', 'KHT', 'BLORA', 'WUNUT'];
const regions = ['JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR', 'JAWA TENGAH DAN TIMUR'];
const pdfCustomerNames = [
    'PT Cipta Lestari Idea Nusa', 'PT Mitra Kaya Galvanize', 'PT Optima Adhi Jaya',
    'SHB', 'GTL', 'TWK', 'BEM', 'TOMIMOTO', 'NIAGA GARAM', 'PCI MENGGER',
    'Alia Digital', 'BI Surcharge', 'BI', 'STM', 'SMA', 'IP', 'KARISMA', 'KTN',
    'Honchuan', 'NNI', 'GFR Surcharge', 'GF RANCAEKEK', 'BYC', 'HLI Green Power',
    'Dic Grapichs', 'KSN Maja', 'KSN Ranca', 'ATEJA', 'ABC Kogen', 'UMI', 'Ceres',
    'PCI 84 Surcharge', 'PCI 84', 'INDOFOOD NSF', 'Asahimas Surcharge', 'Asahimas',
    'FJI / SBI', 'ALTINEX /Masami', 'Winglok / EBM', 'KGM / RRS', 'CISF / RRS',
    'PUJ - Lubricant', 'Tong Tji / GAS', 'INDONEPTUNE /AAE', 'Calbee/ACE', 'CV PA',
    'GF KULIT', 'RB', 'GF ATOM', 'HSK / GAS', 'Surya Pamenang (Global)',
    'Surya Pamenang (JES)', 'Jiuqi Tecnology Konjac', 'Djarum', 'Green Pulse',
    'Concord Industry', 'Pentawira (KSO REN)',
];
const comparisonAreas = [
    { key: 'JAWA BARAT', label: 'Jawa Barat', regions: ['JAWA BARAT'] },
    { key: 'JAWA TENGAH', label: 'Jawa Tengah', regions: ['JAWA TENGAH'] },
    { key: 'JAWA TIMUR', label: 'Jawa Timur', regions: ['JAWA TIMUR'] },
    { key: 'JAWA_TENGAH_DAN_TIMUR', label: 'Jawa Tengah dan Timur', regions: ['JAWA TENGAH DAN TIMUR'] },
    { key: 'ALL_EXCEPT_JATIM', label: 'All Area', regions: [] },
];
const templateCustomerOrder = [
    'CLIN', 'MKG', 'OPTIMA', 'SHB', 'GTL', 'TWK', 'BEM', 'TOMIMOTO',
    'NIAGA GARAM', 'PCI MENGGER', 'Alia Digital', 'GreenPulse',
    'BI Surcharge', 'BI', 'STM', 'SMA', 'IP', 'KARISMA', 'KTN', 'Honchuan',
    'NNI', 'GFR Surcharge', 'GF RANCAEKEK', 'BYC', 'HLI Green Power',
    'Dic Grapichs', 'KSN Maja', 'ATEJA', 'ABC Kogen', 'KSN Ranca',
    'UMI', 'Ceres', 'PCI 84 Surcharge', 'PCI 84', 'INDOFOOD NSF',
    'Asahimas Surcharge', 'Asahimas', 'Concord',
    'FJI / SBI', 'ALTINEX /Masami', 'Winglok / EBM', 'PSD / WIRA',
    'ABP / SBI', 'KGM / RRS', 'BDP / LEMB', 'Toyobo (KSO Ineko)',
    'Citymall/Wira', 'CISF / RRS', 'PUJ - Lubricant', 'Tong Tji / GAS',
    'Torabika HF', 'Torabika IC', 'SWS / ACE', 'Kimia Farma / IMA',
    'INDONEPTUNE /AAE', 'HSK / GAS', 'Surya Pamenang (Global)',
    'Torabika Cikupa/Ekajaya', 'Calbee/ACE',
    'CV PA', 'GF KULIT', 'RPI', 'RB', 'GF ATOM', 'HSK / GAS',
    'Surya Pamenang (JES)', 'JIUQI', 'Surya Pamenang (Global)',
    'Djarum', 'Surya Pamenang (Global)', 'Pentawira / REN',
];
const customerOrderAliases = {
    adp: 'Alia Digital',
    ami: 'ATEJA',
    altksomasami: 'altinex /masami',
    calbeeksobmi: 'Calbee/ACE',
    cisfksorrs: 'cisf / rrs',
    dic: 'dic grapichs',
    gfranca: 'gf rancaekek',
    gfrsurcharge: 'GFR Surcharge',
    gfatom: 'GF ATOM',
    gfkulit: 'GF KULIT',
    hci: 'Honchuan',
    hli: 'HLI Green Power',
    idpksoaae: 'indoneptune /aae',
    hskksogas: 'hsk / gas',
    indofood: 'INDOFOOD NSF',
    ka: 'KARISMA',
    kgmksorrs: 'KGM / RRS',
    niagagaram: 'NIAGA GARAM',
    pcimengger: 'PCI MENGGER',
    pa: 'CV PA',
    spglobal: 'Surya Pamenang (Global)',
    spksojes: 'Surya Pamenang (JES)',
    greenpulse: 'GreenPulse',
    jiuqi: 'JIUQI',
    djarum: 'Djarum',
    kimiafarmaksoineko: 'Kimia Farma / IMA',
    ksn: 'KSN Maja',
    oaj: 'OPTIMA',
    pentawiraksoren: 'pentawira / ren',
    fjiksosalmah: 'FJI / SBI',
    tongjiksogas: 'Tong Tji / GAS',
    winglokksoebm: 'winglok / ebm',
};
const januaryCustomerAliases = {
    adp: 'Alia Digital',
    calbeeksobmi: 'Calbee/ACE',
    fjiksosalmah: 'FJI / SBI',
    gfatom: 'GF ATOM',
    gfkulit: 'GF KULIT',
    gfranca: 'GF RANCAEKEK',
    gfrsurcharge: 'GFR Surcharge',
    hli: 'HLI Green Power',
    hskksogas: 'HSK / GAS',
    idpksoaae: 'INDONEPTUNE /AAE',
    indofood: 'INDOFOOD NSF',
    ka: 'KARISMA',
    kgmksorrs: 'KGM / RRS',
    niagagaram: 'NIAGA GARAM',
    pcimengger: 'PCI MENGGER',
    pa: 'CV PA',
    spglobal: 'Surya Pamenang (Global)',
    spksojes: 'Surya Pamenang (JES)',
    tongjiksogas: 'Tong Tji / GAS',
};
const normalizeCustomerOrder = (value) => String(value ?? '').toLowerCase().replace(/[^a-z0-9]/g, '');
const customerOrderIndex = new Map();
templateCustomerOrder.forEach((customer, index) => {
    const key = normalizeCustomerOrder(customer);
    if (!customerOrderIndex.has(key)) customerOrderIndex.set(key, index);
});
const workbookCustomerGroups = [
    {
        label: 'Customer <50.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['CLIN', 'MKG', 'OPTIMA', 'SHB', 'GTL', 'TWK', 'BEM', 'TOMIMOTO', 'NIAGA GARAM', 'PCI MENGGER', 'Alia Digital'],
            'JAWA TENGAH': ['CV PA', 'GF KULIT', 'RPI'],
            'JAWA TIMUR': ['Djarum'],
        },
    },
    {
        label: 'Customer 50.001 - 100.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['BI Surcharge', 'BI', 'STM', 'SMA', 'IP', 'KARISMA', 'KTN', 'Honchuan'],
            'JAWA TENGAH': ['RB', 'GF ATOM'],
            'JAWA TIMUR': ['Surya Pamenang (Global)'],
        },
    },
    {
        label: 'Customer 100.001 - 200.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['NNI', 'GFR Surcharge', 'GF RANCAEKEK', 'BYC', 'HLI Green Power', 'Dic Grapichs', 'KSN Maja', 'ATEJA', 'ABC Kogen'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'Customer >200.001 Sm³/bln',
        regions: {
            'JAWA BARAT': ['UMI', 'Ceres', 'PCI 84 Surcharge', 'PCI 84', 'INDOFOOD NSF', 'Asahimas Surcharge', 'Asahimas'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'KSO · Customer <50.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['FJI / SBI', 'ALTINEX /Masami', 'Winglok / EBM', 'PSD / WIRA', 'ABP / SBI', 'KGM / RRS', 'BDP / LEMB', 'Toyobo (KSO Ineko)', 'Citymall/Wira'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'KSO · Customer 50.001 - 100.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['CISF / RRS', 'PUJ - Lubricant', 'Tong Tji / GAS', 'Torabika HF', 'Torabika IC', 'SWS / ACE'],
            'JAWA TENGAH': [],
        },
    },
    {
        label: 'KSO · Customer 100.001 - 200.000 Sm³/bln',
        regions: {
            'JAWA BARAT': ['INDONEPTUNE /AAE', 'HSK / GAS', 'Surya Pamenang (Global)'],
            'JAWA TENGAH': ['HSK / GAS', 'Surya Pamenang (Global)'],
        },
    },
    {
        label: 'KSO · Customer >200.001 Sm³/bln',
        regions: {
            'JAWA BARAT': ['Torabika Cikupa/Ekajaya', 'Calbee/ACE', 'Surya Pamenang (JES)'],
            'JAWA TENGAH': ['Surya Pamenang (JES)'],
            'JAWA TIMUR': ['Pentawira / REN'],
        },
    },
];
const workbookCustomerGroupByRegion = new Map();
workbookCustomerGroups.forEach((group, groupIndex) => {
    Object.entries(group.regions).forEach(([region, customers]) => {
        if (!workbookCustomerGroupByRegion.has(region)) {
            workbookCustomerGroupByRegion.set(region, new Map());
        }
        customers.forEach((customer) => {
            workbookCustomerGroupByRegion.get(region).set(normalizeCustomerOrder(customer), groupIndex);
        });
    });
});
const laterWorkbookCustomerGroups = [
    { region: 'JAWA BARAT', customer: 'greenpulse', fromMonth: '2026-08', groupIndex: 0 },
    { region: 'JAWA BARAT', customer: 'ksnranca', fromMonth: '2026-06', groupIndex: 2 },
    { region: 'JAWA BARAT', customer: 'concord', fromMonth: '2026-09', groupIndex: 3 },
    { region: 'JAWA BARAT', customer: 'kimiafarmaima', fromMonth: '2026-09', groupIndex: 5 },
    { region: 'JAWA TENGAH', customer: 'jiuqi', fromMonth: '2026-04', groupIndex: 6 },
];
function workbookGroupForCustomer(row, month) {
    const region = String(row.region ?? '').trim().toUpperCase();
    const customerKey = normalizeCustomerOrder(row.customer);
    if (region === 'JAWA TENGAH DAN TIMUR') {
        const groupIndex = {
            cvpa: 0,
            gfkulit: 0,
            rpi: 0,
            rb: 1,
            gfatom: 1,
            hskksogas: 6,
            suryapamenangjes: 6,
            jiuqi: 6,
            suryapamenangglobal: 7,
        }[customerKey];
        if (groupIndex != null) {
            return { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
        }
    }
    const laterGroup = laterWorkbookCustomerGroups.find((group) =>
        group.region === region
        && group.customer === customerKey
        && month >= group.fromMonth);
    if (laterGroup) {
        return { index: laterGroup.groupIndex, label: workbookCustomerGroups[laterGroup.groupIndex].label };
    }
    if (region === 'JAWA TENGAH' && ['suryapamenangglobal', 'suryapamenangjes'].includes(customerKey)) {
        const isMayOrLater = month >= '2026-05';
        const groupIndex = customerKey === 'suryapamenangglobal'
            ? isMayOrLater ? 7 : 6
            : isMayOrLater ? 6 : 7;
        return { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
    }
    const groupIndex = workbookCustomerGroupByRegion.get(region)?.get(customerKey);
    return groupIndex == null
        ? { index: workbookCustomerGroups.length, label: 'Tidak tercantum di file pengguna' }
        : { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
}
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
    const activeComparisonAreas = comparisonAreas
        .filter((area) => area.key !== 'JAWA_TENGAH_DAN_TIMUR'
            || ['2026-06', '2026-07'].includes(selectedMonth))
        .map((area) => {
        if (area.key !== 'ALL_EXCEPT_JATIM') return area;
        const excludesEastJava = selectedMonth >= '2026-09';
        return {
            ...area,
            label: excludesEastJava ? 'All Area (exc. Jatim)' : 'All Area',
        };
        });
    const [report, setReport] = useState({ rows: [], operator_factors: {}, exchange_rate: 0, targets: {}, totals: {} });
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [selectedCustomerKey, setSelectedCustomerKey] = useState('');
    const [customerCatalog, setCustomerCatalog] = useState([]);
    const [customersLoading, setCustomersLoading] = useState(true);
    const [customerEntry, setCustomerEntry] = useState({
        customer: '',
        operator: '',
        region: '',
        price_unit: 'USD_MMBTU',
        price: '',
    });

    useEffect(() => {
        let active = true;
        api('/api/customers')
            .then((data) => {
                if (!Array.isArray(data) || data.some((customer) => (
                    typeof customer.customer_key !== 'string'
                    || typeof customer.customer_name !== 'string'
                    || typeof customer.operator !== 'string'
                ))) {
                    throw new Error('Format daftar customer dari server tidak valid.');
                }
                if (active) setCustomerCatalog(data);
            })
            .catch((requestError) => {
                if (active) setError(requestError.message);
            })
            .finally(() => {
                if (active) setCustomersLoading(false);
            });
        return () => { active = false; };
    }, []);

    useEffect(() => {
        if (!selectedMonth) return undefined;
        let active = true;
        setLoading(true);
        setError('');
        setSelectedCustomerKey('');
        setCustomerEntry({
            customer: '',
            operator: '',
            region: '',
            price_unit: 'USD_MMBTU',
            price: '',
        });
        setReport({ rows: [], operator_factors: {}, exchange_rate: 0, targets: {}, totals: {} });
        api(`/api/monthly-average-price?month=${encodeURIComponent(selectedMonth)}`)
            .then((data) => {
                if (!active) return;
                setSelectedCustomerKey('');
                setReport(data);
            })
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, [selectedMonth]);

    function selectCustomer(customerKey) {
        const row = report.rows.find((item) => item.customer_key === customerKey);
        const masterCustomer = customerCatalog.find((item) => item.customer_key === customerKey);
        const customer = row || masterCustomer;
        setSelectedCustomerKey(customer?.customer_key || '');
        setCustomerEntry({
            customer: row?.customer || masterCustomer?.customer_name || '',
            operator: row?.operator || masterCustomer?.operator || '',
            region: row?.region || '',
            price_unit: row?.price_unit || 'USD_MMBTU',
            price: row?.price_unit === 'IDR_SM3'
                ? row.price_rp_per_sm3 || ''
                : row?.price_usd_per_mmbtu || '',
        });
    }

    function updateCustomerName(value) {
        const normalizedName = normalizeCustomerOrder(value.trim());
        const matchingRow = report.rows.find(
            (row) => normalizeCustomerOrder(row.customer) === normalizedName,
        );
        const matchingCustomer = matchingRow || customerCatalog.find(
            (customer) => normalizeCustomerOrder(customer.customer_name) === normalizedName,
        );
        if (matchingCustomer) {
            selectCustomer(matchingCustomer.customer_key);
            return;
        }
        setSelectedCustomerKey('');
        setCustomerEntry((current) => ({
            ...current,
            customer: value,
            operator: '',
            region: '',
            price_unit: 'USD_MMBTU',
            price: '',
        }));
    }

    function updateFactor(operator, value) {
        setReport((current) => ({
            ...current,
            operator_factors: { ...current.operator_factors, [operator]: value },
            rows: current.rows.map((row) => row.operator === operator
                ? {
                    ...row,
                    mmbtu_override: null,
                    total_usd_override: null,
                    rupiah_override: null,
                }
                : row),
        }));
    }

    function updateExchangeRate(value) {
        setReport((current) => ({
            ...current,
            exchange_rate: value,
            rows: current.rows.map((row) => ({
                ...row,
                total_usd_override: null,
                rupiah_override: null,
            })),
        }));
    }

    function updateTarget(area, value) {
        setReport((current) => ({
            ...current,
            targets: { ...current.targets, [area]: value },
        }));
    }

    async function persistReport(nextReport, successMessage) {
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
                        Number(nextReport.operator_factors[operator] || 0),
                    ])),
                    exchange_rate: Number(nextReport.exchange_rate || 0),
                    targets: Object.fromEntries(activeComparisonAreas.map(({ key }) => [
                        key,
                        nextReport.targets[key] === '' || nextReport.targets[key] == null
                            ? null
                            : Number(nextReport.targets[key]),
                    ])),
                    entries: nextReport.rows.map((row) => ({
                        customer_key: row.customer_key,
                        region: row.region || '',
                        price_unit: row.price_unit || 'USD_MMBTU',
                        price_usd_per_mmbtu: row.price_unit === 'IDR_SM3'
                            ? 0
                            : Number(row.price_usd_per_mmbtu || 0),
                        price_rp_per_sm3: row.price_unit === 'IDR_SM3'
                            ? Number(row.price_rp_per_sm3 || 0)
                            : 0,
                        sm3_override: row.sm3_override ?? null,
                        mmbtu_override: row.mmbtu_override ?? null,
                        total_usd_override: row.total_usd_override ?? null,
                        rupiah_override: row.rupiah_override ?? null,
                        include_in_summary: row.include_in_summary !== false,
                    })),
                },
            });
            const refreshed = await api(`/api/monthly-average-price?month=${encodeURIComponent(selectedMonth)}`);
            setReport(refreshed);
            setNotice(successMessage);
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSaving(false);
        }
    }

    async function saveCustomerEntry(event) {
        event.preventDefault();
        const customerName = customerEntry.customer.trim();
        const price = Number(customerEntry.price);
        const row = report.rows.find((item) => item.customer_key === selectedCustomerKey);
        if (!customerName) {
            setError('Nama customer wajib diisi.');
            return;
        }
        if (!selectedCustomerKey && !customerEntry.operator) {
            setError('Pilih operator untuk customer baru.');
            return;
        }
        if (!selectedCustomerHasWorkbookData && !customerEntry.region) {
            setError('Pilih wilayah untuk customer ini.');
            return;
        }
        if (!Number.isFinite(price) || price <= 0) {
            setError('Harga harus berupa angka lebih besar dari nol.');
            return;
        }

        setError('');
        setSaving(true);
        try {
            let customerKey = selectedCustomerKey;
            let operator = row?.operator || customerEntry.operator;
            if (!customerKey) {
                const createdCustomer = await api('/api/customer-mapping', {
                    method: 'POST',
                    body: { customer: customerName, operator },
                });
                if (typeof createdCustomer.customer_key !== 'string' || !createdCustomer.customer_key) {
                    throw new Error('Server tidak mengembalikan identitas customer baru.');
                }
                customerKey = createdCustomer.customer_key;
            }

            const existingRow = row || {
                customer_key: customerKey,
                customer: customerName,
                operator,
                region: customerEntry.region,
                so_sm3: 0,
                actual_sm3: 0,
                sm3: 0,
                price_unit: customerEntry.price_unit,
                price_usd_per_mmbtu: 0,
                price_rp_per_sm3: 0,
                sm3_override: null,
                mmbtu_override: null,
                total_usd_override: null,
                rupiah_override: null,
                total_usd: 0,
                rupiah: 0,
                include_in_summary: true,
            };
            const priceChanged = existingRow.price_unit !== customerEntry.price_unit
                || (customerEntry.price_unit === 'IDR_SM3'
                    ? Number(existingRow.price_rp_per_sm3 || 0) !== price
                    : Number(existingRow.price_usd_per_mmbtu || 0) !== price);
            const updatedRow = {
                ...existingRow,
                region: customerEntry.region,
                price_unit: customerEntry.price_unit,
                price_usd_per_mmbtu: customerEntry.price_unit === 'USD_MMBTU' ? price : 0,
                price_rp_per_sm3: customerEntry.price_unit === 'IDR_SM3' ? price : 0,
                total_usd_override: priceChanged ? null : existingRow.total_usd_override,
                rupiah_override: priceChanged ? null : existingRow.rupiah_override,
            };
            const nextRows = row
                ? report.rows.map((item) => item.customer_key === customerKey ? updatedRow : item)
                : [...report.rows, updatedRow];
            const nextReport = { ...report, rows: nextRows };
            setSelectedCustomerKey(customerKey);
            await persistReport(
                nextReport,
                `Data Average Price ${customerName} berhasil disimpan untuk ${monthLabel(selectedMonth)}.`,
            );
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSaving(false);
        }
    }

    async function saveReport(event) {
        event.preventDefault();
        await persistReport(
            report,
            `Pengaturan Average Price ${monthLabel(selectedMonth)} berhasil disimpan.`,
        );
    }

    const calculatedRows = report.rows.map((row) => {
        const sm3 = Number(row.sm3 ?? row.actual_sm3 ?? 0);
        const factor = Number(report.operator_factors[row.operator] || 0);
        const volumeMmbtu = row.mmbtu_override != null
            ? Number(row.mmbtu_override)
            : factor > 0 ? sm3 / factor : 0;
        const priceUnit = row.price_unit || 'USD_MMBTU';
        const priceUsd = Number(row.price_usd_per_mmbtu || 0);
        const priceRp = Number(row.price_rp_per_sm3 || 0);
        const exchangeRate = Number(report.exchange_rate || 0);
        const calculatedRp = priceUnit === 'IDR_SM3'
            ? sm3 * priceRp
            : volumeMmbtu * priceUsd * exchangeRate;
        const totalRp = row.rupiah_override != null
            ? Number(row.rupiah_override)
            : calculatedRp;
        const calculatedUsd = priceUnit === 'IDR_SM3'
            ? (exchangeRate > 0 ? totalRp / exchangeRate : 0)
            : volumeMmbtu * priceUsd;
        const totalUsd = row.total_usd_override != null
            ? Number(row.total_usd_override)
            : calculatedUsd;
        const customerKey = normalizeCustomerOrder(row.customer_key);
        const customer = selectedMonth === '2026-01'
            ? januaryCustomerAliases[customerKey] || customerOrderAliases[customerKey] || row.customer
            : customerOrderAliases[customerKey] || row.customer;
        return {
            ...row,
            customer,
            price_unit: priceUnit,
            sm3,
            volume_mmbtu: volumeMmbtu,
            total_usd: totalUsd,
            rupiah: totalRp,
            workbook_group: workbookGroupForCustomer({ customer, region: row.region }, selectedMonth),
        };
    }).filter((row) => row.sm3_override != null
        || row.has_valid_price
        || (row.price_unit === 'IDR_SM3'
            ? Number(row.price_rp_per_sm3) > 0
            : Number(row.price_usd_per_mmbtu) > 0))
        .map((row, index) => ({ row, index }))
        .sort((left, right) => {
            const groupOrder = left.row.workbook_group.index - right.row.workbook_group.index;
            if (groupOrder !== 0) return groupOrder;
            const leftOrder = customerOrderIndex.get(normalizeCustomerOrder(left.row.customer)) ?? Infinity;
            const rightOrder = customerOrderIndex.get(normalizeCustomerOrder(right.row.customer)) ?? Infinity;
            return leftOrder - rightOrder || left.index - right.index;
        })
        .map(({ row }) => row);
    const displayRows = calculatedRows.filter((row) => row.workbook_group.index >= 4);
    const displayGroups = displayRows.reduce((groups, row) => {
        const currentGroup = groups[groups.length - 1];
        if (!currentGroup || currentGroup.group.index !== row.workbook_group.index) {
            groups.push({ group: row.workbook_group, rows: [row] });
        } else {
            currentGroup.rows.push(row);
        }
        return groups;
    }, []);
    const displayRowNumbers = new Map(displayRows.map((row, index) => [row.customer_key, index + 1]));
    const totals = calculatedRows.filter((row) =>
        row.has_valid_price && row.include_in_summary !== false,
    ).reduce((sum, row) => ({
        sm3: sum.sm3 + row.sm3,
        mmbtu: sum.mmbtu + row.volume_mmbtu,
        usd: sum.usd + row.total_usd,
        rupiah: sum.rupiah + row.rupiah,
    }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
    const averagePriceRpSm3 = totals.sm3 > 0 ? totals.rupiah / totals.sm3 : 0;
    const hasUncalculatedPriceRows = calculatedRows.some((row) =>
        !row.has_valid_price
        && (row.price_unit === 'IDR_SM3'
            ? Number(row.price_rp_per_sm3) > 0
            : Number(row.price_usd_per_mmbtu) > 0),
    );
    const customerSuggestions = Array.from(new Map(
        [
            ...pdfCustomerNames,
            ...customerCatalog.map((customer) => customer.customer_name),
            ...report.rows.map((row) => row.customer),
        ]
            .map((customerName) => [normalizeCustomerOrder(customerName), customerName])
            .filter(([customerKey]) => customerKey),
    ).values());
    const comparisonRows = activeComparisonAreas.map((area) => {
        const eligibleRows = calculatedRows.filter((row) =>
            (area.key === 'ALL_EXCEPT_JATIM'
                ? row.include_in_summary !== false
                : area.regions.includes(row.region))
            && row.sm3 + Number(row.so_sm3 || 0) > 0
            && (row.price_unit === 'IDR_SM3'
                ? Number(row.price_rp_per_sm3) > 0
                : Number(row.sm3_per_mmbtu) > 0
                    && Number(row.price_usd_per_mmbtu) > 0
                    && Number(report.exchange_rate) > 0));
        const volume = eligibleRows.reduce(
            (sum, row) => sum + row.sm3 + Number(row.so_sm3 || 0),
            0,
        );
        const rupiah = eligibleRows.reduce((sum, row) => {
            const actualSm3 = row.sm3;
            const prognosisSm3 = actualSm3 + Number(row.so_sm3 || 0);
            const rupiahPerSm3 = actualSm3 > 0
                ? row.rupiah / actualSm3
                : row.price_unit === 'IDR_SM3'
                    ? Number(row.price_rp_per_sm3)
                    : Number(row.price_usd_per_mmbtu)
                        / Number(row.sm3_per_mmbtu)
                        * Number(report.exchange_rate);
            return sum + prognosisSm3 * rupiahPerSm3;
        }, 0);
        const targetValue = report.targets[area.key];
        const target = targetValue == null || targetValue === '' ? null : Number(targetValue);
        const prognosis = volume > 0 ? rupiah / volume : null;
        const hasRegionalRows = area.key === 'ALL_EXCEPT_JATIM'
            ? calculatedRows.some((row) => row.include_in_summary !== false)
            : calculatedRows.some((row) => area.regions.includes(row.region));
        return {
            ...area,
            target,
            prognosis,
            hasRegionalRows,
            difference: target != null && prognosis != null ? prognosis - target : null,
        };
    });
    const selectedCustomer = report.rows.find((row) => row.customer_key === selectedCustomerKey);
    const selectedCustomerHasWorkbookData = Number(selectedCustomer?.sm3_override) > 0
        && !selectedCustomer?.region;
    const hasUnassignedWorkbookRegions = calculatedRows.some(
        (row) => Number(row.sm3_override) > 0 && !row.region,
    );
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
            {error && <div className="notice bad" role="alert">{error}</div>}
            {notice && <div className="notice good" role="status">{notice}</div>}
            {hasUncalculatedPriceRows && (
                <div className="notice" role="status">
                    Beberapa harga sudah tercatat, tetapi belum dapat dihitung karena kurs atau faktor konversi belum tersedia. Baris tersebut tidak masuk total.
                </div>
            )}

            <section className="average-kpi-grid">
                <article className="average-kpi average-kpi-blue"><span className="average-kpi-icon">▤</span><div><small>TOTAL SM³</small><strong>{formatInteger(totals.sm3)}</strong><span>Volume sumber perhitungan</span></div></article>
                <article className="average-kpi average-kpi-green"><span className="average-kpi-icon">◆</span><div><small>TOTAL MMBTU</small><strong>{formatDecimal(totals.mmbtu, 3)}</strong><span>Sm³ ÷ faktor operator</span></div></article>
                <article className="average-kpi average-kpi-blue"><span className="average-kpi-icon">AVG</span><div><small>AVERAGE Rp/Sm³</small><strong>{formatDecimal(averagePriceRpSm3, 2)}</strong><span>Total Rupiah ÷ volume sumber</span></div></article>
            </section>

            <section className="average-data-panel">
                <div className="average-workspace-grid">
                    <div className="average-workspace-column average-workspace-left">
                <div className="average-data-heading">
                    <div className="average-panel-heading">
                        <b>2. Hasil Perhitungan Average Price</b>
                        <small>{monthLabel(selectedMonth)} · Customer DIRECT tetap masuk total. Baris * dikecualikan dari total Summary.</small>
                    </div>
                </div>
                <form onSubmit={saveReport}>
                    <div className="average-table-wrap average-customer-table-wrap" role="region" aria-label="Tabel data Average Price Customer" tabIndex="0">
                        <table className="average-data-table">
                            <thead><tr><th>No</th><th>Customer</th><th>Operator</th><th>Sm³</th><th>MMBTU</th><th>Harga Efektif</th><th>Total (USD)</th><th>Total (Rp)</th></tr></thead>
                            <tbody>
                                {displayRows.length === 0
                                    ? (
                                        <tr>
                                            <td colSpan="8" className="empty-row">
                                                {loading
                                                    ? 'Memuat data...'
                                                    : report.rows.length === 0
                                                        ? 'Belum ada data sales untuk bulan ini.'
                                                        : 'Belum ada hasil. Pilih customer, isi harga, lalu simpan.'}
                                            </td>
                                        </tr>
                                    )
                                    : displayGroups.map((group) => {
                                        const groupTotals = group.rows
                                            .filter((row) => row.has_valid_price)
                                            .reduce((sum, row) => ({
                                                sm3: sum.sm3 + row.sm3,
                                                mmbtu: sum.mmbtu + row.volume_mmbtu,
                                                usd: sum.usd + row.total_usd,
                                                rupiah: sum.rupiah + row.rupiah,
                                            }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
                                        return <React.Fragment key={group.group.index}>
                                            {group.rows.map((row) => {
                                                return <tr key={row.customer_key}>
                                                    <td>{displayRowNumbers.get(row.customer_key)}</td>
                                                    <td>{row.customer}{row.include_in_summary === false ? ' *' : ''}</td>
                                                    <td>{row.operator}</td>
                                                    <td>{formatInteger(row.sm3)}</td>
                                                    <td>{formatDecimal(row.volume_mmbtu, 3)}</td>
                                                    <td>{row.price_unit === 'IDR_SM3'
                                                        ? `Rp ${formatDecimal(row.price_rp_per_sm3, 2)}`
                                                        : `$ ${formatDecimal(row.price_usd_per_mmbtu, 4)}`}</td>
                                                    <td>$ {formatDecimal(row.total_usd, 2)}</td>
                                                    <td>Rp {formatDecimal(row.rupiah, 2)}</td>
                                                </tr>;
                                            })}
                                            <tr className="average-workbook-subtotal">
                                                <th colSpan="3">JUMLAH</th>
                                                <th>{formatInteger(groupTotals.sm3)}</th>
                                                <th>{formatDecimal(groupTotals.mmbtu, 3)}</th>
                                                <th>—</th>
                                                <th>$ {formatDecimal(groupTotals.usd, 2)}</th>
                                                <th>Rp {formatDecimal(groupTotals.rupiah, 2)}</th>
                                            </tr>
                                        </React.Fragment>;
                                    })}
                            </tbody>
                            {displayRows.length > 0 && <tfoot><tr>
                                <th colSpan="3">TOTAL</th>
                                <th>{formatInteger(totals.sm3)}</th>
                                <th>{formatDecimal(totals.mmbtu, 3)}</th>
                                <th>—</th>
                                <th>$ {formatDecimal(totals.usd, 2)}</th>
                                <th>Rp {formatDecimal(totals.rupiah, 2)}</th>
                            </tr></tfoot>}
                        </table>
                    </div>
                </form>
                <div className="average-data-heading average-customer-entry-heading">
                    <div className="average-panel-heading">
                        <b>1. Input Average Price Customer</b>
                        <small>Data dari Excel tetap dipertahankan jika harga tidak diubah.</small>
                    </div>
                </div>
                <form className="average-entry-form" onSubmit={saveCustomerEntry}>
                    <label>
                        Periode
                        <input readOnly value={monthLabel(selectedMonth)} />
                    </label>
                    <label>
                        Customer
                        <input
                            type="text"
                            list="average-customer-options"
                            required
                            maxLength="255"
                            placeholder="Ketik nama customer"
                            value={customerEntry.customer}
                            onChange={(event) => updateCustomerName(event.target.value)}
                        />
                        <datalist id="average-customer-options">
                            {customerSuggestions.map((customerName) => (
                                <option key={normalizeCustomerOrder(customerName)} value={customerName} />
                            ))}
                        </datalist>
                    </label>
                    <label>
                        Operator
                        {selectedCustomerKey
                            ? <input readOnly value={customerEntry.operator} />
                            : <select
                                required
                                value={customerEntry.operator}
                                onChange={(event) => setCustomerEntry((current) => ({
                                    ...current,
                                    operator: event.target.value,
                                }))}
                            >
                                <option value="">Pilih operator</option>
                                {operators.map((operator) => <option key={operator} value={operator}>{operator}</option>)}
                            </select>}
                    </label>
                    <label>
                        Wilayah
                        {selectedCustomerHasWorkbookData
                            ? <input readOnly value="Tidak tersedia di file" />
                            : <select
                            required
                            value={customerEntry.region}
                            onChange={(event) => setCustomerEntry((current) => ({
                                ...current,
                                region: event.target.value,
                            }))}
                        >
                            <option value="">Pilih wilayah</option>
                            {regions.map((region) => <option key={region} value={region}>{region}</option>)}
                        </select>}
                    </label>
                    <label>
                        Satuan Harga
                        <select
                            value={customerEntry.price_unit}
                            onChange={(event) => setCustomerEntry((current) => ({
                                ...current,
                                price_unit: event.target.value,
                                price: '',
                            }))}
                        >
                            <option value="USD_MMBTU">USD/MMBTU</option>
                            <option value="IDR_SM3">Rp/Sm³</option>
                        </select>
                    </label>
                    <label>
                        Harga {customerEntry.price_unit === 'IDR_SM3' ? '(Rp/Sm³)' : '(USD/MMBTU)'}
                        <input
                            required
                            type="number"
                            min="0"
                            step={customerEntry.price_unit === 'IDR_SM3' ? '1' : '0.0001'}
                            value={customerEntry.price}
                            onChange={(event) => setCustomerEntry((current) => ({
                                ...current,
                                price: event.target.value,
                            }))}
                        />
                    </label>
                    <div className="average-entry-actions">
                        <button className="primary" type="submit" disabled={saving || loading || customersLoading || !selectedMonth}>
                            {saving ? 'Menyimpan...' : 'Simpan Harga'}
                        </button>
                    </div>
                </form>
                <form onSubmit={saveReport}>
                    <div className="average-data-heading average-conversion-heading">
                        <div className="average-panel-heading">
                            <b>3. Faktor Konversi Operator dan Kurs</b>
                            <small>Faktor dan kurs berlaku untuk seluruh customer pada {monthLabel(selectedMonth)}.</small>
                        </div>
                        <label className="average-filter-field">
                            <span>Kurs Rp/USD</span>
                            <input aria-label="Kurs Rupiah per USD" type="number" min="0" step="1" value={report.exchange_rate || ''} onChange={(event) => updateExchangeRate(event.target.value)} />
                        </label>
                    </div>
                    <div className="average-table-wrap average-conversion-wrap">
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
                </form>
                    </div>

                    <div className="average-workspace-column average-workspace-right">
                    <form onSubmit={saveReport}>
                    <div className="average-data-heading average-comparison-heading">
                        <div className="average-panel-heading">
                            <b>4. Target Harga dan Prognosa (Rp/Sm³)</b>
                            <small>{monthLabel(selectedMonth)} · Prognosa menggunakan (Sm³ actual customer + SO) · Selisih = Prognosa − Target</small>
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
                                    <td>{row.prognosis == null
                                        ? hasUnassignedWorkbookRegions && !row.hasRegionalRows
                                            ? 'Tidak ada data wilayah'
                                            : '—'
                                        : formatInteger(row.prognosis)}</td>
                                    <td className={row.difference == null ? '' : row.difference < 0 ? 'diff-neg' : 'diff-pos'}>
                                        {row.difference == null
                                            ? hasUnassignedWorkbookRegions && !row.hasRegionalRows
                                                ? 'Tidak ada data wilayah'
                                                : '—'
                                            : formatDifference(row.difference)}
                                    </td>
                                </tr>
                            ))}</tbody>
                        </table>
                    </div>
                    <div className="average-toolbar average-monthly-save">
                        <button className="average-add-button" type="submit" disabled={saving || loading || !selectedMonth}>
                            {saving ? 'Menyimpan...' : 'Simpan Data Bulan Ini'}
                        </button>
                    </div>
                    </form>
                    </div>
                </div>
            </section>
        </div>
    );
}
