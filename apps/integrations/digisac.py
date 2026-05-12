"""
Digisac integration — fetches tickets, service summaries and ratings.

Digisac REST API docs: https://docs.digisac.com.br/
Authentication: Bearer token via DIGISAC_TOKEN env var.

Collected data shape:
{
    "total_tickets": int,
    "open_tickets": int,
    "closed_tickets": int,
    "avg_first_response_minutes": float,
    "avg_resolution_minutes": float,
    "ratings": {
        "total": int,
        "average_score": float,   # 1-5
        "distribution": {1: int, 2: int, 3: int, 4: int, 5: int}
    },
    "tickets_by_day": [{"date": "YYYY-MM-DD", "count": int}, ...],
    "tickets_by_category": [{"category": str, "count": int}, ...],
    "top_agents": [{"name": str, "tickets": int, "avg_score": float}, ...],
    "ticket_samples": [{"id": str, "subject": str, "status": str, "score": int|None}, ...]
}
"""
import logging
from datetime import date

from django.conf import settings

from .base import BaseAPIClient

logger = logging.getLogger(__name__)


class DigisacClient(BaseAPIClient):
    def __init__(self):
        self.base_url = settings.DIGISAC_BASE_URL
        self.token = settings.DIGISAC_TOKEN

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _get_tickets(self, department_id: str, start: date, end: date) -> list[dict]:
        params = {
            "departmentId": department_id,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "limit": 1000,
        }
        data = self._get("/tickets", params=params, headers=self._headers)
        return data.get("data", data) if isinstance(data, dict) else data

    def _get_ratings(self, department_id: str, start: date, end: date) -> list[dict]:
        params = {
            "departmentId": department_id,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "limit": 1000,
        }
        data = self._get("/ratings", params=params, headers=self._headers)
        return data.get("data", data) if isinstance(data, dict) else data

    def collect(self, external_id: str, start: date, end: date, extra: dict = None) -> dict:
        extra = extra or {}
        department_id = extra.get("department_id", external_id)

        tickets = self._get_tickets(department_id, start, end)
        ratings = self._get_ratings(department_id, start, end)

        return self._process(tickets, ratings)

    def _process(self, tickets: list, ratings: list) -> dict:
        from collections import defaultdict

        open_count = sum(1 for t in tickets if t.get("status") in ("open", "aberto"))
        closed_count = sum(1 for t in tickets if t.get("status") in ("closed", "fechado", "resolved"))

        # Avg response / resolution times (in minutes)
        first_responses = [
            t.get("firstResponseMinutes") or t.get("first_response_minutes", 0)
            for t in tickets if t.get("firstResponseMinutes") or t.get("first_response_minutes")
        ]
        resolutions = [
            t.get("resolutionMinutes") or t.get("resolution_minutes", 0)
            for t in tickets if t.get("resolutionMinutes") or t.get("resolution_minutes")
        ]

        avg_first = round(sum(first_responses) / len(first_responses), 1) if first_responses else 0
        avg_res = round(sum(resolutions) / len(resolutions), 1) if resolutions else 0

        # Ratings
        scores = [r.get("score") or r.get("rating", 0) for r in ratings if r.get("score") or r.get("rating")]
        distribution = defaultdict(int)
        for s in scores:
            distribution[int(s)] += 1
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

        # Tickets by day
        by_day = defaultdict(int)
        for t in tickets:
            day = (t.get("createdAt") or t.get("created_at", ""))[:10]
            if day:
                by_day[day] += 1
        tickets_by_day = [{"date": d, "count": c} for d, c in sorted(by_day.items())]

        # Tickets by category
        by_cat = defaultdict(int)
        for t in tickets:
            cat = t.get("category") or t.get("type") or "Sem categoria"
            by_cat[cat] += 1
        tickets_by_category = [
            {"category": c, "count": n}
            for c, n in sorted(by_cat.items(), key=lambda x: -x[1])
        ]

        # Top agents
        agent_tickets = defaultdict(list)
        agent_ratings = defaultdict(list)
        for t in tickets:
            agent = t.get("agentName") or t.get("agent", {}).get("name", "Sem agente")
            agent_tickets[agent].append(t)
        for r in ratings:
            agent = r.get("agentName") or r.get("agent", {}).get("name", "Sem agente")
            score = r.get("score") or r.get("rating", 0)
            if score:
                agent_ratings[agent].append(score)

        top_agents = []
        for agent, tks in agent_tickets.items():
            ag_scores = agent_ratings.get(agent, [])
            top_agents.append({
                "name": agent,
                "tickets": len(tks),
                "avg_score": round(sum(ag_scores) / len(ag_scores), 2) if ag_scores else None,
            })
        top_agents.sort(key=lambda x: -x["tickets"])

        # Sample tickets (last 10 closed)
        closed_tickets = [t for t in tickets if t.get("status") in ("closed", "fechado", "resolved")]
        ticket_samples = [
            {
                "id": str(t.get("id") or t.get("ticketId", "")),
                "subject": t.get("subject") or t.get("title", "—"),
                "status": t.get("status", "—"),
                "score": None,
            }
            for t in closed_tickets[:10]
        ]
        # Attach scores to samples
        ratings_by_ticket = {str(r.get("ticketId") or r.get("ticket_id", "")): r for r in ratings}
        for sample in ticket_samples:
            r = ratings_by_ticket.get(sample["id"])
            if r:
                sample["score"] = r.get("score") or r.get("rating")

        return {
            "total_tickets": len(tickets),
            "open_tickets": open_count,
            "closed_tickets": closed_count,
            "avg_first_response_minutes": avg_first,
            "avg_resolution_minutes": avg_res,
            "ratings": {
                "total": len(scores),
                "average_score": avg_score,
                "distribution": dict(distribution),
            },
            "tickets_by_day": tickets_by_day,
            "tickets_by_category": tickets_by_category,
            "top_agents": top_agents,
            "ticket_samples": ticket_samples,
        }
