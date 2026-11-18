export function hasAveragePriceDisplayData(row) {
    return Number(row.sm3) > 0
        || Number(row.price_usd_per_mmbtu) > 0
        || Number(row.price_rp_per_sm3) > 0
        || Number(row.total_usd_override) > 0
        || Number(row.rupiah_override) > 0;
}
