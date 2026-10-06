#!/usr/bin/env python3
"""Verify a second View identity and a failed build without altering the first."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import check_support as check


def build_packages(work, validator):
    first = check.SERIES / '01-first-view/service-board'
    original, _, _ = check.build(first, work, validator, 'service-board')
    revised, artifact, built = check.build(HERE / 'service-board-priority',
        work, validator, 'service-board-priority')
    check.require((original / 'types.yaml').read_bytes() ==
                  (revised / 'types.yaml').read_bytes(), 'Input contract changed')
    collision = work / 'collision-source'
    shutil.copytree(revised, collision)
    manifest = json.loads((collision / 'view.json').read_text())
    manifest.update(name='ServiceBoard', id='service-board')
    (collision / 'view.json').write_text(json.dumps(manifest))
    check.compile_source(collision, work / 'view-work/collision.wes-view.json',
                         validator)
    return original, revised, artifact, built


def seed_revision(binary, home, work):
    check.successful(check.program(binary, home, HERE / 'load.wes', work))
    revised = check.last_value(check.program(binary, home,
                                             HERE / 'create.wes', work))
    check.require(revised['definition'] == 'ServiceBoardPriority', revised)
    for name, definition in [('read.wes', 'ServiceBoardPriority'),
                              ('read-original.wes', 'ServiceBoard')]:
        read = check.last_value(check.program(binary, home, HERE / name, work))
        check.require(read['definition'] == definition, 'Existing View changed')
    return revised


def main():
    args = check.options(__doc__)
    check.verify_chapter(HERE)
    with tempfile.TemporaryDirectory(prefix='wes-revise-view-') as scratch:
        work = Path(scratch)
        _, revised, artifact, _ = build_packages(work, args.validator)
        home = work / 'check-home'
        data = check.seed_first(args.binary, home, work)
        collision = check.program(args.binary, home, HERE / 'collision.wes', work)
        check.require(collision.returncode == 1 and
            'VIE004' in collision.stderr and
            'View name/id is already installed; use a new identity for different code'
            in collision.stderr, collision.stdout + collision.stderr)
        before = check.last_value(check.program(args.binary, home,
                                                HERE / 'read-original.wes', work))
        created = seed_revision(args.binary, home, work)
        original = check.last_value(check.program(args.binary, home,
                                                  HERE / 'read-original.wes', work))
        check.require(before == original, 'Original View changed')
        check.require(created['definition'] != original['definition'],
                      'New instance used the original definition')
        check.successful(check.program(args.binary, home, HERE / 'load.wes', work))
        again = check.last_value(check.program(args.binary, home,
                                               HERE / 'read.wes', work))
        check.require(again == created, 'Identical reload changed the instance')
        order = check.last_value(check.program(args.binary, home,
                                               HERE / 'input-order.wes', work))
        check.require(order == ['orders-api', 'billing-worker', 'gateway'], order)
        cases = check.contract_cases(args.binary, home, work, data)
        ties = copy.deepcopy(data)
        ties['services'] = [
            {'name': name, 'status': status, 'rps': 1, 'p95Ms': 2}
            for name, status in [('ok-a', 'ok'), ('down-a', 'down'),
                                  ('ok-b', 'ok'), ('down-b', 'down'),
                                  ('warn', 'degraded')]
        ]
        cases['ties'] = ties
        check.render(revised, work, cases, priority=True)
        # Failed compilation must leave the last successful artifact untouched.
        saved_artifact = artifact.read_bytes()
        renderer = revised / 'View.tsx'
        saved_source = renderer.read_text()
        renderer.write_text(saved_source + '\nconst invalid: string = 1;\n')
        failed = check.compiler(revised, artifact, args.validator)
        diagnostics = json.loads(failed.stdout)
        check.require(failed.returncode == 1 and not diagnostics['ok'] and
                      any(d['code'] == 'TS2322' for d in diagnostics['diagnostics']),
                      failed.stdout + failed.stderr)
        check.require(artifact.read_bytes() == saved_artifact,
                      'Failed build replaced the previous artifact')
        renderer.write_text(saved_source)
        print('PASS revision: severity order, stable ties and unchanged input')
        print('PASS packages: collision refused; both definitions remain usable')
        print('PASS rebuild: identical reload and failed-build artifact retention')
        if args.preview:
            preview_home = work / 'preview-home'
            check.seed_first(args.binary, preview_home, work)
            check.preview(args, preview_home, work)


if __name__ == '__main__':
    main()
