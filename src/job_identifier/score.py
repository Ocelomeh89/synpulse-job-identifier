from __future__ import annotations
from dataclasses import replace
from datetime import date, datetime

from job_identifier.models import (
    Posting, RunConfig, ScoreWeights, Seniority,
)


_SENIORITY_SCORE = {
    Seniority.IC: 0.20,
    Seniority.SENIOR_IC: 0.40,
    Seniority.LEAD: 0.60,
    Seniority.DIRECTOR: 0.85,
    Seniority.VP_PLUS: 1.00,
}


def recency_score(posted_date: date, now: datetime, window_days: int) -> float:
    days = (now.date() - posted_date).days
    if days >= window_days:
        return 0.0
    if days < 0:
        return 1.0
    return 1.0 - (days / window_days)


def seniority_score(s: Seniority) -> float:
    return _SENIORITY_SCORE[s]


def combined(recency: float, seniority: float, weights: ScoreWeights) -> float:
    return weights.recency * recency + weights.seniority * seniority


def apply(postings: list[Posting], cfg: RunConfig, now: datetime) -> list[Posting]:
    out: list[Posting] = []
    for p in postings:
        r = recency_score(p.posted_date, now, cfg.recency_window_days)
        s = seniority_score(p.seniority)
        c = combined(r, s, cfg.score_weights)
        out.append(replace(p, recency_score=r, seniority_score=s, score=c))
    return out
