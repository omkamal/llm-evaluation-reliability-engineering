"""The review desk: a packet, a queue, and approve, edit or reject."""
import heapq
from dataclasses import dataclass

from pydantic import BaseModel, Field

from ch02_trust_outputs.refund import ToolError, validate_refund_args
from ch18_governance.routing import (REVIEW_COST_CENTS,
                                     expected_loss_cents, triggers)


class Packet(BaseModel, extra="forbid"):
    """What a reviewer needs, so that nobody has to dig."""
    case_id: str
    summary: str = Field(max_length=120)       # one line: what and why
    proposed: dict                             # tool and exact arguments
    evidence: list[str] = Field(min_length=1)  # owner, order, policy hit
    risk: str                                  # the expected-loss line
    triggers: list[str] = Field(min_length=1)  # why a person was asked
    trace: str                                 # link to the full trace
    due: float                                 # when the SLA runs out


def build_packet(case, due):
    loss = expected_loss_cents(case.p_error,
                               case.args.get("amount_cents", 0))
    return Packet(
        case_id=case.case_id, summary=case.summary,
        proposed={"tool": case.tool, "args": case.args},
        evidence=case.evidence,
        risk=f"expected loss ${loss / 100:.2f}, "
             f"review ${REVIEW_COST_CENTS / 100:.2f}",
        triggers=triggers(case), trace=case.trace, due=due)


@dataclass
class Item:
    id: int
    reason: str
    packet: Packet
    priority: int
    queued_at: float
    customer: str            # from the session; the model never sets it


@dataclass
class Outcome:
    item: Item
    reviewer: str
    decision: str            # approve | edit | reject
    waited: float            # seconds from queued to decided
    final_cents: int         # 0 when rejected

    def label(self):
        """A free expert label: approve is a pass, the rest a fail."""
        return {"case": self.item.packet.case_id,
                "label": "pass" if self.decision == "approve" else "fail",
                "proposed": self.item.packet.proposed["args"],
                "final_cents": self.final_cents}


class InvalidProposal(Exception):
    pass


class ReviewDesk:
    def __init__(self, clock, broker, door, log, orders, sla=900):
        self.clock, self.broker, self.door = clock, broker, door
        self.log, self.orders, self.sla = log, orders, sla
        self.heap, self.count, self.outcomes = [], 0, []

    def escalate_to_human(self, reason, context_packet, customer,
                          priority=1):
        """The tool Relay calls: park the case and its packet. The
        runtime adds `customer` from the session."""
        self.count += 1
        item = Item(self.count, reason, context_packet, priority,
                    self.clock.now(), customer)
        heapq.heappush(self.heap, (priority, context_packet.due,
                                   item.id, item))
        return item

    def next(self):
        """Most urgent first, then the earliest deadline."""
        return heapq.heappop(self.heap)[-1]

    def decide(self, item, reviewer, decision, edited_cents=None):
        packet = item.packet
        case, tool = packet.case_id, packet.proposed["tool"]
        args = dict(packet.proposed["args"])
        final = 0
        if decision != "reject":
            if decision == "edit":
                if not 0 < edited_cents <= args["amount_cents"]:
                    raise ValueError("an edit may only lower the amount")
                args["amount_cents"] = edited_cents
            customer = item.customer
            checked = validate_refund_args(args, customer, self.orders)
            if isinstance(checked, ToolError):
                raise InvalidProposal(checked.code)
            token = self.broker.issue(
                "actioner", tool, case, customer,
                max_cents=args["amount_cents"], approver=reviewer)
            self.door.call(token, tool, args, customer, packet.trace)
            final = args["amount_cents"]
        self.log.record(
            agent=reviewer, version="-", tool="review",
            args={"order_id": args["order_id"], "case": case,
                  "proposed": packet.proposed["args"]["amount_cents"],
                  "final": final},
            decision=decision, approver=reviewer,
            trace=packet.trace, task=case)
        outcome = Outcome(item, reviewer, decision,
                          self.clock.now() - item.queued_at, final)
        self.outcomes.append(outcome)
        return outcome


def packet_lines(packet):
    """The packet as the reviewer sees it: nothing to dig for."""
    call = packet.proposed
    values = ", ".join(str(v) for v in call["args"].values())
    return ([f"case {packet.case_id} [{', '.join(packet.triggers)}]",
             f"  {packet.summary}",
             f"  propose: {call['tool']}({values})"]
            + [f"  evidence: {line}" for line in packet.evidence]
            + [f"  risk: {packet.risk}", f"  trace: {packet.trace[:8]}"])
