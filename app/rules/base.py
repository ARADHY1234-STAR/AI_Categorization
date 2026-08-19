from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional
from app.models.category import CategoryEnum


class RuleScope(str, Enum):
    GLOBAL = "GLOBAL"
    DOMAIN = "DOMAIN"
    SUBDOMAIN = "SUBDOMAIN"
    DISAMBIGUATION = "DISAMBIGUATION"


@dataclass
class Rule:
    rule_id: str
    name: str
    description: str
    scope: RuleScope
    precedence: int  # Higher number = higher precedence
    prompt_instruction: str
    category_affinity: Optional[List[CategoryEnum]] = None
    is_locked: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


class RuleRegistry:
    """Explicit, inspectable, and auditable registry of business classification rules."""

    def __init__(self):
        self._rules: Dict[str, Rule] = {}

    def register(self, rule: Rule) -> None:
        self._rules[rule.rule_id] = rule

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        return self._rules.get(rule_id)

    def list_rules(self, sorted_by_precedence: bool = True) -> List[Rule]:
        rules = list(self._rules.values())
        if sorted_by_precedence:
            rules.sort(key=lambda r: r.precedence, reverse=True)
        return rules

    def generate_prompt_rules_text(self) -> str:
        """Format all registered rules into structured prompt text for LLM injection."""
        lines = ["LOCKED BUSINESS RULES & TIE-BREAKERS:"]
        for rule in self.list_rules(sorted_by_precedence=True):
            lines.append(f"- [{rule.rule_id}] {rule.name}: {rule.prompt_instruction}")
        return "\n".join(lines)


# Global rule registry singleton
rule_registry = RuleRegistry()
