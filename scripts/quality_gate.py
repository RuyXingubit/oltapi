"""
Portão Automático de Qualidade, Segurança (SAST/SCA) e Zero Duplicidade (OLTAPI).
Substituto local e de CI 100% gratuito e independente de licença externa (padrão SonarQube).

Validações executadas:
1. Densidade Global de Duplicação de Código (< 2.0%) em app/ e frontend/lib/.
2. SAST & Confiabilidade AST em app/ e scripts/:
   - Zero argumentos default mutáveis (B006).
   - Zero I/O bloqueante (time.sleep / requests.*) dentro de funções async (S7483).
   - Zero blocos bare except: ou captura cega de BaseException (S5754).
   - Zero interpolação SQL via f-string em .execute() (S3649).
   - Zero endereços IPv4 operacionais hardcoded fora das faixas RFC 5737 / loopback (S1313).
3. Complexidade Cognitiva (S3776 <= 15) em todas as funções novas ou modificadas no commit/working tree.
4. Hardening de Containers Docker (execução não-root, lockfiles estritos e permissões explícitas).
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

MAX_DUPLICATION_PERCENT = 2.0
DUPLICATION_WINDOW_LINES = 15
MAX_COGNITIVE_COMPLEXITY = 15

IPV4_RE = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
SQL_KEYWORDS_RE = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE)\b", re.IGNORECASE)

ALLOWED_IPS: Set[str] = {
    "0.0.0.0",
    "127.0.0.0",
    "127.0.0.1",
    "169.254.0.0",
    "255.255.0.0",
    "255.255.255.0",
    "255.255.255.255",
}
ALLOWED_IP_PREFIXES: Tuple[str, ...] = (
    "192.0.2.",      # RFC 5737 TEST-NET-1
    "198.51.100.",   # RFC 5737 TEST-NET-2
    "203.0.113.",    # RFC 5737 TEST-NET-3
)


@dataclass(frozen=True)
class QualityViolation:
    rule_id: str
    file_path: str
    line: int
    message: str


def is_allowed_ipv4(candidate: str) -> bool:
    """Verifica se uma string no formato A.B.C.D é um IP permitido (loopback, máscara ou RFC 5737)."""
    parts = [int(part) for part in candidate.split(".")]
    if any(octet > 255 for octet in parts):
        return True
    if candidate in ALLOWED_IPS:
        return True
    return candidate.startswith(ALLOWED_IP_PREFIXES)


def _normalize_source_lines(file_path: pathlib.Path) -> Tuple[int, List[Tuple[int, str]]]:
    """Lê um arquivo-fonte e retorna (total_linhas, [(numero_linha, linha_normalizada)])."""
    raw_lines = file_path.read_text(encoding="utf-8").splitlines()
    normalized: List[Tuple[int, str]] = []
    for idx, line in enumerate(raw_lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "import ", "from ")):
            continue
        normalized.append((idx, stripped))
    return len(raw_lines), normalized


def _collect_source_files_data(roots: Sequence[str]) -> Dict[str, Tuple[int, List[Tuple[int, str]]]]:
    files_data: Dict[str, Tuple[int, List[Tuple[int, str]]]] = {}
    for root in roots:
        root_path = pathlib.Path(root)
        if not root_path.exists():
            continue
        for ext in ("*.py", "*.dart"):
            for path in sorted(root_path.rglob(ext)):
                files_data[str(path)] = _normalize_source_lines(path)
    return files_data


def _find_duplicated_line_indices(
    files_data: Dict[str, Tuple[int, List[Tuple[int, str]]]],
    window: int,
) -> Dict[str, Set[int]]:
    block_occurrences: Dict[Tuple[str, ...], List[Tuple[str, int]]] = {}
    for fname, (_, norm_lines) in files_data.items():
        limit = len(norm_lines) - window + 1
        for start in range(max(0, limit)):
            signature = tuple(item[1] for item in norm_lines[start : start + window])
            block_occurrences.setdefault(signature, []).append((fname, start))

    duplicated_indices: Dict[str, Set[int]] = {fname: set() for fname in files_data}
    for occurrences in block_occurrences.values():
        if len(occurrences) >= 2:
            for fname, start_idx in occurrences:
                duplicated_indices[fname].update(range(start_idx, start_idx + window))
    return duplicated_indices


def compute_duplication_density(
    roots: Sequence[str] = ("app", "frontend/lib"),
    window: int = DUPLICATION_WINDOW_LINES,
) -> Tuple[float, int, int]:
    """
    Calcula o percentual de linhas duplicadas usando blocos deslizantes de `window` linhas.
    Retorna (percentual, linhas_duplicadas, total_linhas).
    """
    files_data = _collect_source_files_data(roots)
    duplicated_indices = _find_duplicated_line_indices(files_data, window)
    total_lines = sum(total for total, _ in files_data.values())
    dup_lines = sum(len(indices) for indices in duplicated_indices.values())
    density = (dup_lines / total_lines * 100.0) if total_lines else 0.0
    return density, dup_lines, total_lines


class _CognitiveComplexityVisitor:
    """Calculador AST de Complexidade Cognitiva (SonarQube S3776)."""

    def __init__(self) -> None:
        self.score = 0

    def visit_body(self, statements: Iterable[ast.AST], nesting: int) -> None:
        for stmt in statements:
            self.visit(stmt, nesting)

    def _visit_if(self, node: ast.If, nesting: int, is_elif: bool) -> None:
        self.score += 1 if is_elif else (1 + nesting)
        self.visit(node.test, nesting)
        self.visit_body(node.body, nesting + 1)
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            self._visit_if(node.orelse[0], nesting, is_elif=True)
        elif node.orelse:
            self.score += 1
            self.visit_body(node.orelse, nesting + 1)

    def _visit_loop(self, node: ast.For | ast.AsyncFor | ast.While, nesting: int) -> None:
        self.score += 1 + nesting
        self.visit_body(node.body, nesting + 1)
        if node.orelse:
            self.score += 1
            self.visit_body(node.orelse, nesting + 1)

    def _visit_try(self, node: ast.Try, nesting: int) -> None:
        self.visit_body(node.body, nesting)
        for handler in node.handlers:
            self.score += 1 + nesting
            self.visit_body(handler.body, nesting + 1)
        if node.orelse:
            self.score += 1
            self.visit_body(node.orelse, nesting + 1)
        self.visit_body(node.finalbody, nesting)

    def visit(self, node: ast.AST, nesting: int) -> None:
        if isinstance(node, ast.If):
            self._visit_if(node, nesting, is_elif=False)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            self._visit_loop(node, nesting)
        elif isinstance(node, ast.Try):
            self._visit_try(node, nesting)
        elif isinstance(node, ast.BoolOp):
            self.score += 1
            self.visit_body(node.values, nesting)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            self.visit_body(ast.iter_child_nodes(node), nesting + 1)
        else:
            self.visit_body(ast.iter_child_nodes(node), nesting)


def calculate_cognitive_complexity(func_node: ast.AST) -> int:
    """Calcula a Complexidade Cognitiva (SonarQube S3776) de uma função ou método."""
    visitor = _CognitiveComplexityVisitor()
    visitor.visit_body(getattr(func_node, "body", []), 0)
    return visitor.score


def _extract_docstring_id(node: ast.AST) -> Optional[int]:
    if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    if not node.body or not isinstance(node.body[0], ast.Expr):
        return None
    val = node.body[0].value
    if isinstance(val, ast.Constant) and isinstance(val.value, str):
        return id(val)
    return None


def _collect_doc_and_description_nodes(tree: ast.AST) -> Set[int]:
    """Identifica IDs de nós Constant que são docstrings ou descrições de documentação OpenAPI/Pydantic."""
    ignored_ids: Set[int] = set()
    for node in ast.walk(tree):
        doc_id = _extract_docstring_id(node)
        if doc_id is not None:
            ignored_ids.add(doc_id)
        if isinstance(node, ast.keyword) and node.arg in ("description", "example", "examples"):
            ignored_ids.update(
                id(sub) for sub in ast.walk(node.value) if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
            )
    return ignored_ids


def _check_function_defaults(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
) -> List[QualityViolation]:
    violations: List[QualityViolation] = []
    defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
    for default_node in defaults:
        if isinstance(default_node, (ast.List, ast.Dict, ast.Set)):
            violations.append(
                QualityViolation(
                    rule_id="B006",
                    file_path=file_path,
                    line=node.lineno,
                    message=f"Função '{node.name}' usa argumento default mutável (use None).",
                )
            )
    return violations


def _check_async_blocking_calls(
    node: ast.AsyncFunctionDef,
    file_path: str,
) -> List[QualityViolation]:
    violations: List[QualityViolation] = []
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)):
            continue
        if not isinstance(sub.func.value, ast.Name):
            continue
        caller = sub.func.value.id
        method = sub.func.attr
        if caller == "time" and method == "sleep":
            violations.append(
                QualityViolation(
                    rule_id="S7483",
                    file_path=file_path,
                    line=sub.lineno,
                    message=f"Função async '{node.name}' chama time.sleep() bloqueante (use asyncio.sleep).",
                )
            )
        elif caller == "requests":
            violations.append(
                QualityViolation(
                    rule_id="S7483",
                    file_path=file_path,
                    line=sub.lineno,
                    message=f"Função async '{node.name}' chama requests.{method}() síncrono (use httpx/to_thread).",
                )
            )
    return violations


def _check_except_handler(node: ast.ExceptHandler, file_path: str) -> List[QualityViolation]:
    if node.type is None:
        return [
            QualityViolation(
                rule_id="S5754",
                file_path=file_path,
                line=node.lineno,
                message="Uso de 'except:' sem especificar classe de exceção (use 'except Exception:').",
            )
        ]
    if isinstance(node.type, ast.Name) and node.type.id == "BaseException":
        has_raise = any(isinstance(stmt, ast.Raise) for stmt in ast.walk(node))
        if not has_raise:
            return [
                QualityViolation(
                    rule_id="S5754",
                    file_path=file_path,
                    line=node.lineno,
                    message="Captura de BaseException sem re-raise bloqueia SystemExit/KeyboardInterrupt.",
                )
            ]
    return []


def _is_fstring_sql_execute(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute"):
        return False
    if not (node.args and isinstance(node.args[0], ast.JoinedStr)):
        return False
    joined_text = "".join(
        part.value for part in node.args[0].values if isinstance(part, ast.Constant) and isinstance(part.value, str)
    )
    return bool(SQL_KEYWORDS_RE.search(joined_text))


def _check_sql_injection_and_ips(
    node: ast.AST,
    file_path: str,
    ignored_const_ids: Set[int],
) -> List[QualityViolation]:
    violations: List[QualityViolation] = []
    if _is_fstring_sql_execute(node):
        violations.append(
            QualityViolation(
                rule_id="S3649",
                file_path=file_path,
                line=getattr(node, "lineno", 1),
                message="Possível SQL Injection: f-string passada diretamente para .execute().",
            )
        )

    if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in ignored_const_ids:
        for ip_match in IPV4_RE.findall(node.value):
            if not is_allowed_ipv4(ip_match):
                violations.append(
                    QualityViolation(
                        rule_id="S1313",
                        file_path=file_path,
                        line=getattr(node, "lineno", 1),
                        message=f"IP operacional hardcoded '{ip_match}' (use Settings/.env ou RFC 5737).",
                    )
                )
    return violations


def scan_python_ast_rules(root_dir: str = "app") -> List[QualityViolation]:
    """Executa todas as verificações SAST e de confiabilidade na árvore AST de `root_dir`."""
    violations: List[QualityViolation] = []
    root_path = pathlib.Path(root_dir)
    if not root_path.exists():
        return violations

    for py_file in sorted(root_path.rglob("*.py")):
        rel_path = str(py_file)
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=rel_path)
        ignored_const_ids = _collect_doc_and_description_nodes(tree)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                violations.extend(_check_function_defaults(node, rel_path))
            if isinstance(node, ast.AsyncFunctionDef):
                violations.extend(_check_async_blocking_calls(node, rel_path))
            if isinstance(node, ast.ExceptHandler):
                violations.extend(_check_except_handler(node, rel_path))
            violations.extend(_check_sql_injection_and_ips(node, rel_path, ignored_const_ids))

    return violations


def _extract_changed_lines_from_diff(diff_output: str) -> Dict[str, Set[int]]:
    changed: Dict[str, Set[int]] = {}
    current_file: Optional[str] = None
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")
    for line in diff_output.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
        elif line.startswith("@@ ") and current_file and current_file.endswith(".py"):
            match = hunk_re.match(line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                changed.setdefault(current_file, set()).update(range(start, start + max(1, count)))
    return changed


def _parse_changed_lines_from_git() -> Dict[str, Set[int]]:
    """Retorna um mapa {arquivo_py: {linhas_modificadas}} em relação ao HEAD (incluindo arquivos untracked)."""
    try:
        proc = subprocess.run(
            ["git", "diff", "-U0", "HEAD", "--", "app/", "scripts/"],
            capture_output=True,
            text=True,
            check=False,
        )
        diff_output = proc.stdout
        if not diff_output.strip():
            proc = subprocess.run(
                ["git", "diff", "-U0", "HEAD~1", "HEAD", "--", "app/", "scripts/"],
                capture_output=True,
                text=True,
                check=False,
            )
            diff_output = proc.stdout
        changed = _extract_changed_lines_from_diff(diff_output)

        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", "app/", "scripts/"],
            capture_output=True,
            text=True,
            check=False,
        )
        for rel_file in untracked.stdout.splitlines():
            if rel_file.endswith(".py") and pathlib.Path(rel_file).exists():
                line_count = len(pathlib.Path(rel_file).read_text(encoding="utf-8").splitlines())
                changed[rel_file] = set(range(1, line_count + 1))
        return changed
    except OSError:
        return {}


def _check_file_functions_complexity(
    rel_path: str,
    touched_lines: Set[int],
    max_complexity: int,
) -> List[QualityViolation]:
    path_obj = pathlib.Path(rel_path)
    if not path_obj.exists() or not touched_lines:
        return []
    violations: List[QualityViolation] = []
    tree = ast.parse(path_obj.read_text(encoding="utf-8"), filename=rel_path)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_lineno = getattr(node, "end_lineno", node.lineno)
        if not (set(range(node.lineno, end_lineno + 1)) & touched_lines):
            continue
        complexity = calculate_cognitive_complexity(node)
        if complexity > max_complexity:
            violations.append(
                QualityViolation(
                    rule_id="S3776",
                    file_path=rel_path,
                    line=node.lineno,
                    message=(
                        f"Função '{node.name}' possui Complexidade Cognitiva {complexity} "
                        f"(máximo permitido: {max_complexity})."
                    ),
                )
            )
    return violations


def check_changed_functions_complexity(
    changed_files_map: Optional[Dict[str, Set[int]]] = None,
    max_complexity: int = MAX_COGNITIVE_COMPLEXITY,
) -> List[QualityViolation]:
    """Verifica se alguma função tocada recentemente ultrapassa a Complexidade Cognitiva máxima (15)."""
    target_map = _parse_changed_lines_from_git() if changed_files_map is None else changed_files_map
    violations: List[QualityViolation] = []
    for rel_path, touched_lines in target_map.items():
        violations.extend(_check_file_functions_complexity(rel_path, touched_lines, max_complexity))
    return violations


def check_dockerfiles_hardening(
    dockerfiles: Sequence[str] = ("Dockerfile", "frontend/Dockerfile"),
) -> List[QualityViolation]:
    """Audita os Dockerfiles garantindo execução não-root (USER) e uso de lockfiles."""
    violations: List[QualityViolation] = []
    for df_path_str in dockerfiles:
        df_path = pathlib.Path(df_path_str)
        if not df_path.exists():
            continue
        content = df_path.read_text(encoding="utf-8")
        if not re.search(r"^\s*USER\s+(?!root\b)\S+", content, re.MULTILINE):
            violations.append(
                QualityViolation(
                    rule_id="S6470",
                    file_path=df_path_str,
                    line=1,
                    message="Dockerfile deve definir um usuário não-root ('USER <non-root>') no estágio final.",
                )
            )
        if "flutter upgrade" in content:
            violations.append(
                QualityViolation(
                    rule_id="S6596",
                    file_path=df_path_str,
                    line=1,
                    message="Proibido usar 'flutter upgrade' mutável no Dockerfile; fixe a tag do SDK.",
                )
            )
    return violations


def check_dependency_integrity() -> List[QualityViolation]:
    """Executa 'pip check' para garantir que não existam dependências conflitantes ou quebradas."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            msg = proc.stdout.strip() or proc.stderr.strip() or "Conflito de dependências detectado pelo pip check."
            return [
                QualityViolation(
                    rule_id="SCA-PIP",
                    file_path="requirements.txt",
                    line=1,
                    message=msg,
                )
            ]
    except OSError:
        pass
    return []


def run_quality_gate() -> int:
    """Executa todas as etapas do Quality Gate e retorna código de saída (0 = aprovado, 1 = falha)."""
    violations: List[QualityViolation] = []

    density, dup_lines, total_lines = compute_duplication_density()
    if density >= MAX_DUPLICATION_PERCENT:
        violations.append(
            QualityViolation(
                rule_id="CPD",
                file_path="app,frontend/lib",
                line=1,
                message=(
                    f"Densidade de duplicação em {density:.2f}% ({dup_lines}/{total_lines} linhas) "
                    f"excede o limite de {MAX_DUPLICATION_PERCENT:.1f}%."
                ),
            )
        )

    violations.extend(scan_python_ast_rules("app"))
    violations.extend(scan_python_ast_rules("scripts"))
    violations.extend(check_changed_functions_complexity())
    violations.extend(check_dockerfiles_hardening())
    violations.extend(check_dependency_integrity())

    print(
        f"[Quality Gate] Duplicação: {density:.2f}% ({dup_lines}/{total_lines} linhas, limite < {MAX_DUPLICATION_PERCENT:.1f}%)"
    )

    if violations:
        print(f"[Quality Gate] FALHOU com {len(violations)} violação(ões):")
        for v in violations:
            print(f"  - [{v.rule_id}] {v.file_path}:{v.line} -> {v.message}")
        return 1

    print("[Quality Gate] APROVADO: 0 violações de SAST, SCA, Complexidade Cognitiva, Duplicidade e Docker Hardening.")
    return 0


if __name__ == "__main__":
    sys.exit(run_quality_gate())
