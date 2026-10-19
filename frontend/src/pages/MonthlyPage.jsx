
import React, { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../api";

const months = [
  "Januari", "Februari", "Maret", "April",
  "Mei", "Juni", "Juli", "Agustus",
  "September", "Oktober", "November", "Desember"
];

const operators = ["SETU", "KHT", "BLORA", "WUNUT"];

const regionByOperator = {
  SETU: "JAWA BARAT",
  KHT: "JAWA BARAT",
  BLORA: "JAWA TENGAH",
  WUNUT: "JAWA TIMUR"
};

const regions = ["JAWA BARAT", "JAWA TENGAH", "JAWA TIMUR"];
const colors = ["#1777d1", "#f0a43a", "#70afe4"];

const fmt = (value) =>
  new Intl.NumberFormat("id-ID", {
    maximumFractionDigits: 0
  }).format(Number(value) || 0);

const fmtSO = (value) =>
  new Intl.NumberFormat("id-ID", {
    maximumFractionDigits: 2
  }).format(Number(value) || 0);

const parseLocalizedNumber = (value) => {
  const normalizedInput = value.trim();
  if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?$/.test(normalizedInput)) {
    return Number.NaN;
  }

  return Number(
    normalizedInput.replaceAll(".", "").replace(",", ".")
  );
};

const fmtPercent = (value) =>
  `${Number(value || 0).toLocaleString("id-ID", {
    maximumFractionDigits: 2
  })}%`;

const sum = (values) =>
  values.reduce((total, value) => total + (Number(value) || 0), 0);

function periodKeysBetween(startDate, endDate) {
  if (!startDate || !endDate) return [];
  const periods = [];
  const [startYear, startMonth] = startDate.slice(0, 7).split("-").map(Number);
  const [endYear, endMonth] = endDate.slice(0, 7).split("-").map(Number);
  let year = startYear;
  let month = startMonth;
  while (year < endYear || (year === endYear && month <= endMonth)) {
    periods.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return periods;
}

function periodLabel(period) {
  const [year, month] = period.split("-").map(Number);
  return `${months[month - 1]} ${year}`;
}

function buildCustomerRows(items = [], periods = []) {
  const customerMap = new Map();
  const periodIndexes = new Map(periods.map((period, index) => [period, index]));

  for (const item of items) {
    const key = item.customer_key;

    if (!customerMap.has(key)) {
      customerMap.set(key, {
        key,
        customer: item.customer,
        operator: item.operator,
        region: regionByOperator[item.operator] || "LAINNYA",
        soValues: Array(periods.length).fill(0),
        actualValues: Array(periods.length).fill(0)
      });
    }

    const row = customerMap.get(key);
    const index = periodIndexes.get(item.period);

    if (index !== undefined) {
      row.soValues[index] += Number(item.so) || 0;
      row.actualValues[index] += Number(item.actual) || 0;
    }
  }

  return Array.from(customerMap.values());
}

export default function MonthlyPage() {
  const { rangeStartDate, rangeEndDate } = useOutletContext();
  const [region, setRegion] = useState("Semua Wilayah");
  const [operator, setOperator] = useState("Semua MS");

  const [filter, setFilter] = useState({
    region: "Semua Wilayah",
    operator: "Semua MS",
    startDate: rangeStartDate,
    endDate: rangeEndDate,
  });

  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [manualSO, setManualSO] = useState(null);
  const [manualSOInput, setManualSOInput] = useState("");
  const [manualSOSaving, setManualSOSaving] = useState(false);
  const [manualSOError, setManualSOError] = useState("");
  const [manualSOSaved, setManualSOSaved] = useState(false);
  const periodKeys = useMemo(
    () => periodKeysBetween(filter.startDate, filter.endDate),
    [filter.startDate, filter.endDate],
  );
  const periodLabels = useMemo(() => periodKeys.map(periodLabel), [periodKeys]);

  useEffect(() => {
    setFilter((current) => ({
      ...current,
      startDate: rangeStartDate,
      endDate: rangeEndDate,
    }));
  }, [rangeStartDate, rangeEndDate]);

  useEffect(() => {
    let cancelled = false;

    async function loadMonthlyData() {
      setLoading(true);
      setError("");

      try {
        if (!filter.startDate || !filter.endDate) {
          setRecords([]);
          return;
        }
        const params = new URLSearchParams({
          start_date: filter.startDate,
          end_date: filter.endDate,
        });
        const result = await api(`/api/monthly-range?${params.toString()}`);

        if (cancelled) return;

        setRecords(buildCustomerRows(result.items || [], periodKeys));
      } catch (err) {
        if (cancelled) return;

        setRecords([]);
        setError(
          err.message ||
          "Data bulanan gagal dimuat dari database."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadMonthlyData();

    return () => {
      cancelled = true;
    };
  }, [filter.startDate, filter.endDate, periodKeys]);

  const monthIndex = Math.max(0, periodKeys.length - 1);
  const selectedMonthKey = periodKeys[0] || "";

  useEffect(() => {
    let cancelled = false;
    if (!selectedMonthKey) {
      setManualSO(null);
      setManualSOInput("");
      return () => { cancelled = true; };
    }
    setManualSO(null);
    setManualSOInput("");
    setManualSOError("");
    setManualSOSaved(false);

    api(`/api/monthly-so?month=${encodeURIComponent(selectedMonthKey)}`)
      .then((result) => {
        if (cancelled) return;
        setManualSO(result.so);
        setManualSOInput(result.so == null ? "" : fmtSO(result.so));
      })
      .catch((requestError) => {
        if (!cancelled) {
          setManualSOError(
            requestError.message || "SO manual bulanan gagal dimuat."
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedMonthKey]);

  const saveManualSO = async (event) => {
    event.preventDefault();
    setManualSOError("");
    setManualSOSaved(false);

    const value = parseLocalizedNumber(manualSOInput);
    if (!Number.isFinite(value) || value < 0) {
      setManualSOError("Masukkan target menggunakan format angka Indonesia, misalnya 8.027.252.");
      return;
    }

    setManualSOSaving(true);
    try {
      const result = await api("/api/monthly-so", {
        method: "PUT",
        body: { month: selectedMonthKey, so: value }
      });
      setManualSO(result.so);
      setManualSOInput(fmtSO(result.so));
      setManualSOSaved(true);
    } catch (requestError) {
      setManualSOError(
        requestError.message || "SO manual bulanan gagal disimpan."
      );
    } finally {
      setManualSOSaving(false);
    }
  };

  const rows = useMemo(() => {
    return records.filter((item) => {
      const regionMatches =
        filter.region === "Semua Wilayah" ||
        item.region === filter.region.toUpperCase();

      const operatorMatches =
        filter.operator === "Semua MS" ||
        item.operator === filter.operator;

      return regionMatches && operatorMatches;
    });
  }, [records, filter.region, filter.operator]);

  const monthlyTotals = useMemo(() => {
    return periodLabels.map((name, index) => {
      const totalSO = sum(
        rows.map((row) => row.soValues[index])
      );

      const totalActual = sum(
        rows.map((row) => row.actualValues[index])
      );

      return {
        month: name,
        so: totalSO,
        actual: totalActual,
        diff: totalActual - totalSO
      };
    });
  }, [rows, periodLabels]);

  const totalSO = sum(monthlyTotals.map((item) => item.so));
  const totalActual = sum(monthlyTotals.map((item) => item.actual));
  const achievement = totalSO
    ? (totalActual / totalSO) * 100
    : 0;

  const previousMonth = monthIndex > 0
    ? monthlyTotals[monthIndex - 1]
    : null;

  const actualGrowth = previousMonth?.actual
    ? ((totalActual - previousMonth.actual) /
        previousMonth.actual) * 100
    : null;

  const regionTotals = useMemo(() => {
    return regions.map((name) => ({
      name,
      value: sum(
        rows
          .filter((row) => row.region === name)
          .map((row) => sum(row.actualValues))
      )
    }));
  }, [rows, monthIndex]);

  const grandRegionTotal = sum(
    regionTotals.map((item) => item.value)
  );

  const maxChartValue = Math.max(
    1,
    ...monthlyTotals.flatMap((item) => [
      item.so,
      item.actual
    ])
  );

  const chartScale = Math.ceil(maxChartValue / 5) || 1;

  const applyFilters = () => {
    setFilter({
      region,
      operator,
      startDate: rangeStartDate,
      endDate: rangeEndDate,
    });
  };

  return (
    <div className="monthly-app">
      <main className="monthly-main">
        <section className="monthly-filters">
          <label>
            Wilayah
            <select
              value={region}
              onChange={(event) => setRegion(event.target.value)}
            >
              {[
                "Semua Wilayah",
                "Jawa Barat",
                "Jawa Tengah",
                "Jawa Timur"
              ].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>

          <label>
            MS
            <select
              value={operator}
              onChange={(event) => setOperator(event.target.value)}
            >
              {["Semua MS", ...operators].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>

          <button
            className="monthly-primary"
            type="button"
            onClick={applyFilters}
            disabled={loading}
          >
            ⟳ &nbsp; {loading ? "Memuat Data..." : "Tampilkan Data"}
          </button>
        </section>

        {error && (
          <div className="notice bad" role="alert">
            {error} Pastikan endpoint `/api/monthly-range` sudah ditambahkan
            dan server backend sudah dijalankan ulang.
          </div>
        )}

        {!error && !loading && records.length === 0 && (
          <div className="notice" role="status">
            Belum ada data penjualan pada periode yang dipilih.
            Impor data melalui halaman Harian terlebih dahulu.
          </div>
        )}

        <section className="monthly-kpis">
          <article className="monthly-kpi">
            <div className="monthly-kpi-icon blue">▤</div>
            <div>
              <span>Total SO Periode</span>
              <strong>{fmtSO(periodKeys.length === 1 ? manualSO ?? totalSO : totalSO)}</strong>
              <form className="monthly-so-form" onSubmit={saveManualSO}>
                <div>
                  <input
                    id="monthly-so-target"
                    type="text"
                    inputMode="decimal"
                    placeholder="8.027.252"
                    aria-label="Input Total Target Bulanan"
                    value={manualSOInput}
                    disabled={periodKeys.length !== 1}
                    onChange={(event) => setManualSOInput(event.target.value)}
                    required
                  />
                  <button
                    type="submit"
                    disabled={manualSOSaving || periodKeys.length !== 1}
                  >
                    {manualSOSaving ? "Menyimpan..." : "Simpan"}
                  </button>
                </div>
                {periodKeys.length > 1 && <small>Input manual tersedia jika rentang hanya mencakup satu bulan.</small>}
                {manualSOError && (
                  <small className="monthly-so-error" role="alert">
                    {manualSOError}
                  </small>
                )}
                {manualSOSaved && (
                  <small className="monthly-so-success" role="status">
                    Target SO tersimpan.
                  </small>
                )}
              </form>
            </div>
          </article>

          <article className="monthly-kpi">
            <div className="monthly-kpi-icon green">◎</div>
            <div>
              <span>Total Actual (Rp)</span>
              <strong>{fmt(totalActual)}</strong>
              <small>
                {actualGrowth === null
                  ? "Tidak ada pembanding bulan sebelumnya"
                  : `${actualGrowth >= 0 ? "▲" : "▼"} ${
                      fmtPercent(Math.abs(actualGrowth))
                    } vs bulan lalu`}
              </small>
            </div>
          </article>

          <article className="monthly-kpi">
            <div className="monthly-kpi-icon gold">%</div>
            <div>
              <span>Pencapaian</span>
              <strong>{fmtPercent(achievement)}</strong>
              <small>Actual dibandingkan SO</small>
            </div>
          </article>

          <article className="monthly-kpi">
            <div className="monthly-kpi-icon purple">♟</div>
            <div>
              <span>Total Volume (Sm³)</span>
              <strong>{fmt(totalActual)}</strong>
              <small>Actual pada periode terpilih</small>
            </div>
          </article>
        </section>

        <section className="monthly-charts">
          <article className="monthly-card">
            <div className="monthly-card-title">
              <h2>Realisasi Bulanan (Rp)</h2>
              <div className="monthly-legend">
                <span><i className="legend-so" /> SO</span>
                <span><i className="legend-actual" /> Actual</span>
              </div>
            </div>

            <div className="monthly-chart">
              <div className="monthly-y-axis">
                {[5, 4, 3, 2, 1, 0].map((tick) => (
                  <span key={tick}>
                    {fmt(chartScale * tick)}
                  </span>
                ))}
              </div>

              <div className="monthly-plot">
                {[0, 20, 40, 60, 80, 100].map((value) => (
                  <div
                    key={value}
                    className="monthly-grid"
                    style={{ top: `${value}%` }}
                  />
                ))}

                <div className="monthly-bars">
                  {monthlyTotals.map((item) => (
                    <div
                      className="monthly-bar-group"
                      key={item.month}
                    >
                      <div
                        className="monthly-pair"
                        title={`${item.month}: SO ${fmt(item.so)}, Actual ${fmt(item.actual)}`}
                      >
                        <i
                          className="bar-so"
                          style={{
                            height: `${item.so / (chartScale * 5) * 100}%`
                          }}
                        />
                        <i
                          className="bar-actual"
                          style={{
                            height: `${item.actual / (chartScale * 5) * 100}%`
                          }}
                        />
                      </div>
                      <small>{item.month.slice(0, 3)}</small>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </article>

          <article className="monthly-card">
            <div className="monthly-card-title">
              <h2>Realisasi per Wilayah</h2>
            </div>

            <div className="monthly-region-content">
              <div
                className="monthly-donut"
                style={{
                  background: grandRegionTotal
                    ? `conic-gradient(${regionTotals.map((item, index) => {
                        const before = sum(
                          regionTotals
                            .slice(0, index)
                            .map((entry) => entry.value)
                        );
                        const start = before / grandRegionTotal * 100;
                        const end = (
                          before + item.value
                        ) / grandRegionTotal * 100;

                        return `${colors[index]} ${start}% ${end}%`;
                      }).join(",")})`
                    : "#e7eee9"
                }}
              >
                <div>
                  <small>Total Actual</small>
                  <strong>
                    Rp {(totalActual / 1_000_000).toLocaleString(
                      "id-ID",
                      { maximumFractionDigits: 2 }
                    )} M
                  </strong>
                  <b>{fmtPercent(achievement)}</b>
                </div>
              </div>

              <div className="monthly-region-legend">
                {regionTotals.map((item, index) => (
                  <div key={item.name}>
                    <i style={{ background: colors[index] }} />
                    <p>
                      <b>{item.name.replace("JAWA ", "Jawa ")}</b>
                      <span>
                        Rp {fmt(item.value)} (
                        {grandRegionTotal
                          ? (
                              item.value / grandRegionTotal * 100
                            ).toLocaleString("id-ID", {
                              maximumFractionDigits: 1
                            })
                          : "0"}%)
                      </span>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </article>
        </section>

        <footer className="monthly-footer">
          <span>Commercial Sales Monitoring</span>
          <span>
            {loading
              ? "Sedang mengambil data dari database..."
              : `Sumber: database penjualan ${filter.startDate} – ${filter.endDate}`}
          </span>
        </footer>
      </main>
    </div>
  );
}
