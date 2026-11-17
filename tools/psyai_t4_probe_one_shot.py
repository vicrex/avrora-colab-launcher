#!/usr/bin/env python3
"""One-shot official Colab T4 allocation diagnostic. No model, user data or secrets logged."""
import os,sys,subprocess,tempfile,re
from pathlib import Path

REMOTE="""import subprocess
r=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
if r.returncode:
    raise RuntimeError('GPU_NOT_VISIBLE')
rows=[x.strip() for x in r.stdout.splitlines() if x.strip()]
if not rows: raise RuntimeError('GPU_NOT_VISIBLE')
print('PSYAI_COLAB_T4_PROBE_OK', flush=True)
"""
def categorize(out):
    low=out.casefold()
    tests=[
        ('GPU_ALLOCATION_OR_QUOTA',r'too many assignments|refus|exhaust|412|cannot assign|resource unavailable|resource exhausted|accelerator not available'),
        ('AUTH_OR_TOKEN_FAILURE',r'authentication|unauthorized|invalid_grant|refresh token|permission denied|403|401|login required'),
        ('CLI_ARGUMENT_FAILURE',r'no such option|unrecognized arguments|missing argument|usage: colab'),
        ('BACKEND_TRANSPORT_ERROR',r'503|504|connection reset|connection refused|network|timed out|timeout|service unavailable'),
        ('REMOTE_SCRIPT_ERROR',r'gpu_not_visible|traceback|error in cell|execution failed'),
    ]
    for name,pat in tests:
        if re.search(pat,low):return name
    return 'UNKNOWN_REMOTE_FAILURE'

def main():
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        print('PSYAI_COLAB_STATUS=BLOCKED_MISSING_EXISTING_ADC');return 2
    with tempfile.TemporaryDirectory(prefix="psyai-t4-probe-") as tmp:
        p=Path(tmp)/"probe.py";p.write_text(REMOTE,encoding="utf-8")
        try:
            run=subprocess.run(['colab','--auth=adc','run','--gpu','T4',str(p)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                timeout=360,check=False)
            txt=run.stdout.decode("utf-8","replace")
            ok=run.returncode==0 and 'PSYAI_COLAB_T4_PROBE_OK' in txt
            print('PSYAI_COLAB_STATUS='+('T4_ASSIGNED' if ok else categorize(txt)))
            print('PSYAI_COLAB_CLI_EXIT='+str(run.returncode))
            print('PSYAI_COLAB_INFERENCE=NOT_RUN')
            return 0 if ok else 2
        except subprocess.TimeoutExpired:
            print('PSYAI_COLAB_STATUS=TRANSPORT_TIMEOUT_360S')
            print('PSYAI_COLAB_INFERENCE=NOT_RUN')
            return 2
if __name__=='__main__':sys.exit(main())
