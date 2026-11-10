from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / ".opencode" / "agents"
EXPECTED = {
    "company-orchestrator", "ceo", "coo", "cfo", "market-research",
    "lead-generation", "sales", "customer-support", "proposal",
    "software-architect", "developer", "qa-testing", "devops",
    "security-reviewer", "product-research", "product-manager",
    "saas-development", "documentation",
}


def test_company_agent_profiles_exist_and_keep_safe_defaults():
    profiles = {path.stem: path for path in AGENTS.glob("*.md")}
    assert EXPECTED <= profiles.keys()
    for name in EXPECTED:
        source = profiles[name].read_text(encoding="utf-8")
        assert source.startswith("---\\n")
        assert re.search(r"(?m)^mode: (primary|subagent)$", source)
        assert re.search(r"(?m)^edit: ask$", source)
        assert re.search(r"(?m)^bash: ask$", source)
        assert "do not call paid hosted models or APIs" in source
        assert "Human approval is mandatory" in source
