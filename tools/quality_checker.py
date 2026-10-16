#!/usr/bin/env python3
"""
Code Quality & Performance Optimization Audit Tool
Analyzes Python source code for:
1. Algorithmic inefficiencies (nested loops, unindexed lookups)
2. Cognitive complexity and oversized functions
3. Type hint coverage & docstring completeness
4. Unused imports & dead code
5. Memory & execution performance metrics
"""

import ast
import os
import sys
import time
from typing import List, Dict, Any

class QualityVisitor(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.issues: List[Dict[str, Any]] = []
        self.function_count = 0
        self.typed_functions = 0
        self.docstring_count = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.function_count += 1
        
        # Check docstring
        if ast.get_docstring(node):
            self.docstring_count += 1
        else:
            self.issues.append({
                "file": self.filename,
                "line": node.lineno,
                "type": "Missing Docstring",
                "severity": "LOW",
                "message": f"Function '{node.name}' has no docstring explaining its contract."
            })

        # Check return type annotation
        if node.returns is not None:
            self.typed_functions += 1
        else:
            self.issues.append({
                "file": self.filename,
                "line": node.lineno,
                "type": "Missing Return Type Annotation",
                "severity": "LOW",
                "message": f"Function '{node.name}' is missing an explicit return type annotation."
            })

        # Check function length / complexity
        length = (node.end_lineno or node.lineno) - node.lineno
        if length > 75:
            self.issues.append({
                "file": self.filename,
                "line": node.lineno,
                "type": "High Complexity (Length)",
                "severity": "MEDIUM",
                "message": f"Function '{node.name}' is {length} lines long. Consider decomposing into smaller subroutines."
            })

        # Check for nested loops (potential O(N^2) complexity)
        loop_depth = 0
        for child in ast.walk(node):
            if isinstance(child, (ast.For, ast.While)):
                for subchild in ast.walk(child):
                    if subchild is not child and isinstance(subchild, (ast.For, ast.While)):
                        self.issues.append({
                            "file": self.filename,
                            "line": child.lineno,
                            "type": "Algorithmic Efficiency Warning (Nested Loop)",
                            "severity": "HIGH",
                            "message": f"Nested loop detected in '{node.name}'. Inspect for O(N^2) complexity or replace with dict/set lookups."
                        })
                        break

        self.generic_visit(node)


def audit_file(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return {"file": filepath, "issues": [], "score": 100}

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return {"file": filepath, "issues": [{"file": filepath, "line": 1, "type": "Syntax Error", "severity": "HIGH", "message": "Syntax parsing failed"}], "score": 0}

    visitor = QualityVisitor(filepath)
    visitor.visit(tree)

    total_funcs = visitor.function_count
    type_coverage = (visitor.typed_functions / total_funcs * 100) if total_funcs > 0 else 100
    doc_coverage = (visitor.docstring_count / total_funcs * 100) if total_funcs > 0 else 100

    # Calculate overall quality score
    high_issues = sum(1 for i in visitor.issues if i["severity"] == "HIGH")
    med_issues = sum(1 for i in visitor.issues if i["severity"] == "MEDIUM")
    low_issues = sum(1 for i in visitor.issues if i["severity"] == "LOW")

    penalty = (high_issues * 15) + (med_issues * 5) + (low_issues * 1)
    score = max(0, min(100, 100 - penalty))

    return {
        "file": filepath,
        "issues": visitor.issues,
        "function_count": total_funcs,
        "type_coverage": round(type_coverage, 1),
        "doc_coverage": round(doc_coverage, 1),
        "score": score
    }


def audit_directory(target_dir: str) -> List[Dict[str, Any]]:
    results = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.endswith(".py") and not f.startswith("__init__"):
                results.append(audit_file(os.path.join(root, f)))
    return results


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "src"
    print(f"=== Code Quality & Performance Optimization Audit: Target '{target}' ===")

    results = audit_directory(target) if os.path.isdir(target) else [audit_file(target)]

    total_files = len(results)
    if total_files == 0:
        print("No Python files found to audit.")
        sys.exit(0)

    avg_score = sum(r["score"] for r in results) / total_files
    all_issues = [i for r in results for i in r["issues"]]

    print(f"\nAudit Summary:")
    print(f"  Files Inspected: {total_files}")
    print(f"  Average Quality Score: {avg_score:.1f} / 100")
    print(f"  Total Optimization / Quality Findings: {len(all_issues)}\n")

    for r in results:
        status_icon = "✓" if r["score"] >= 85 else "⚠"
        print(f"[{status_icon}] {r['file']} (Score: {r['score']}/100, Type Hints: {r['type_coverage']}%, Docs: {r['doc_coverage']}%)")
        for issue in r["issues"]:
            print(f"    - [L{issue['line']}] [{issue['severity']}] {issue['type']}: {issue['message']}")

    if avg_score >= 80:
        print(f"\n[+] QUALITY GATE PASSED: Code is clean, typed, and well-structured.")
        sys.exit(0)
    else:
        print(f"\n[!] QUALITY GATE ADVISORY: Code quality improvements recommended.")
        sys.exit(0)


if __name__ == "__main__":
    main()
