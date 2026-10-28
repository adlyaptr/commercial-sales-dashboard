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
const workbookRegionsByCustomer = new Map();
const januaryCentralEastCustomers = new Set(
    workbookCustomerGroups.flatMap((group) => [
        ...(group.regions['JAWA TENGAH'] || []),
        ...(group.regions['JAWA TIMUR'] || []),
    ]).map(normalizeCustomerOrder),
);
workbookCustomerGroups.forEach((group, groupIndex) => {
    Object.entries(group.regions).forEach(([region, customers]) => {
        if (!workbookCustomerGroupByRegion.has(region)) {
            workbookCustomerGroupByRegion.set(region, new Map());
        }
        customers.forEach((customer) => {
            const customerKey = normalizeCustomerOrder(customer);
            workbookCustomerGroupByRegion.get(region).set(customerKey, groupIndex);
            if (!workbookRegionsByCustomer.has(customerKey)) {
                workbookRegionsByCustomer.set(customerKey, new Set());
            }
            workbookRegionsByCustomer.get(customerKey).add(region);
        });
    });
});
function workbookRegionForCustomer(customer) {
    const regionsForCustomer = workbookRegionsByCustomer.get(normalizeCustomerOrder(customer));
    return regionsForCustomer?.size === 1 ? [...regionsForCustomer][0] : '';
}
function workbookAreaForCustomer(region, customer, month) {
    if (
        month === '2026-01'
        && januaryCentralEastCustomers.has(normalizeCustomerOrder(customer))
    ) {
        return 'JAWA TENGAH DAN TIMUR';
    }
    const normalizedRegion = String(region ?? '').trim().toUpperCase()
        || workbookRegionForCustomer(customer);
    if (
        month >= '2026-01'
        && month < '2026-08'
        && ['JAWA TENGAH', 'JAWA TIMUR', 'JAWA TENGAH DAN TIMUR'].includes(normalizedRegion)
    ) {
        return 'JAWA TENGAH DAN TIMUR';
    }
    return normalizedRegion || 'WILAYAH BELUM DIPETAKAN';
}
const laterWorkbookCustomerGroups = [
    { region: 'JAWA BARAT', customer: 'greenpulse', fromMonth: '2026-08', groupIndex: 0 },
    { region: 'JAWA BARAT', customer: 'ksnranca', fromMonth: '2026-06', groupIndex: 2 },
    { region: 'JAWA BARAT', customer: 'concord', fromMonth: '2026-09', groupIndex: 3 },
    { region: 'JAWA BARAT', customer: 'kimiafarmaima', fromMonth: '2026-09', groupIndex: 5 },
    { region: 'JAWA TENGAH', customer: 'jiuqi', fromMonth: '2026-04', groupIndex: 6 },
];
function workbookGroupForCustomer(row, month) {
    const region = workbookAreaForCustomer(row.region, row.customer, month);
    const customerKey = normalizeCustomerOrder(row.customer);
    if (region === 'JAWA TENGAH DAN TIMUR') {
        const groupIndex = {
            cvpa: 0,
            gfkulit: 0,
            rpi: 0,
            rb: 1,
            gfatom: 1,
            hskksogas: 6,
            jiuqi: 6,
        }[customerKey];
        if (groupIndex != null) {
            return { index: groupIndex, label: workbookCustomerGroups[groupIndex].label };
        }
        if (['suryapamenangglobal', 'suryapamenangjes'].includes(customerKey)) {
            const isMayOrLater = month >= '2026-05';
            const groupIndex = customerKey === 'suryapamenangglobal'
                ? isMayOrLater ? 7 : 6
                : isMayOrLater ? 6 : 7;
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
const parseExchangeRate = (value) => {
    const normalized = String(value ?? '').trim().replace(/[.\s]/g, '');
    if (!normalized) return 0;
    if (!/^\d+$/.test(normalized)) return null;
    const parsed = Number(normalized);
    return Number.isSafeInteger(parsed) ? parsed : null;
};

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
    const [exchangeRateInput, setExchangeRateInput] = useState('');
    const [exchangeRateInputError, setExchangeRateInputError] = useState(false);
    const [exchangeRateInputDirty, setExchangeRateInputDirty] = useState(false);
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
        setExchangeRateInput('');
        setExchangeRateInputError(false);
        setExchangeRateInputDirty(false);
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
                setExchangeRateInput(data.exchange_rate
                    ? Number.isInteger(Number(data.exchange_rate))
                        ? formatInteger(data.exchange_rate)
                        : String(data.exchange_rate)
                    : '');
                setExchangeRateInputDirty(false);
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
        setExchangeRateInput(value);
        setExchangeRateInputDirty(true);
        const parsedRate = parseExchangeRate(value);
        setExchangeRateInputError(parsedRate == null);
        if (parsedRate == null) return;
        setReport((current) => ({
            ...current,
            exchange_rate: parsedRate,
            rows: current.rows.map((row) => ({
                ...row,
                total_usd_override: null,
                rupiah_override: row.price_unit === 'IDR_SM3'
                    ? row.rupiah_override
                    : null,
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
        const exchangeRate = exchangeRateInputDirty
            ? parseExchangeRate(exchangeRateInput)
            : Number(nextReport.exchange_rate || 0);
        if (exchangeRate == null) {
            setExchangeRateInputError(true);
            setError('Kurs harus berupa angka bulat. Contoh: 18.069 berarti Rp18.069 per USD.');
            return;
        }
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
                    exchange_rate: exchangeRate,
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
            setExchangeRateInput(refreshed.exchange_rate
                ? Number.isInteger(Number(refreshed.exchange_rate))
                    ? formatInteger(refreshed.exchange_rate)
                    : String(refreshed.exchange_rate)
                : '');
            setExchangeRateInputError(false);
            setExchangeRateInputDirty(false);
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
                setCustomerCatalog((current) => (
                    current.some((customer) => customer.customer_key === customerKey)
                        ? current
                        : [...current, {
                            customer_key: customerKey,
                            customer_name: customerName,
                            operator,
                        }]
                ));
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

    const workbookAreaOrder = selectedMonth >= '2026-01' && selectedMonth < '2026-08'
        ? ['JAWA BARAT', 'JAWA TENGAH DAN TIMUR', 'WILAYAH BELUM DIPETAKAN']
        : ['JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR', 'WILAYAH BELUM DIPETAKAN'];
    const workbookAreaOrderByName = new Map(
        workbookAreaOrder.map((area, index) => [area, index]),
    );
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
        const workbookArea = workbookAreaForCustomer(row.region, customer, selectedMonth);
        const workbookGroup = workbookGroupForCustomer({ customer, region: workbookArea }, selectedMonth);
        return {
            ...row,
            customer,
            price_unit: priceUnit,
            sm3,
            volume_mmbtu: volumeMmbtu,
            total_usd: totalUsd,
            rupiah: totalRp,
            workbook_group: workbookGroup,
            workbook_area: workbookArea,
        };
    }).map((row, index) => ({ row, index }))
        .sort((left, right) => {
            const leftAreaOrder = workbookAreaOrderByName.get(left.row.workbook_area) ?? Infinity;
            const rightAreaOrder = workbookAreaOrderByName.get(right.row.workbook_area) ?? Infinity;
            if (leftAreaOrder !== rightAreaOrder) return leftAreaOrder - rightAreaOrder;
            const groupOrder = left.row.workbook_group.index - right.row.workbook_group.index;
            if (groupOrder !== 0) return groupOrder;
            const leftOrder = customerOrderIndex.get(normalizeCustomerOrder(left.row.customer)) ?? Infinity;
            const rightOrder = customerOrderIndex.get(normalizeCustomerOrder(right.row.customer)) ?? Infinity;
            return leftOrder - rightOrder || left.index - right.index;
        })
        .map(({ row }) => row);
    const displayRows = calculatedRows.filter((row) =>
        row.sm3 > 0
        || Number(row.price_usd_per_mmbtu) > 0
        || Number(row.price_rp_per_sm3) > 0
        || Number(row.total_usd_override) > 0
        || Number(row.rupiah_override) > 0,
    );
    const displayGroups = displayRows.reduce((groups, row) => {
        const currentGroup = groups[groups.length - 1];
        if (
            !currentGroup
            || currentGroup.group.index !== row.workbook_group.index
            || currentGroup.area !== row.workbook_area
        ) {
            groups.push({ area: row.workbook_area, group: row.workbook_group, rows: [row] });
        } else {
            currentGroup.rows.push(row);
        }
        return groups;
    }, []);
    const displayRowNumbers = new Map();
    displayGroups.forEach((group) => {
        group.rows.forEach((row, index) => {
            displayRowNumbers.set(row.customer_key, index + 1);
        });
    });
    const displayCustomerNameCounts = displayRows.reduce((counts, row) => {
        const key = normalizeCustomerOrder(row.customer);
        counts.set(key, (counts.get(key) || 0) + 1);
        return counts;
    }, new Map());
    const totals = calculatedRows.filter((row) =>
        row.has_valid_price && row.include_in_summary !== false,
    ).reduce((sum, row) => ({
        sm3: sum.sm3 + row.sm3,
        mmbtu: sum.mmbtu + row.volume_mmbtu,
        usd: sum.usd + row.total_usd,
        rupiah: sum.rupiah + row.rupiah,
    }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
    const validRowsByArea = calculatedRows
        .filter((row) => row.has_valid_price && row.sm3 > 0)
        .reduce((areas, row) => {
            const areaRows = areas.get(row.workbook_area) || [];
            areaRows.push(row);
            areas.set(row.workbook_area, areaRows);
            return areas;
        }, new Map());
    const standaloneAreas = new Set(
        Array.from(validRowsByArea.entries())
            .filter(([, rows]) => !rows.some((row) => row.include_in_summary !== false))
            .map(([area]) => area),
    );
    const regionalTotalsByName = new Map([
        ['JAWA BARAT', { region: 'JAWA BARAT', sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 }],
        ['JAWA TENGAH', { region: 'JAWA TENGAH', sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 }],
        ['JAWA TIMUR', { region: 'JAWA TIMUR', sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 }],
    ]);
    calculatedRows.filter((row) =>
        row.has_valid_price
        && (row.include_in_summary !== false || standaloneAreas.has(row.workbook_area)),
    ).forEach((row) => {
        const region = row.workbook_area || 'WILAYAH BELUM DIPETAKAN';
        if (!regionalTotalsByName.has(region)) {
            regionalTotalsByName.set(region, { region, sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
        }
        const regionTotals = regionalTotalsByName.get(region);
        regionTotals.sm3 += row.sm3;
        regionTotals.mmbtu += row.volume_mmbtu;
        regionTotals.usd += row.total_usd;
        regionTotals.rupiah += row.rupiah;
    });
    const regionalTotals = Array.from(regionalTotalsByName.values());
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
        const areaTotals = area.key === 'ALL_EXCEPT_JATIM'
            ? totals
            : area.regions.reduce((sum, region) => {
                const regionTotals = regionalTotalsByName.get(region);
                if (!regionTotals) return sum;
                return {
                    sm3: sum.sm3 + regionTotals.sm3,
                    rupiah: sum.rupiah + regionTotals.rupiah,
                };
            }, { sm3: 0, rupiah: 0 });
        const targetValue = report.targets[area.key];
        const target = targetValue == null || targetValue === '' ? null : Number(targetValue);
        const prognosis = areaTotals.sm3 > 0
            ? areaTotals.rupiah / areaTotals.sm3
            : null;
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
                <article className="average-kpi average-kpi-teal"><span className="average-kpi-icon">AVG</span><div><small>AVERAGE Rp/Sm³</small><strong>{formatDecimal(averagePriceRpSm3, 2)}</strong><span>Total Rupiah ÷ volume sumber</span></div></article>
            </section>

            <section className="average-data-panel">
                <div className="average-workspace-grid">
                    <div className="average-workspace-column average-workspace-left">
                <div className="average-data-heading">
                    <div className="average-panel-heading">
                        <b>2. Hasil Perhitungan Average Price</b>
                        <small>{monthLabel(selectedMonth)} · Wilayah mengikuti workbook: Jawa Tengah dan Timur satu blok pada Januari–Juli 2026, lalu terpisah mulai Agustus. Customer BELUM DIPETAKAN tetap terpisah; tanda * berarti dikecualikan dari Summary.</small>
                    </div>
                </div>
                <form onSubmit={saveReport}>
                    <div className="average-table-wrap average-customer-table-wrap" role="region" aria-label="Tabel data Average Price Customer" tabIndex="0">
                        <table className="average-data-table">
                            <thead><tr><th>No</th><th>Customer</th><th>Sm³</th><th>MMBTU</th><th>Harga / MMBTU</th><th>Total USD</th><th>Total Rupiah</th></tr></thead>
                            <tbody>
                                {displayRows.length === 0
                                    ? (
                                        <tr>
                                            <td colSpan="7" className="empty-row">
                                                {loading
                                                    ? 'Memuat data...'
                                                    : 'Belum ada data volume untuk bulan ini.'}
                                            </td>
                                        </tr>
                                    )
                                    : displayGroups.map((group, groupIndex) => {
                                        const groupTotals = group.rows
                                            .filter((row) => row.has_valid_price
                                                && (row.include_in_summary !== false
                                                    || standaloneAreas.has(group.area)))
                                            .reduce((sum, row) => ({
                                                    sm3: sum.sm3 + row.sm3,
                                                    mmbtu: sum.mmbtu + row.volume_mmbtu,
                                                    usd: sum.usd + row.total_usd,
                                                    rupiah: sum.rupiah + row.rupiah,
                                            }), { sm3: 0, mmbtu: 0, usd: 0, rupiah: 0 });
                                        const isUnmappedGroup = group.group.index >= workbookCustomerGroups.length;
                                        const showAreaHeading = !isUnmappedGroup
                                            && (groupIndex === 0 || displayGroups[groupIndex - 1].area !== group.area);
                                        const isLastGroupInArea = groupIndex === displayGroups.length - 1
                                            || displayGroups[groupIndex + 1].area !== group.area;
                                        const areaTotals = regionalTotalsByName.get(group.area);
                                        return <React.Fragment key={`${group.area}:${group.group.index}`}>
                                                    {showAreaHeading && (
                                                        <tr className="average-workbook-area">
                                                                <th colSpan="7">{group.area}</th>
                                                        </tr>
                                                        )}
                                                        <tr className={`average-workbook-group${isUnmappedGroup ? ' average-unmapped-group' : ''}`}>
                                                            {isUnmappedGroup
                                                                ? <th colSpan="7">BELUM DIPETAKAN</th>
                                                                : <>
                                                                    <th>{group.group.index < 4 ? 'DIRECT' : 'KSO'}</th>
                                                                    <th>{group.group.label.replace(/^KSO · /, '')}</th>
                                                                    <th colSpan="5"></th>
                                                                </>}
                                                        </tr>
                                                        {group.rows.map((row) => {
                                                            return <tr key={row.customer_key}>
                                                            <td>{displayRowNumbers.get(row.customer_key)}</td>
                                                            <td>
                                                                {row.customer}{row.include_in_summary === false ? ' *' : ''}
                                                                {displayCustomerNameCounts.get(normalizeCustomerOrder(row.customer)) > 1
                                                                    && <small className="average-customer-key">key: {row.customer_key}</small>}
                                                            </td>
                                                            <td>{formatInteger(row.sm3)}</td>
                                                            <td>{formatDecimal(row.volume_mmbtu, 3)}</td>
                                                            <td>{row.has_valid_price
                                                                ? <>
                                                                    {row.price_unit === 'IDR_SM3' ? 'Rp ' : '$ '}
                                                                    {row.price_unit === 'IDR_SM3'
                                                                        ? formatDecimal(row.price_rp_per_sm3, 2)
                                                                        : formatDecimal(row.price_usd_per_mmbtu, 2)}
                                                                </>
                                                                : '—'}
                                                            </td>
                                                            <td>{row.has_valid_price ? `$ ${formatDecimal(row.total_usd, 2)}` : '—'}</td>
                                                            <td>{row.has_valid_price ? `Rp ${formatDecimal(row.rupiah, 2)}` : '—'}</td>
                                                    </tr>;
                                                })}
                                                <tr className="average-workbook-subtotal">
                                                    <th colSpan="2">{isUnmappedGroup ? 'JUMLAH BELUM DIPETAKAN' : 'JUMLAH'}</th>
                                                    <th>{formatInteger(groupTotals.sm3)}</th>
                                                    <th>{formatDecimal(groupTotals.mmbtu, 3)}</th>
                                                    <th>—</th>
                                                    <th>$ {formatDecimal(groupTotals.usd, 2)}</th>
                                                    <th>Rp {formatDecimal(groupTotals.rupiah, 2)}</th>
                                                </tr>
                                                <tr className="average-workbook-average">
                                                    <th colSpan="2">AVG</th>
                                                    <th>—</th>
                                                    <th>—</th>
                                                    <th>
                                                        {groupTotals.mmbtu > 0
                                                            ? `$ ${formatDecimal(groupTotals.usd / groupTotals.mmbtu, 2)}`
                                                            : '—'}
                                                    </th>
                                                    <th>—</th>
                                                    <th>
                                                        {groupTotals.sm3 > 0
                                                            ? `Rp ${formatDecimal(groupTotals.rupiah / groupTotals.sm3, 2)}`
                                                            : '—'}
                                                    </th>
                                                </tr>
                                                {isLastGroupInArea && areaTotals && (
                                                    <>
                                                        <tr className="average-regional-total-row">
                                                            <th colSpan="2">TOTAL {areaTotals.region}{standaloneAreas.has(group.area) ? ' · DI LUAR KONSOLIDASI' : ''}</th>
                                                            <th>{formatInteger(areaTotals.sm3)}</th>
                                                            <th>{formatDecimal(areaTotals.mmbtu, 3)}</th>
                                                            <th>—</th>
                                                            <th>$ {formatDecimal(areaTotals.usd, 2)}</th>
                                                            <th>Rp {formatDecimal(areaTotals.rupiah, 2)}</th>
                                                        </tr>
                                                        <tr className="average-regional-average-row">
                                                            <th colSpan="6">ASP {areaTotals.region}{standaloneAreas.has(group.area) ? ' · DI LUAR KONSOLIDASI' : ''}</th>
                                                            <th>
                                                                {areaTotals.sm3 > 0
                                                                    ? `Rp ${formatDecimal(areaTotals.rupiah / areaTotals.sm3, 2)}`
                                                                    : '—'}
                                                            </th>
                                                        </tr>
                                                    </>
                                                )}
                                            </React.Fragment>;
                                    })}
                            </tbody>
                            {displayRows.length > 0 && <tfoot>
                                <tr>
                                    <th colSpan="2">TOTAL KESELURUHAN</th>
                                    <th>{formatInteger(totals.sm3)}</th>
                                    <th>{formatDecimal(totals.mmbtu, 3)}</th>
                                    <th>—</th>
                                    <th>$ {formatDecimal(totals.usd, 2)}</th>
                                    <th>Rp {formatDecimal(totals.rupiah, 2)}</th>
                                </tr>
                            </tfoot>}
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
                            <small>Faktor dan kurs berlaku untuk seluruh customer pada {monthLabel(selectedMonth)}. Masukkan kurs dengan format Indonesia; contoh 18.069 berarti Rp18.069/USD.</small>
                        </div>
                        <label className="average-filter-field">
                            <span>Kurs Rp/USD</span>
                            <input
                                aria-label="Kurs Rupiah per USD"
                                type="text"
                                inputMode="decimal"
                                value={exchangeRateInput}
                                aria-invalid={exchangeRateInputError}
                                onChange={(event) => updateExchangeRate(event.target.value)}
                                onBlur={() => {
                                    if (!exchangeRateInputDirty) return;
                                    const parsedRate = parseExchangeRate(exchangeRateInput);
                                    if (parsedRate != null) {
                                        setExchangeRateInput(parsedRate ? formatInteger(parsedRate) : '');
                                    }
                                }}
                            />
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
                            <small>{monthLabel(selectedMonth)} · Prognosa mengikuti ASP pada hasil perhitungan Average Price · Selisih = Prognosa − Target</small>
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
