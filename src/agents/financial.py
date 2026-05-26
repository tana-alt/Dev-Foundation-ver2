from .base import BaseAnalyst


class EPSAnalyst(BaseAnalyst):
    role = "eps_analyst"
    relevant_sections = ("eps", "revenue", "guidance")

    @property
    def system_prompt(self) -> str:
        return (
            "You are the EPS analyst. Decide whether EPS beat or missed "
            "consensus and whether the variance appears durable or temporary. "
            "Focus on consensus delta, margin, tax, one-time items, and share "
            "count. Do not make trading recommendations."
        )


class PLAnalyst(BaseAnalyst):
    role = "pnl_analyst"
    relevant_sections = ("revenue", "segments", "eps")

    @property
    def system_prompt(self) -> str:
        return (
            "You are the P&L analyst. Review revenue, operating margin, mix, "
            "segment performance, and cost structure. Explain what changed and "
            "whether it supports future EPS. Do not calculate new metrics; use "
            "the precomputed data and cited source text."
        )


class CFSAnalyst(BaseAnalyst):
    role = "cfs_analyst"
    relevant_sections = ("revenue", "guidance", "risk", "other")

    @property
    def system_prompt(self) -> str:
        return (
            "You are the cash-flow statement analyst. Focus on operating cash "
            "flow, free cash flow, CapEx, working capital, and whether current "
            "investment is likely to pressure or improve future FCF. State when "
            "the available source text is insufficient."
        )


class BSAnalyst(BaseAnalyst):
    role = "bs_analyst"
    relevant_sections = ("risk", "other")

    @property
    def system_prompt(self) -> str:
        return (
            "You are the balance-sheet analyst. Review liquidity, debt, leverage, "
            "inventory, receivables, and any balance-sheet item that affects the "
            "quality of EPS or FCF. Be concise and evidence-based."
        )
