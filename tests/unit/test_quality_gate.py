"""
Testes unitários para o Portão Automático de Qualidade e Segurança (scripts/quality_gate.py).
Garante que todas as regras SAST, SCA, Complexidade Cognitiva, Zero Duplicidade e Docker Hardening
detectem violações corretamente e aprovem código limpo.
"""

import ast
from pathlib import Path

from scripts.quality_gate import (
    calculate_cognitive_complexity,
    check_changed_functions_complexity,
    check_dependency_integrity,
    check_dockerfiles_hardening,
    compute_duplication_density,
    is_allowed_ipv4,
    run_quality_gate,
    scan_python_ast_rules,
)


def test_is_allowed_ipv4():
    assert is_allowed_ipv4("127.0.0.1") is True
    assert is_allowed_ipv4("0.0.0.0") is True
    assert is_allowed_ipv4("192.0.2.15") is True
    assert is_allowed_ipv4("198.51.100.42") is True
    assert is_allowed_ipv4("203.0.113.99") is True
    assert is_allowed_ipv4("999.999.999.999") is True
    assert is_allowed_ipv4("10.20.30.40") is False
    assert is_allowed_ipv4("172.16.0.10") is False


def test_calculate_cognitive_complexity():
    simple_code = """
def simple(a, b):
    if a and b:
        return 1
    return 0
"""
    simple_tree = ast.parse(simple_code)
    assert calculate_cognitive_complexity(simple_tree.body[0]) == 2

    complex_code = """
def very_nested(items):
    total = 0
    for item in items:
        if item > 0:
            for sub in range(item):
                if sub % 2 == 0 and sub > 1:
                    try:
                        total += sub
                    except ValueError:
                        total -= 1
                elif sub == 1:
                    total += 2
                else:
                    total += 0
    return total
"""
    complex_tree = ast.parse(complex_code)
    assert calculate_cognitive_complexity(complex_tree.body[0]) > 15


def test_scan_python_ast_rules_detects_all_sast_and_reliability_issues(tmp_path: Path):
    bad_file = tmp_path / "bad_module.py"
    bad_file.write_text(
        '''"""Docstring com IP ignorado 10.99.88.77."""
import time
import requests

def bad_mutable(items=[]):
    return items

async def bad_async_io():
    time.sleep(1)
    requests.get("https://example.com")

def bad_exceptions():
    try:
        pass
    except:
        pass
    try:
        pass
    except BaseException:
        pass

def bad_sql_and_ip(db, user_id):
    target_ip = "10.15.20.25"
    db.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return target_ip
''',
        encoding="utf-8",
    )

    violations = scan_python_ast_rules(str(tmp_path))
    rule_ids = [v.rule_id for v in violations]

    assert "B006" in rule_ids
    assert rule_ids.count("S7483") == 2
    assert rule_ids.count("S5754") == 2
    assert "S3649" in rule_ids
    assert "S1313" in rule_ids
    # Garante que o IP da docstring (10.99.88.77) foi ignorado e apenas 10.15.20.25 foi reportado
    ip_violations = [v for v in violations if v.rule_id == "S1313"]
    assert len(ip_violations) == 1
    assert "10.15.20.25" in ip_violations[0].message


def test_compute_duplication_density_detects_clones(tmp_path: Path):
    lines = "\n".join(f"x_{i} = {i} * 2" for i in range(20))
    (tmp_path / "a.py").write_text(lines, encoding="utf-8")
    (tmp_path / "b.py").write_text(lines, encoding="utf-8")

    density, dup_lines, total_lines = compute_duplication_density([str(tmp_path)], window=15)
    assert total_lines == 40
    assert dup_lines == 40
    assert density == 100.0


def test_check_changed_functions_complexity(tmp_path: Path):
    target = tmp_path / "complex_mod.py"
    target.write_text(
        """
def over_limit(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                while i > 0:
                    if i == 4 and x == 10 or x == 20:
                        i -= 1
                    else:
                        i -= 2
    return x
""",
        encoding="utf-8",
    )
    violations = check_changed_functions_complexity(
        changed_files_map={str(target): {2, 3, 4}},
        max_complexity=15,
    )
    assert len(violations) == 1
    assert violations[0].rule_id == "S3776"


def test_check_dockerfiles_hardening(tmp_path: Path):
    insecure_df = tmp_path / "Dockerfile"
    insecure_df.write_text(
        """FROM python:3.13-slim
RUN flutter upgrade
USER root
""",
        encoding="utf-8",
    )
    violations = check_dockerfiles_hardening([str(insecure_df)])
    rule_ids = {v.rule_id for v in violations}
    assert "S6470" in rule_ids
    assert "S6596" in rule_ids


def test_check_dependency_integrity_and_full_repository_gate():
    assert check_dependency_integrity() == []
    assert run_quality_gate() == 0
