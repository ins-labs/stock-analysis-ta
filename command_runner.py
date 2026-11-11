"""Allow one reviewed analysis entrypoint, never shell/eval."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def parse_command(command):
    if not command or len(command) > 4096:
        raise ValueError('ANALYSIS_COMMAND must be non-empty and at most 4096 characters')
    tokens = shlex.split(command)
    if tokens[:2] != ['python', 'analyze.py']:
        raise ValueError('Only python analyze.py with documented arguments is permitted')
    # Parse only: imports no untrusted module and executes no analysis here.
    from analyze import parser, data_path
    args = parser().parse_args(tokens[2:])
    data_path(args.input, '.csv')
    data_path(args.metadata, '.json')
    return [sys.executable, str(ROOT / 'analyze.py'), *tokens[2:]]


def main():
    try:
        command = parse_command(os.environ.get('ANALYSIS_COMMAND', ''))
    except ValueError as exc:
        print('Command rejected: ' + str(exc), file=sys.stderr)
        return 2
    print('Trusted argv:', command, flush=True)
    env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ['TOKEN', 'SECRET', 'PASSWORD', 'KEY'])}
    result = subprocess.run(command, cwd=ROOT, env=env, shell=False)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
