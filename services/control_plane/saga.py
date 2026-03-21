from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Callable, Dict, List

from services.control_plane.task_protocol import TaskEnvelope


@dataclass
class StateTransition:
    task_id: str
    from_state: str
    to_state: str
    at: str
    detail: str = ""


class SagaManager:
    def __init__(self):
        self._compensations: Dict[str, Callable[[TaskEnvelope], Dict]] = {}
        self._transitions: List[StateTransition] = []

    def register_compensation(self, task_type: str, callback: Callable[[TaskEnvelope], Dict]) -> None:
        self._compensations[task_type] = callback

    def transition(self, envelope: TaskEnvelope, from_state: str, to_state: str, detail: str = "") -> None:
        self._transitions.append(
            StateTransition(
                task_id=envelope.task_id,
                from_state=from_state,
                to_state=to_state,
                at=datetime.utcnow().isoformat(),
                detail=detail,
            )
        )

    def compensate(self, envelope: TaskEnvelope) -> Dict:
        self.transition(envelope, "FAILED", "COMPENSATING", detail=f"task_type={envelope.task_type}")
        fn = self._compensations.get(envelope.task_type)
        if not fn:
            result = {"compensated": False, "reason": "no_compensation_registered"}
        else:
            result = fn(envelope)
        self.transition(envelope, "COMPENSATING", "COMPENSATED", detail=str(result))
        return result

    def get_transition_log(self) -> List[Dict]:
        return [asdict(t) for t in self._transitions]
