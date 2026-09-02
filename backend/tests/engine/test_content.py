from pathlib import Path

import pytest

from app.engine.content import ConditionSpec, ContentDefinition, evaluate_condition, load_content


def test_official_content_loads_and_conditions_evaluate():
    content = load_content()
    assert "gray_blood" in content["events"]
    values = {"species.population": 10, "species.status": "WILD"}
    assert evaluate_condition(ConditionSpec(field="species.population", op="gte", value=10), values)
    assert evaluate_condition(ConditionSpec.model_validate({"all": [
        {"field": "species.population", "op": "gt", "value": 1},
        {"not": {"field": "species.status", "op": "eq", "value": "ACTIVE"}},
    ]}), values)


def test_invalid_content_and_duplicate_ids_fail(tmp_path: Path):
    events = tmp_path / "events"; events.mkdir()
    (tmp_path / "actions").mkdir(); (tmp_path / "strategies").mkdir()
    (events / "a.yaml").write_text("id: duplicate\n")
    (events / "b.yaml").write_text("id: duplicate\n")
    with pytest.raises(ValueError, match="duplicate content id"):
        load_content([tmp_path])


def test_unknown_condition_and_effect_are_rejected():
    with pytest.raises(ValueError):
        ConditionSpec(field="unsafe.value", op="eq", value=1)
    with pytest.raises(ValueError):
        ContentDefinition(id="bad", effects=[{"type": "execute", "target": "world"}])
