#!/usr/bin/env python3
"""Build, install and read the first View without a model or external service."""
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import check_support as check


def main():
    args = check.options(__doc__)
    check.verify_chapter(HERE)
    with tempfile.TemporaryDirectory(prefix='wes-first-view-') as scratch:
        work = Path(scratch)
        source, _, _ = check.build(HERE / 'service-board', work,
                                    args.validator, 'service-board')
        home = work / 'check-home'
        data = check.seed_first(args.binary, home, work)
        cases = check.contract_cases(args.binary, home, work, data)
        check.render(source, work, cases)
        print('PASS first View: build, check, load, create and read')
        print('PASS edge cases: empty, duplicates, invalid, limits and exact numbers')
        if args.preview:
            # The reference package is built; the reader enters the Wes steps.
            check.preview(args, work / 'preview-home', work)


if __name__ == '__main__':
    main()
