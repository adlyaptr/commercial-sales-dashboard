export function greenBarGradient(context, startColor, endColor) {
    const { ctx, chartArea } = context.chart;
    if (!chartArea) return startColor;

    const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
    gradient.addColorStop(0, startColor);
    gradient.addColorStop(1, endColor);
    return gradient;
}
