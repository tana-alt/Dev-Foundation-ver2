from .base import BaseAnalyst


class MacroAnalyst(BaseAnalyst):
    role = "macro"
    relevant_sections = ("revenue", "guidance", "risk", "segments")

    @property
    def system_prompt(self) -> str:
        return (
            "You are a MACRO / industry-context analyst. Your job: place this "
            "print in its industry and macro setting. Focus on: how consensus "
            "was positioned going in (high bar vs low bar), peer reads from "
            "the same quarter, end-market demand signals, FX exposure, rate/"
            "credit sensitivity, sector rotation context. An EPS beat against "
            "an already-lowered bar is weaker than a beat against a stretched "
            "bar — name that explicitly."
        )
