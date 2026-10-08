"""Fail publication when a coding question lacks its reviewed quality contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.interview.registry import is_blocked_path, is_frozen_path
from app.services.interview.runner import COMMAND_IDS, resolve_command
from app.services.interview.trusted_cases import (
    MANUAL_REQUIREMENTS,
    cases_for,
    inventory_digest,
)

CONTRACT_PATH = Path(__file__).resolve().parents[1] / 'benchmarks/interview_quality_contract.json'


def run_gate(*, challenges_dir: Path, contract_path: Path = CONTRACT_PATH) -> dict[str, Any]:
    try:
        contract = json.loads(contract_path.read_text())
        registry = json.loads((challenges_dir / 'interview-registry.json').read_text())
        questions = contract['questions']
        entries = registry['challenges']
        slugs = [entry['slug'] for entry in entries]
        if (contract['version'] != 1 or len(slugs) != 10 or len(set(slugs)) != len(slugs)
                or set(questions) != set(slugs)):
            raise ValueError('Registry and quality contract do not match')
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'pass': False, 'issues': [str(error)], 'questions': []}

    rows = []
    for entry in entries:
        slug = entry['slug']
        issues = []
        try:
            path = (challenges_dir / slug).resolve()
            if not path.is_relative_to(challenges_dir.resolve()):
                raise ValueError('Question path escapes challenge root')
            quality = questions[slug]
            floor = quality['min_visible_tests']
            if type(floor) is not int or floor < 5:
                raise ValueError('Invalid visible test floor')
            cases = cases_for(slug)
            ids = {case.id for case in cases}
            if len(cases) < 5 or len(ids) != len(cases) or any(type(c.weight) is not int or c.weight <= 0 for c in cases):
                raise ValueError('Invalid independent case inventory')
            requirements = quality['requirements']
            if not isinstance(requirements, dict) or len(requirements) < 3:
                raise ValueError('Insufficient requirement coverage')
            for requirement, case_ids in requirements.items():
                if not requirement or not isinstance(case_ids, list) or not case_ids or not set(case_ids) <= ids:
                    raise ValueError('Uncovered requirement: ' + str(requirement))
            if quality['manual_requirements'] != MANUAL_REQUIREMENTS.get(slug, []):
                raise ValueError('Undeclared manual coverage gap')
            for name in ('README.md', 'SOLUTION.md'):
                if not (path / name).is_file():
                    raise ValueError('Missing ' + name)
            entry_files = entry['entry_files']
            if not isinstance(entry_files, list) or not entry_files:
                raise ValueError('Missing entry files')
            for name in entry_files:
                target = (path / name).resolve()
                if not target.is_relative_to(path) or not target.is_file() or is_blocked_path(name):
                    raise ValueError('Invalid candidate entry file: ' + name)
            tests = [p for p in (path / 'tests').rglob('*') if p.is_file() and (
                p.name.startswith('test_') and p.suffix == '.py' or '.test.' in p.name)]
            if not tests or any(not is_frozen_path(str(p.relative_to(path))) for p in tests):
                raise ValueError('Missing or editable practice tests')
            commands = entry['runner']['commands']
            if set(commands) != COMMAND_IDS:
                raise ValueError('Incomplete command inventory')
            for command in [entry['test_command'], *commands.values()]:
                resolve_command(command)
            json.dumps([c.expected for c in cases], allow_nan=False)
            digest = inventory_digest(slug)
        except (OSError, ValueError, KeyError, TypeError) as error:
            issues.append(str(error))
            digest = None
        rows.append({'slug': slug, 'pass': not issues, 'issues': issues, 'inventory_digest': digest})
    return {'pass': all(row['pass'] for row in rows), 'questions': rows, 'question_count': len(rows),
            'runtime_verification': 'Required separately in Docker CI; static publication checks are not execution evidence'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--challenges-dir', type=Path, default=Path(__file__).resolve().parents[2] / 'challenges')
    args = parser.parse_args()
    result = run_gate(challenges_dir=args.challenges_dir)
    print(json.dumps(result, indent=2))
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
