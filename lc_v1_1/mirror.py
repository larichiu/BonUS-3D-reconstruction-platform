"""Run: python mirror.py ORIGINAL_SEQUENCE [ORIGINAL_SEQUENCE ...]."""
import argparse
from pathlib import Path
from variants.lc_v1_1.core.io import load_patient
from variants.lc_v1_1.core.mirror import mirror


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='mirror: save left-right mirrored ultrasound images AND masks as _for3Drecon series')
    parser.add_argument('sequences',nargs='+',type=Path)
    parser.add_argument('--output',type=Path,default=Path('data/derived_series'))
    parser.add_argument('--force',action='store_true',help='Regenerate every copy from its original image or mask, without reusing existing outputs')
    args=parser.parse_args()
    for sequence in args.sequences:
        print(f'mirror: {sequence}',flush=True)
        def progress(done,total):
            if done%100==0 or done==total:
                print(f'  {done}/{total} frames',flush=True)
        result=mirror(load_patient(sequence),args.output,progress,force=args.force)
        print(f'Saved {len(result.matches)} frames, {int(result.matches.has_mask.sum())} masks: {result.frames_dir.parent}',flush=True)
