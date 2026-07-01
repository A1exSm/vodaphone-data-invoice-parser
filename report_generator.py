from __future__ import annotations

import os
import argparse
import statistics
import tempfile
from dataclasses import dataclass, field
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
    KeepTogether, PageBreak,
)


from parser import phone_numbers, PhoneNumber, DataYear

MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKEND_DAYS = {"Sat", "Sun"}
CHART_COLOR = "#3B82F6"
ACCENT_COLOR = "#F59E0B"


def format_gb(value: float | int) -> str:
    return f"{value / 1024:.2f} GB"


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def pct_change(old: float, new: float) -> float | None:
    if old == 0:
        return None
    return (new - old) / old * 100


def generate_rows(days: list[DayRecord], style_header: Any, style_cell: Any) -> Table:
    rows = [[
        Paragraph("Date", style_header),
        Paragraph("Weekday", style_header),
        Paragraph("Usage", style_header)
    ]]
    for d in days:
        rows.append([
            Paragraph(f"{d.month} {d.date}, {d.year}", style_cell),
            Paragraph(d.weekday, style_cell),
            Paragraph(format_gb(d.data_mb), style_cell)
        ])
    return Table(rows, colWidths=[2.2 * inch, 1.5 * inch, 1.5 * inch])


@dataclass
class DayRecord:
    year: str
    month: str
    date: int
    weekday: str
    data_mb: float


@dataclass
class PhoneInsights:
    number: str
    total_data_mb: float
    years_sorted: list[str] = field(default_factory=list)
    year_totals: dict[str, float] = field(default_factory=dict)
    year_month_avg: dict[str, float] = field(default_factory=dict)
    year_month_median: dict[str, float] = field(default_factory=dict)
    year_best_month: dict[str, tuple[str, float]] = field(default_factory=dict)
    year_worst_month: dict[str, tuple[str, float]] = field(default_factory=dict)
    year_over_year_change: dict[str, float | None] = field(default_factory=dict)
    all_days: list[DayRecord] = field(default_factory=list)
    top_days: list[DayRecord] = field(default_factory=list)
    quiet_days: list[DayRecord] = field(default_factory=list)
    weekday_avg: float = 0.0
    weekend_avg: float = 0.0
    daily_avg: float = 0.0
    has_data: bool = True


def compute_insights(phone: PhoneNumber) -> PhoneInsights:
    insights = PhoneInsights(number=phone.number, total_data_mb=phone.total_data_mb)

    if not phone.data_years:
        insights.has_data = False
        return insights

    insights.years_sorted = sorted(phone.data_years.keys())

    for year in insights.years_sorted:
        data_year: DataYear = phone.data_years[year]
        insights.year_totals[year] = data_year.total_data_mb
        insights.year_month_avg[year] = data_year.get_month_avg()
        insights.year_month_median[year] = data_year.get_month_median()

        if data_year.data_months:
            months_by_usage = sorted(
                data_year.data_months.values(), key=lambda m: m.total_data_mb
            )
            worst = months_by_usage[0]
            best = months_by_usage[-1]
            insights.year_best_month[year] = (best.month, best.total_data_mb)
            insights.year_worst_month[year] = (worst.month, worst.total_data_mb)

        for month in data_year.data_months.values():
            for day in month.data_days.values():
                insights.all_days.append(
                    DayRecord(year, month.month, day.date, day.day, day.total_data_mb)
                )

    # Year-over-year % change
    prev_total: float | None = None
    for year in insights.years_sorted:
        total = insights.year_totals[year]
        insights.year_over_year_change[year] = (
            pct_change(prev_total, total) if prev_total is not None else None
        )
        prev_total = total

    # Day-level insights
    if insights.all_days:
        days_by_usage = sorted(insights.all_days, key=lambda d: d.data_mb, reverse=True)
        insights.top_days = days_by_usage[:5]
        insights.quiet_days = days_by_usage[-5:][::-1]

        weekday_values = [d.data_mb for d in insights.all_days if d.weekday not in WEEKEND_DAYS]
        weekend_values = [d.data_mb for d in insights.all_days if d.weekday in WEEKEND_DAYS]
        insights.weekday_avg = safe_div(sum(weekday_values), len(weekday_values))
        insights.weekend_avg = safe_div(sum(weekend_values), len(weekend_values))
        insights.daily_avg = statistics.mean(d.data_mb for d in insights.all_days)

    return insights


def style_axes(ax: Any) -> None:
    """Apply prettier formatting to matplotlib axes."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E5E7EB")
    ax.spines["bottom"].set_color("#E5E7EB")
    ax.tick_params(axis="both", colors="#4B5563")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: f"{x/1024:.0f} GB"))


def make_yearly_trend_chart(insights: PhoneInsights, tmp_dir: str) -> str | None:
    if len(insights.years_sorted) < 2:
        return None

    fig, ax = plt.subplots(figsize=(6.5, 3))
    totals = [insights.year_totals[y] for y in insights.years_sorted]

    ax.plot(insights.years_sorted, totals, marker="o", color=CHART_COLOR, linewidth=2.5, markersize=8)
    ax.set_title("Total Data Usage by Year", color="#1F2937", fontweight="bold", pad=15)
    ax.grid(axis="y", alpha=0.4, linestyle="--")
    style_axes(ax)

    fig.tight_layout()
    path = os.path.join(tmp_dir, f"trend_{insights.number.strip('+')}.png")
    fig.savefig(path, dpi=150, transparent=True)
    plt.close(fig)
    return path


def make_monthly_chart(insights: PhoneInsights, phone: PhoneNumber, year: str, tmp_dir: str) -> str | None:
    data_year = phone.data_years[year]
    if not data_year.data_months:
        return None

    months_present = [m for m in MONTH_ORDER if m in data_year.data_months]
    totals = [data_year.data_months[m].total_data_mb for m in months_present]
    avg = insights.year_month_avg[year]

    fig, ax = plt.subplots(figsize=(6.5, 3))
    ax.bar(months_present, totals, color=CHART_COLOR, width=0.6, alpha=0.9)
    ax.axhline(avg, color=ACCENT_COLOR, linestyle="--", linewidth=2, label="Monthly average")

    ax.set_title(f"Monthly Data Usage — {year}", color="#1F2937", fontweight="bold", pad=15)
    ax.legend(loc="upper right", frameon=False, fontsize=9, labelcolor="#4B5563")
    ax.grid(axis="y", alpha=0.4, linestyle="--")
    style_axes(ax)

    fig.tight_layout()
    path = os.path.join(tmp_dir, f"monthly_{insights.number.strip('+')}_{year}.png")
    fig.savefig(path, dpi=150, transparent=True)
    plt.close(fig)
    return path


def build_styles() -> Any:
    styles = getSampleStyleSheet()

    # Decouple to Any to clear false-positive style inheritance alerts
    title_style: Any = styles["Title"]
    normal_style: Any = styles["Normal"]
    heading2_style: Any = styles["Heading2"]

    styles.add(ParagraphStyle(
        name="ReportTitle", parent=title_style, fontSize=24, spaceAfter=8,
        textColor=colors.HexColor("#111827"), fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        name="SubTitle", parent=normal_style, fontSize=12,
        textColor=colors.HexColor("#6B7280"), spaceAfter=24,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", parent=heading2_style, spaceBefore=20, spaceAfter=12,
        textColor=colors.HexColor("#1F2937"), fontName="Helvetica-Bold"
    ))
    styles.add(ParagraphStyle(
        name="TableHeader", parent=normal_style, fontSize=9, leading=12,
        textColor=colors.white, fontName="Helvetica-Bold", alignment=1 # Center
    ))
    styles.add(ParagraphStyle(
        name="TableCell", parent=normal_style, fontSize=9, leading=12,
        textColor=colors.HexColor("#374151"), alignment=1 # Center
    ))
    styles.add(ParagraphStyle(
        name="TableCellLeft", parent=normal_style, fontSize=9, leading=12,
        textColor=colors.HexColor("#374151"), alignment=0 # Left
    ))
    return styles


def table_style(header_bg: Any = colors.HexColor("#3B82F6")) -> TableStyle:
    """A clean, cell-padding-optimized table layout."""
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def build_pdf_for_phone(phone: PhoneNumber, insights: PhoneInsights, tmp_dir: str, output_dir: str) -> str:
    styles = build_styles()

    # Cast extracted styles to Any to resolve aggressive IDE type-stub warnings
    rt: Any = styles["ReportTitle"]
    st: Any = styles["SubTitle"]
    nm: Any = styles["Normal"]
    ts: Any = styles["SectionHeading"]
    th: Any = styles["TableHeader"]
    tc: Any = styles["TableCell"]
    tcl: Any = styles["TableCellLeft"]

    story: list[Any] = []

    filename = f"usage_report_{phone.number.strip('+').replace(' ', '')}.pdf"
    filepath = os.path.join(output_dir, filename)

    story.append(Paragraph("Data Usage Insight Report", rt))
    story.append(Paragraph(f"Phone number: {phone.number}", st))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#E5E7EB"), thickness=1))
    story.append(Spacer(1, 16))

    if not insights.has_data:
        story.append(Paragraph(
            "No usage data is currently recorded for this phone number.",
            nm,
        ))
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        doc.build(story)
        return filepath

    # Overview
    story.append(Paragraph("Overview", ts))
    overview_rows = [
        [Paragraph("Metric", th), Paragraph("Value", th)],
        [Paragraph("Total data usage (all time)", tcl), Paragraph(format_gb(insights.total_data_mb), tc)],
        [Paragraph("Years on record", tcl), Paragraph(", ".join(insights.years_sorted), tc)],
        [Paragraph("Average daily usage", tcl), Paragraph(format_gb(insights.daily_avg), tc)],
        [Paragraph("Average weekday usage", tcl), Paragraph(format_gb(insights.weekday_avg), tc)],
        [Paragraph("Average weekend usage", tcl), Paragraph(format_gb(insights.weekend_avg), tc)],
    ]
    overview_table = Table(overview_rows, colWidths=[3.2 * inch, 2.8 * inch])
    overview_table.setStyle(table_style(header_bg=colors.HexColor("#1F2937")))
    story.append(overview_table)

    # Weekday vs weekend note
    if insights.weekday_avg and insights.weekend_avg:
        diff_pct = pct_change(insights.weekday_avg, insights.weekend_avg)
        if diff_pct is not None:
            direction = "higher" if diff_pct > 0 else "lower"
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                f"<b>Note:</b> Weekend usage runs about <b>{abs(diff_pct):.1f}% {direction}</b> than weekday usage on average.",
                nm,
            ))

    # Yearly trend chart
    trend_chart = make_yearly_trend_chart(insights, tmp_dir)
    if trend_chart:
        trend_block: list[Any] = [
            Paragraph("Year-over-Year Trend", ts),
            Image(trend_chart, width=6.5 * inch, height=3 * inch)
        ]
        story.append(KeepTogether(trend_block))
    story.append(PageBreak())
    # Yearly breakdown table
    story.append(Paragraph("Yearly Breakdown", ts))
    headers = ["Year", "Total", "Monthly Avg", "Monthly Median", "Highest Month", "Lowest Month", "YoY Change"]
    year_rows = [[Paragraph(h, th) for h in headers]]

    for year in insights.years_sorted:
        best = insights.year_best_month.get(year)
        worst = insights.year_worst_month.get(year)
        yoy = insights.year_over_year_change.get(year)
        year_rows.append([
            Paragraph(year, tc),
            Paragraph(format_gb(insights.year_totals[year]), tc),
            Paragraph(format_gb(insights.year_month_avg[year]), tc),
            Paragraph(format_gb(insights.year_month_median[year]), tc),
            Paragraph(f"{best[0]} ({format_gb(best[1])})" if best else "-", tc),
            Paragraph(f"{worst[0]} ({format_gb(worst[1])})" if worst else "-", tc),
            Paragraph(f"{yoy:+.1f}%" if yoy is not None else "-", tc),
        ])

    year_table = Table(year_rows, colWidths=[0.6 * inch, 0.9 * inch, 1.0 * inch, 1.1 * inch, 1.2 * inch, 1.2 * inch, 0.9 * inch])
    year_table.setStyle(table_style())
    story.append(year_table)

    # Per-year monthly chart + dynamic breaks
    for year in insights.years_sorted:
        monthly_chart = make_monthly_chart(insights, phone, year, tmp_dir)
        if monthly_chart:
            year_block: list[Any] = [
                Paragraph(f"{year} — Monthly Usage", ts),
                Image(monthly_chart, width=6.5 * inch, height=3 * inch),
                Spacer(1, 15)
            ]
            story.append(KeepTogether(year_block))

    # Notable days
    if insights.top_days:
        notable_block: list[Any] = [
            Paragraph("Notable Days", ts),
            Spacer(1, 6)
        ]

        top_table = generate_rows(insights.top_days, th, tc)
        top_table.setStyle(table_style(header_bg=colors.HexColor("#EF4444")))
        notable_block.append(top_table)
        notable_block.append(Spacer(1, 20))
        story.append(KeepTogether(notable_block))

    doc = SimpleDocTemplate(
        filepath, pagesize=letter,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    doc.build(story)
    return filepath


def generate_reports(output_dir: str) -> None:
    if not phone_numbers:
        print("No phone numbers found in `phone_numbers`. Nothing to do.")
        return

    os.makedirs(output_dir, exist_ok=True)
    generated = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for number, phone in phone_numbers.items():
            insights = compute_insights(phone)
            filepath = build_pdf_for_phone(phone, insights, tmp_dir, output_dir)
            generated.append(filepath)
            print(f"Generated: {filepath}")

    print(f"\nDone. {len(generated)} report(s) written to '{output_dir}/'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate per-phone-number PDF reports of data usage.")
    parser.add_argument(
        "-o", "--output",
        default="usage_reports",
        help="Directory to save the PDF reports (defaults to 'usage_reports/')."
    )
    args = parser.parse_args()

    generate_reports(args.output)