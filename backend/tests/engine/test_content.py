from pathlib import Path

import pytest

from app.engine.content import ConditionSpec, ContentDefinition, evaluate_condition, load_content
from app.models.enums import Strategy


def test_official_content_loads_and_conditions_evaluate():
    content = load_content()
    assert "GRAY_BLOOD" in content["events"]
    assert set(content["strategies"]) == {item.value for item in Strategy}
    values = {"species.population": 10, "species.status": "WILD"}
    assert evaluate_condition(ConditionSpec(field="species.population", op="gte", value=10), values)
    assert evaluate_condition(ConditionSpec.model_validate({"all": [
        {"field": "species.population", "op": "gt", "value": 1},
        {"not": {"field": "species.status", "op": "eq", "value": "ACTIVE"}},
    ]}), values)


def test_invalid_content_and_duplicate_ids_fail(tmp_path: Path):
    events = tmp_path / "events"; events.mkdir()
    (tmp_path / "actions").mkdir(); (tmp_path / "strategies").mkdir()
    definition = "id: duplicate\nscope: SPECIES\nname: D\ndescription: D\nrarity: COMMON\nchance: 0.1\ntrigger: {field: species.population, op: gt, value: 0}\n"
    (events / "a.yaml").write_text(definition)
    (events / "b.yaml").write_text(definition)
    with pytest.raises(ValueError, match="duplicate content id"):
        load_content(tmp_path)


def test_unknown_condition_and_effect_are_rejected():
    with pytest.raises(ValueError):
        ConditionSpec(field="unsafe.value", op="eq", value=1)
    with pytest.raises(ValueError):
        ContentDefinition(id="bad", effects=[{"type": "execute", "target": "world"}])


@pytest.mark.parametrize("op,expected", [("eq", 3), ("neq", 4), ("gt", 2), ("gte", 3), ("lt", 4), ("lte", 3), ("in", [1, 3])])
def test_condition_operator_dispatch(op, expected):
    assert evaluate_condition(ConditionSpec(field="species.population", op=op, value=expected), {"species.population": 3})


def test_invalid_in_operand_and_full_unknown_field():
    with pytest.raises(ValueError):
        ConditionSpec(field="species.foo", op="eq", value=1)
    with pytest.raises(ValueError):
        ConditionSpec(field="species.population", op="in", value=123)
