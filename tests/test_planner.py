import json
from pathlib import Path
from src.planner import generate, validate

def test_starter_generation_is_referentially_valid(tmp_path):
    cfg=json.loads(Path("config.json").read_text())
    cfg["scale"]="starter"
    cfg["inject_anomalies"]=False
    tables=generate(cfg,tmp_path)
    assert len(tables["programs"])==10
    assert len(tables["courses"])==100
    assert len(tables["faculty"])==50
    assert len(tables["student_plans"])==2000
    assert validate(tables)==[]

def test_deterministic_ids(tmp_path):
    cfg=json.loads(Path("config.json").read_text())
    a=generate(cfg,tmp_path/"a")
    b=generate(cfg,tmp_path/"b")
    assert a["programs"].program_id.tolist()==b["programs"].program_id.tolist()
    assert a["courses"].course_id.tolist()==b["courses"].course_id.tolist()
