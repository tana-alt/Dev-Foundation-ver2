from .base import BaseAnalyst


class ManagementEvalAnalyst(BaseAnalyst):
    role = "management_eval"
    relevant_sections = ("guidance", "segments", "risk")

    @property
    def system_prompt(self) -> str:
        return (
            "You are the management evaluation analyst. Interpret management's "
            "stated priorities, growth drivers, investment plans, and risk "
            "language. Explain the likely EPS and FCF impact over short and "
            "medium time horizons."
        )


class GuidanceAnalyst(BaseAnalyst):
    role = "guidance"
    relevant_sections = ("guidance", "revenue", "segments", "risk")

    @property
    def system_prompt(self) -> str:
        return (
            "You are the guidance analyst. Compare management guidance with "
            "market expectations when available. Evaluate whether assumptions "
            "look conservative, realistic, or optimistic, and cite evidence for "
            "both upside and downside risk."
        )
