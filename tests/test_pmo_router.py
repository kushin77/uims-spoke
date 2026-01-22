import yaml
from src.pmo_router.router import PMORouter


def test_deterministic_routing():
    rules = {
        "infrastructure": {
            "match": ["terraform", "vpc"],
            "project": "uims-infra"
        },
        "monitoring": {
            "match": ["prometheus", "alert"],
            "project": "uims-monitoring"
        }
    }
    router = PMORouter(rules)
    
    issue = {"title": "Fix VPC subnet", "body": "terraform issue", "labels": []}
    result = router.route(issue)
    assert result["project"] == "uims-infra"
    assert result["rule"] == "infrastructure"
    assert result["confidence"] == 1.0
    assert result["method"] == "deterministic"


def test_fallback_to_human_review():
    rules = {"infra": {"match": ["terraform"], "project": "uims-infra"}}
    router = PMORouter(rules)
    
    issue = {"title": "Random issue", "body": "no keywords", "labels": []}
    result = router.route(issue)
    assert result["project"] == "pmo-human-review"
    assert result["rule"] == "unmatched"
    assert result["confidence"] == 0.0


def test_ml_fallback():
    rules = {"infra": {"match": ["terraform"], "project": "uims-infra"}}
    
    def mock_ml(issue):
        if "machine learning" in issue.get("title", "").lower():
            return {"project": "uims-ml", "confidence": 0.9}
        return {"project": None, "confidence": 0.3}
    
    router = PMORouter(rules, ml_classifier=mock_ml)
    
    issue = {"title": "Machine learning pipeline", "body": "", "labels": []}
    result = router.route(issue)
    assert result["project"] == "uims-ml"
    assert result["rule"] == "ml"
    assert result["confidence"] == 0.9


def test_load_rules_from_yaml():
    with open("src/pmo_router/rules.yaml", "r") as f:
        rules = yaml.safe_load(f)
    router = PMORouter(rules)
    
    issue = {"title": "Fix monitoring alert", "body": "prometheus query", "labels": []}
    result = router.route(issue)
    assert result["project"] == "uims-spoke-monitoring"
    assert result["method"] == "deterministic"
