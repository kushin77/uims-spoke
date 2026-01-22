import yaml
import re
from typing import Dict, Any

with open("src/pmo_router/rules.yaml", "r") as f:
    RULES = yaml.safe_load(f)


def rule_classify(issue: Dict[str, Any]):
    title = (issue.get("title") or "").lower()
    body = (issue.get("body") or "").lower()
    text = f"{title} {body}"
    for name, rule in RULES.items():
        for kw in rule.get("match", []):
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return {"project": rule["project"], "rule": name, "confidence": 0.99}
    return {"project": None, "rule": None, "confidence": 0.0}


# ML fallback stub (returns low confidence)
def ml_classify(issue: Dict[str, Any]):
    # Placeholder for ML model inference
    return {"project": None, "confidence": 0.5}


def classify_issue(issue: Dict[str, Any]):
    r = rule_classify(issue)
    if r["project"]:
        return r
    m = ml_classify(issue)
    if m["confidence"] >= 0.8:
        return {
            "project": m.get("project"),
            "rule": "ml",
            "confidence": m["confidence"],
        }
    return {
        "project": "pmo-human-review",
        "rule": "uncertain",
        "confidence": m["confidence"],
    }


if __name__ == "__main__":
    sample = {
        "title": "Fix VPC subnet creation in Terraform",
        "body": "vpc and subnet issue on prod",
    }
    print(classify_issue(sample))
