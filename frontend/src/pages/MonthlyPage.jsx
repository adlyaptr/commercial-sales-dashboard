
import { useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../api";
import SectionIcon from "../components/SectionIcon";

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

function periodLabel(period) {
  const [year, month] = period.split("-").map(Number);
  return `${months[month - 1]} ${year}`;
}

function buildPeriodKeys(startDate, endDate) {
  if (!startDate || !endDate || startDate > endDate) return [];

  const periods = [];
  let [year, month] = startDate.split("-").map(Number);
  const lastPeriod = endDate.slice(0, 7);

  while (`${year}-${String(month).padStart(2, "0")}` <= lastPeriod) {
    periods.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }

  return periods;
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
  const { rangeStartDate, rangeEndDate, canEdit } = useOutletContext();
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
  const [monthlySOTargets, setMonthlySOTargets] = useState({});
  const [manualSOInput, setManualSOInput] = useState("");
  const [manualSOSaving, setManualSOSaving] = useState(false);
  const [manualSOError, setManualSOError] = useState("");
  const [manualSOSaved, setManualSOSaved] = useState(false);
  const periodKeys = useMemo(
    () => buildPeriodKeys(filter.startDate, filter.endDate),
    [filter.startDate, filter.endDate]
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
  const selectedMonthKey = periodKeys.length === 1 ? periodKeys[0] : "";

  useEffect(() => {
    let cancelled = false;
    if (!periodKeys.length) {
      setMonthlySOTargets({});
      setManualSOInput("");
      return () => { cancelled = true; };
    }
    setMonthlySOTargets({});
    setManualSOInput("");
    setManualSOError("");
    setManualSOSaved(false);

    Promise.all(
      periodKeys.map(async (month) => {
        const result = await api(`/api/monthly-so?month=${encodeURIComponent(month)}`);
        return [month, result.so];
      })
    )
      .then((targets) => {
        if (cancelled) return;
        const targetMap = Object.fromEntries(targets);
        setMonthlySOTargets(targetMap);
        if (selectedMonthKey) {
          const target = targetMap[selectedMonthKey];
          setManualSOInput(target == null ? "" : fmtSO(target));
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setManualSOError(
            requestError.message || "Target SO bulanan gagal dimuat."
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [periodKeys, selectedMonthKey]);

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
      setMonthlySOTargets((current) => ({
        ...current,
        [selectedMonthKey]: result.so,
      }));
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
  const totalPeriodTarget = sum(
    monthlyTotals.map(
      (item, index) => monthlySOTargets[periodKeys[index]] ?? item.so
    )
  );
  const achievement = totalPeriodTarget
    ? (totalActual / totalPeriodTarget) * 100
    : 0;

  const currentMonth = monthlyTotals[monthIndex];
  const previousMonth = monthIndex > 0
    ? monthlyTotals[monthIndex - 1]
    : null;

  const actualGrowth = currentMonth?.actual && previousMonth?.actual
    ? ((currentMonth.actual - previousMonth.actual) /
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
              <span>Total Target Periode</span>
              <strong>{fmtSO(totalPeriodTarget)}</strong>
              {canEdit && selectedMonthKey && <form className="monthly-so-form" onSubmit={saveManualSO}>
                <div>
                  <input
                    id="monthly-so-target"
                    type="text"
                    inputMode="decimal"
                    placeholder="8.027.252"
                    aria-label="Input Total Target Bulanan"
                    value={manualSOInput}
                    onChange={(event) => setManualSOInput(event.target.value)}
                    required
                  />
                  <button
                    type="submit"
                    disabled={manualSOSaving}
                  >
                    {manualSOSaving ? "Menyimpan..." : "Simpan"}
                  </button>
                </div>
                <small>Masukkan target SO untuk bulan terpilih.</small>
                {manualSOSaved && (
                  <small className="monthly-so-success" role="status">
                    Target bulanan tersimpan.
                  </small>
                )}
              </form>}
              {periodKeys.length > 1 && (
                <small>Total target periode adalah penjumlahan target SO setiap bulan.</small>
              )}
              {canEdit && manualSOError && (
                <small className="monthly-so-error" role="alert">
                  {manualSOError}
                </small>
              )}
            </div>
          </article>

          <article className="monthly-kpi">
            <div className="monthly-kpi-icon purple">♟</div>
            <div>
              <span>Total SO</span>
              <strong>{fmt(totalSO)}</strong>
              <small>Total SO pada periode terpilih</small>
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
              <small>Actual dibandingkan target periode</small>
            </div>
          </article>
        </section>

        <section className="monthly-charts">
          <article className="monthly-card">
            <div className="monthly-card-title">
              <h2><SectionIcon name="sales" />Realisasi Bulanan (Rp)</h2>
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
              <h2><SectionIcon name="region" />Realisasi per Wilayah</h2>
            </div>

            <div className="monthly-region-content">
              <div
                className="monthly-pie"
                role="img"
                aria-label={`Realisasi per wilayah: ${regionTotals.map((item) => `${item.name.replace("JAWA ", "Jawa ")}, ${fmt(item.value)} rupiah, ${grandRegionTotal ? (item.value / grandRegionTotal * 100).toLocaleString("id-ID", { maximumFractionDigits: 1 }) : "0"} persen`).join("; ")}`}
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
                <div className="monthly-pie-center">
                  <span>Total Realisasi</span>
                  <strong>Rp {fmt(grandRegionTotal)}</strong>
                </div>
              </div>
              <div className="monthly-region-legend">
                {regionTotals.map((item, index) => (
                  <div key={item.name}>
                    <i style={{ background: colors[index] }} />
                    <p>
                      <b>{item.name.replace("JAWA ", "Jawa ")}</b>
                      <span>Rp {fmt(item.value)}</span>
                    </p>
                    <strong>
                      {grandRegionTotal
                        ? (item.value / grandRegionTotal * 100).toLocaleString(
                            "id-ID",
                            { maximumFractionDigits: 1 }
                          )
                        : "0"}%
                    </strong>
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
              : `Sumber: database penjualan ${
                  filter.startDate && filter.endDate
                    ? `${filter.startDate.split("-").reverse().join("/")} - ${filter.endDate.split("-").reverse().join("/")}`
                    : "—"
                }`}
          </span>
        </footer>
      </main>
    </div>
  );
}
