"""Family profiles for the econ_synth (finance/economics) pipeline.

The finance corpus splits into two structurally distinct families:

  A — corporate disclosure  (earnings_release, interim_report,
       quarterly_report, update_letter). Issuer = a listed company.
  B — macro flagship        (IMF Article IV / WEO / GFSR / Fiscal Monitor,
       BIS Quarterly Review, Fed MPR, ECB Economic Bulletin, World Bank GEP,
       central-bank reports). Issuer = an institution.

Each family gets its own section template, terminology, trap catalogue, and
reading hints. The profile is injected into every LLM stage's system prompt
via prompt_compose.compose(), mirroring broad_domain_synth's domain_registry.

Design note: the four *title-slide fields* are deliberately unified across
both families ("Report Title / Issuer / Reporting Period / Publication Date")
so the deterministic Stage-2 / verify static checks stay simple; the
family-specific meaning of each field is conveyed through the prompt text.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Canonical title-slide fields, identical for both families so the static
# checks in stage2_task.py / verify.py can look for a fixed marker set.
TITLE_SLIDE_FIELDS: list[str] = [
    "Report Title:",
    "Issuer:",
    "Reporting Period:",
    "Publication Date:",
]


# ---- Family A: corporate disclosure -----------------------------------------

_A_SECTION_TEMPLATE = """\
Typical ordered sections for a corporate-disclosure deck (adapt to the actual
document — omit sections the source does not support, keep the order):
1. title            — Title & Overview (issuer, fiscal period, announcement date).
2. executive_summary — headline top-line figures (revenue, operating/net income, EPS).
3. management_commentary — CEO/CFO narrative, strategic themes, quotes.
4. income_statement — revenue, expenses, margins, net income vs prior period.
5. segment_performance — per-business-segment revenue and profit breakdown.
6. balance_sheet_capital — capital position, liquidity, buybacks/dividends (as applicable).
7. cash_flow        — operating / investing / financing cash flow (if reported).
8. guidance_outlook — forward guidance / outlook (only if the document states it).
9. risk_disclosures — forward-looking-statement disclaimer & risk factors.
10. closing         — investor-relations contacts, conference-call info, resources.
"""

_A_TERMINOLOGY = [
    "revenue", "net income", "operating income", "gross margin", "operating margin",
    "EPS (diluted / basic)", "GAAP vs non-GAAP", "constant currency (CC)",
    "year-over-year (YoY)", "quarter-over-quarter / sequential (QoQ)",
    "guidance", "segment", "provision for credit losses", "free cash flow",
    "return on equity (ROE)", "CET1 ratio", "share repurchase", "dividend",
    "attributable net income", "backlog", "bookings", "ARR", "reconciliation",
]

_A_TRAP_CATALOGUE = """\
Finance trap kinds to hunt for in a corporate-disclosure document (fill traps[]
with the confusions a careless deck would make):
- gaap_vs_nongaap: reporting a non-GAAP / adjusted figure as if it were GAAP (or vice versa).
- yoy_vs_qoq: labelling a sequential (QoQ) change as year-over-year, or vice versa.
- net_vs_attributable_income: confusing total net income with net income attributable to shareholders.
- gross_vs_net_margin: reporting gross margin where net/operating margin is meant.
- constant_currency_confusion: quoting a constant-currency growth rate as the reported growth rate.
- unit_scale_error: million vs billion (or local-currency vs USD) magnitude errors.
- segment_misattribution: attributing a metric to the wrong business segment.
- guidance_vs_actual: presenting forward guidance as an actual reported result.
- period_mismatch: attaching a figure to the wrong fiscal quarter/year.
- fabrication: adding a metric, quote, or interpretation not in the source.
- scope_overclaim: overstating the scope of a result beyond what the release supports.
"""

_A_READING_HINTS = """\
Corporate disclosures are number-dense and structured. Read the income-statement
table, the segment tables, and any capital/liquidity table carefully. Capture
exact values WITH their unit (billion/million), their GAAP/non-GAAP label, and
their period (which quarter/year, YoY or sequential). Note management quotes and
their attributed speaker. Forward-looking / risk-factor language must be treated
as disclaimer text — never expand or reinterpret it.
"""

# ---- Family B: macro flagship -----------------------------------------------

_B_SECTION_TEMPLATE = """\
Typical ordered sections for a macro-flagship deck (adapt to the actual
document — omit sections the source does not support, keep the order):
1. title            — Title & Overview (institution, report series, period).
2. executive_summary — key messages / headline assessment.
3. global_outlook   — overall growth assessment and its drivers.
4. growth_forecasts — GDP growth projections by region / country / horizon.
5. inflation_forecasts — inflation projections and the policy stance.
6. regional_breakdown — per-region or per-country detail.
7. policy_analysis  — monetary / fiscal / structural policy recommendations.
8. risk_scenarios   — downside/upside risks and scenario analysis.
9. exhibits         — key charts / tables (numbered exhibits) walk-through.
10. conclusion      — synthesis, data-source notes.
"""

_B_TERMINOLOGY = [
    "real GDP growth", "nominal GDP", "headline vs core inflation", "CPI", "PCE",
    "policy rate", "basis points (bps)", "output gap", "fiscal deficit",
    "public debt-to-GDP", "current account balance", "potential output",
    "downside risk", "baseline scenario", "projection horizon", "year-over-year",
    "annualized", "percentage points (pp)", "staff projection", "advanced economies",
    "emerging market and developing economies (EMDEs)", "terms of trade",
]

_B_TRAP_CATALOGUE = """\
Finance/macro trap kinds to hunt for in a macro-flagship document (fill traps[]):
- nominal_vs_real_growth: confusing nominal growth with real (inflation-adjusted) growth.
- headline_vs_core_inflation: reporting headline inflation where core is meant, or vice versa.
- basis_points_vs_percent: confusing a basis-point move with a percentage-point move.
- forecast_vs_historical: presenting a projection/forecast as a realized historical value.
- baseline_vs_scenario: quoting a downside/alternative-scenario figure as the baseline.
- percentage_points_vs_percent: confusing a change in percentage points with a percent change.
- region_misattribution: attributing a forecast to the wrong region/country.
- horizon_mismatch: attaching a projection to the wrong year/horizon.
- unit_scale_error: level vs growth-rate, or currency/scale magnitude errors.
- fabrication: adding a projection, figure, or policy claim not in the source.
- scope_overclaim: overstating the certainty or scope of a projection.
"""

_B_READING_HINTS = """\
Macro-flagship reports are long (often 100+ pages) and forecast-heavy. Do NOT
read every page linearly. Read the executive summary / overview first, then the
projection tables (GDP, inflation) and the numbered exhibits, then sample the
regional and policy chapters. Capture each projection WITH its region/country,
its horizon (which year), whether it is real or nominal, and whether it is a
baseline or scenario value. Distinguish realized data from staff projections.
"""


_SUB_GENRE_LABELS: dict[str, str] = {
    "earnings_release": "quarterly earnings press release",
    "interim_report": "interim / half-year financial report",
    "quarterly_report": "quarterly financial report",
    "update_letter": "shareholder update / quarterly letter",
    "macro_flagship": "macroeconomic flagship report",
}


@dataclass
class FamilyProfile:
    family: str  # "A" or "B"
    sub_genre: str = ""
    issuer: str = ""
    reporting_period: str = ""

    @property
    def family_label(self) -> str:
        return (
            "Corporate disclosure (a listed company's financial report)"
            if self.family == "A"
            else "Macroeconomic flagship report (institution / central bank)"
        )

    @property
    def sub_genre_label(self) -> str:
        return _SUB_GENRE_LABELS.get(self.sub_genre, self.sub_genre or "financial document")

    @property
    def section_template(self) -> str:
        return _A_SECTION_TEMPLATE if self.family == "A" else _B_SECTION_TEMPLATE

    @property
    def terminology(self) -> list[str]:
        return _A_TERMINOLOGY if self.family == "A" else _B_TERMINOLOGY

    @property
    def trap_catalogue(self) -> str:
        return _A_TRAP_CATALOGUE if self.family == "A" else _B_TRAP_CATALOGUE

    @property
    def reading_hints(self) -> str:
        return _A_READING_HINTS if self.family == "A" else _B_READING_HINTS

    @property
    def title_slide_fields(self) -> list[str]:
        return list(TITLE_SLIDE_FIELDS)

    def context_text(self) -> str:
        """Render the Domain Context block appended to each stage's base prompt.

        Deliberately contains NO per-case fields (issuer, period): the composed
        system prompt is identical for every case of the same family/sub_genre,
        so the Anthropic prompt cache can reuse the prefix across cases. Per-case
        identity lives in ./_case_meta.json instead.
        """
        fields = "\n".join(f"- `{f}`" for f in self.title_slide_fields)
        terms = ", ".join(self.terminology)
        return f"""\
---

## Domain Context (auto-injected by the pipeline)

**Domain:** Economics / Finance
**Document family:** {self.family} — {self.family_label}
**Sub-genre:** {self.sub_genre} — {self.sub_genre_label}
(Per-case issuer / reporting period: read them from ./_case_meta.json.)

### Reading approach for this document type
{self.reading_hints}

### Suggested ordered-section template (Stage 1 / Stage 2)
{self.section_template}

### Domain terminology reference
{terms}

### Title-slide fields (Stage 2 must include these exact markers)
{fields}

For Family A the Issuer is the company and the Reporting Period is the fiscal
quarter/year; for Family B the Issuer is the institution and the Reporting
Period is the report edition/date. Use the field markers above verbatim.

### Finance trap catalogue (Stage 1 traps[], Stage 3 correctness coverage)
{self.trap_catalogue}
"""


def load_for_doc(family: str, sub_genre: str = "", issuer: str = "",
                 reporting_period: str = "") -> FamilyProfile:
    fam = (family or "A").strip().upper()
    if fam not in ("A", "B"):
        fam = "A"
    return FamilyProfile(
        family=fam,
        sub_genre=sub_genre or "",
        issuer=issuer or "",
        reporting_period=reporting_period or "",
    )
