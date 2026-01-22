import re
from typing import Dict, Any, Optional


class PMORouter:
    """Rule-based issue routing with ML fallback.
    
    Rules are deterministic keyword matches; ML fallback provides confidence-scored
    predictions when no deterministic rule matches.
    """

    def __init__(self, rules: Dict[str, Dict[str, Any]], ml_classifier=None):
        self.rules = rules
        self.ml_classifier = ml_classifier

    def _match_text(self, text: str, keywords: list) -> bool:
        """Case-insensitive keyword match with word boundaries."""
        text_lower = text.lower()
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw.lower())}\b", text_lower):
                return True
        return False

    def classify_deterministic(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply deterministic rules first. Returns project + rule name + confidence if matched."""
        title = issue.get("title") or ""
        body = issue.get("body") or ""
        labels = issue.get("labels") or []
        
        text = f"{title} {body} {' '.join(labels)}"
        
        for rule_name, rule_config in self.rules.items():
            keywords = rule_config.get("match", [])
            if self._match_text(text, keywords):
                return {
                    "project": rule_config["project"],
                    "rule": rule_name,
                    "confidence": 1.0,
                    "method": "deterministic"
                }
        return None

    def classify_ml(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """ML fallback if deterministic rules do not match."""
        if not self.ml_classifier:
            return None
        # ML classifier should return {"project": str, "confidence": float}
        result = self.ml_classifier(issue)
        if result and result.get("confidence", 0) >= 0.8:
            return {
                "project": result["project"],
                "rule": "ml",
                "confidence": result["confidence"],
                "method": "ml"
            }
        return None

    def route(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Route issue to project. Returns routing decision with confidence."""
        det = self.classify_deterministic(issue)
        if det:
            return det
        
        ml = self.classify_ml(issue)
        if ml:
            return ml
        
        # No match -> send to human review queue
        return {
            "project": "pmo-human-review",
            "rule": "unmatched",
            "confidence": 0.0,
            "method": "fallback"
        }
