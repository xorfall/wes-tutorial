"""Shared offline checks and disposable preview for the Custom Views chapters."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

SERIES = Path(__file__).resolve().parent
sys.path.insert(0, str(SERIES.parent))
from wes_tutorial import WES_CHECKOUT, default_binary  # noqa: E402

# The wes checkout provides the View build tools and the client assets.
ROOT = WES_CHECKOUT


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run(arguments, **options):
    return subprocess.run([str(a) for a in arguments], capture_output=True,
                          text=True, timeout=60, **options)


def successful(result):
    require(result.returncode == 0, result.stdout + result.stderr)
    return result.stdout


def options(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--binary', type=Path, default=default_binary())
    parser.add_argument('--validator', type=Path)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--site', type=Path, default=Path(os.environ.get('WES_SITE', ROOT / 'gui/dist')))
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    args.binary = args.binary.resolve()
    args.validator = (args.validator or Path(os.environ.get(
        'WES_VIEW_CONTRACT_TOOL', str(args.binary.with_name('wes-view-build'))
    ))).resolve()
    return args


def verify_chapter(chapter):
    text = (chapter / 'README.md').read_text()
    for program in chapter.glob('*.wes'):
        require('```text\n' + program.read_text() + '```' in text,
                f'Chapter snippet differs from {program.name}')
        require(all(len(line) <= 80 for line in program.read_text().splitlines()),
                f'Long program line in {program.name}')
    task = '\n'.join(re.findall(r'^> ?(.*)$', text, re.M)) + '\n'
    require(task == (chapter / 'assistant-task.txt').read_text(),
            'Assistant request differs from its file')
    for page in [chapter / 'README.md', SERIES / 'README.md',
                 *sorted((SERIES / 'reference').glob('*.md'))]:
        for target in re.findall(r'\]\(([^)]+)\)', page.read_text()):
            if not target.startswith(('http://', 'https://', '#')):
                require((page.parent / target.partition('#')[0]).exists(), f'Missing link: {target}')
    for source in chapter.glob('service-board*/*'):
        require(all(len(line) <= 80 for line in source.read_text().splitlines()),
                f'Long source line in {source.name}')


def build(source_directory, work, validator, name):
    source = work / 'view-work' / name
    shutil.copytree(source_directory, source)
    artifact = work / 'view-work' / f'{name}.wes-view.json'
    built = compile_source(source, artifact, validator)
    require(built['definition']['outputs'] == {} and
            built['definition']['interaction'] is None,
            'These first two packages must remain static')
    require(built['definition']['execution'] == 'none', 'Unexpected execution')
    generated = (source / 'contract.ts').read_text()
    require('NumericValue' in generated and 'export type State = never;' in
            generated, 'Generated numeric/static contract changed')
    return source, artifact, built


def compiler(source, artifact, validator):
    return run(['node', ROOT / 'tools/view-package/index.mjs', 'build',
                source, artifact], cwd=ROOT,
               env=dict(os.environ, WES_VIEW_CONTRACT_TOOL=str(validator)))


def compile_source(source, artifact, validator):
    built = json.loads(successful(compiler(source, artifact, validator)))
    checked = json.loads(successful(run([
        'node', ROOT / 'tools/view-package/index.mjs', 'check', artifact,
    ], cwd=ROOT, env=dict(os.environ,
                         WES_VIEW_CONTRACT_TOOL=str(validator)))))
    require(built['ok'] and checked['digest'] == built['digest'],
            'Compiled artifact check failed')
    return built


def command(binary, home, text, work):
    return run([binary, '--home', home, '--command', text], cwd=work)


def program(binary, home, path, work):
    return command(binary, home, path.read_text(), work)


def last_value(result):
    lines = successful(result).splitlines()
    values = [json.loads(line.split(': ', 1)[1]) for line in lines
              if line.startswith('id') and ': ' in line]
    require(values, result.stdout + result.stderr)
    return values[-1]


def seed_first(binary, home, work):
    chapter = SERIES / '01-first-view'
    successful(program(binary, home, chapter / 'load.wes', work))
    data = last_value(program(binary, home, chapter / 'services.wes', work))
    view = last_value(program(binary, home, chapter / 'create.wes', work))
    require(view['definition'] == 'ServiceBoard', 'Wrong initial definition')
    read = last_value(program(binary, home, chapter / 'read.wes', work))
    require(read == view, 'Reading changed the View observation')
    return data


def contract_cases(binary, home, work, normal):
    exact = {'title': 'Exact counters', 'services': [
        {'name': 'gateway', 'status': 'down',
         'rps': 9007199254740993, 'p95Ms': 0}]}
    boundary = {'title': '😀' * 128, 'services': [
        {'name': f'{index:02}' + 's' * 62, 'status': 'ok', 'rps': 0, 'p95Ms': 0}
        for index in range(16)]}
    boundary['services'][0]['name'] = '😀' * 64
    escaped = copy.deepcopy(normal)
    escaped['title'] = 'Monitor <script>'
    escaped['extra'] = 'extraFieldMustNotRender'
    duplicate = copy.deepcopy(normal)
    duplicate['services'][1]['name'] = duplicate['services'][0]['name']
    cases = dict(normal=normal, empty={'title': 'Empty monitor', 'services': []},
                 duplicate=duplicate, exact=exact, boundary=boundary,
                 escaped=escaped)
    for value in cases.values():
        last_value(command(binary, home, ':calc pure { return ' +
                           json.dumps(value, ensure_ascii=False) +
                           '; } > caseData', work))
        result = command(binary, home,
                         ':type check $caseData as:ServiceBoardInput', work)
        require(last_value(result) == value, 'Valid input was changed')
        successful(command(binary, home, ':name unbind "caseData"', work))
    invalid = []
    for field, replacement, path in [
        ('title', '', '/title'), ('title', '😀' * 129, '/title'),
        ('name', '', '/services/0/name'),
        ('name', '😀' * 65, '/services/0/name'),
        ('status', 'unknown', '/services/0/status'),
        ('rps', -1, '/services/0/rps'),
        ('p95Ms', -1, '/services/0/p95Ms'),
        ('rps', '120', '/services/0/rps'),
        ('rps', 1.5, '/services/0/rps'),
    ]:
        value = copy.deepcopy(normal)
        target = value if field == 'title' else value['services'][0]
        target[field] = replacement
        invalid.append((value, path))
    missing = copy.deepcopy(normal)
    del missing['services'][0]['p95Ms']
    invalid.append((missing, '/services/0/p95Ms'))
    oversized = copy.deepcopy(boundary)
    oversized['services'].append(dict(oversized['services'][0], name='extra'))
    invalid.append((oversized, '/services'))
    for value, path in invalid:
        last_value(command(binary, home, ':calc pure { return ' +
                           json.dumps(value, ensure_ascii=False) +
                           '; } > caseData', work))
        result = command(binary, home,
                         ':type check $caseData as:ServiceBoardInput *> problem',
                         work)
        require(result.returncode == 1, 'Invalid input was accepted')
        problem = last_value(command(binary, home, ':read $problem', work))
        require(problem['code'] == 'TYP005' and any(
            issue['path'] == path for issue in problem['issues']), problem)
        successful(command(binary, home, ':name unbind "problem"', work))
        successful(command(binary, home, ':name unbind "caseData"', work))
    invalid_binding = copy.deepcopy(normal)
    invalid_binding['services'][0].update(status='unknown', rps=-1)
    last_value(command(binary, home, ':calc pure { return ' +
                       json.dumps(invalid_binding) + '; } > invalidData', work))
    rejected = command(binary, home,
        ':view create ServiceBoard input:$invalidData *> bindingError', work)
    require(rejected.returncode == 1, 'Invalid View binding was accepted')
    problem = last_value(command(binary, home, ':read $bindingError', work))
    require(problem['code'] == 'TYP005' and
            problem['message'] == 'View input does not satisfy ServiceBoardInput'
            and {issue['path'] for issue in problem['issues']} ==
            {'/services/0/status', '/services/0/rps'}, problem)
    return cases


def render(source, work, cases, priority=False):
    cases_file = work / 'renderer-cases.json'
    cases_file.write_text(json.dumps(cases))
    successful(run(['node', SERIES / 'check-renderer.mjs', source, cases_file,
                    'priority' if priority else 'original'], cwd=ROOT))


def preview(args, home, work):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', args.port))
        port = listener.getsockname()[1]
    log_path = work / 'preview.log'
    with log_path.open('w') as log:
        server = subprocess.Popen([
            str(args.binary), '--home', str(home), '--serve', str(port),
            '--site', str(args.site.resolve()),
        ], stdout=log, stderr=log, cwd=work)
        try:
            url = f'http://127.0.0.1:{port}'
            for _ in range(100):
                require(server.poll() is None, log_path.read_text())
                try:
                    with urllib.request.urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Preview did not start')
            print(f'Preview: {url}', flush=True)
            print('Use the chapter commands. Ctrl+C stops and removes the preview.',
                  flush=True)
            server.wait()
        except KeyboardInterrupt:
            pass
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
