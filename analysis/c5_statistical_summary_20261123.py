"""Metadata-preserving wrapper for excluded/synthetic endpoint-table summaries.

The original statistical-plan source and108-scenario artifacts remain frozen.
This adapter never promotes calibration or excluded data into a main analysis.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any
from analysis.c5_statistical_plan_20261123 import summarize_pairs


METADATA=('simulated','data_kind','eligible_for_main_analysis','analysis_release','plan_sha256')


def summarize_export(data:dict[str,Any],*,inference:bool=False)->dict[str,Any]:
    if data.get('schema_version')!='c5-paired-endpoint-table-v1' or not isinstance(data.get('rows'),list):
        raise ValueError('expected endpoint-table schema and explicit rows')
    if any(key not in data for key in METADATA):
        raise ValueError('source metadata is incomplete; no inferred main eligibility')
    if type(data['simulated']) is not bool or data['eligible_for_main_analysis'] is not False:
        raise ValueError('this wrapper accepts only explicitly excluded/calibration data')
    expected='SYNTHETIC_CALIBRATION' if data['simulated'] else 'EXCLUDED_REPLAY_VERIFIED_DESCRIPTIVE'
    if data['data_kind']!=expected:
        raise ValueError('simulated and data_kind provenance disagree')
    if data['analysis_release'] not in {'NOT_ATTESTED_BY_ENDPOINT_READER','NOT_ATTESTED'}:
        raise ValueError('analysis release must remain not attested')
    if not isinstance(data['plan_sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',data['plan_sha256']):
        raise ValueError('frozen plan SHA-256 required')
    if (not isinstance(data.get('model'),str) or not data['model']
            or data.get('contrast') not in {'C5','C4_C3','AA'}
            or data.get('endpoint') not in {'early_stop','terminal_regression','temporary_regression'}):
        raise ValueError('one named model/contrast/endpoint required')
    for row in data['rows']:
        for key in ('model','contrast','endpoint'):
            if key in row and row[key]!=data[key]:raise ValueError('mixed strata in endpoint table')
    result=summarize_pairs(data['rows'],inference=inference)
    result.update({key:data[key] for key in METADATA})
    result['source_context']={key:data[key] for key in
        ('endpoint_definition','denominator','missingness','endpoint_validity','provenance') if key in data}
    result.update(model=data['model'],contrast=data['contrast'],endpoint=data['endpoint'],
                  schema_version='c5-tagged-statistical-summary-v1',
                  confirmatory_eligibility='NOT_ATTESTED_BY_THIS_TOOL',
                  interpretation='EXCLUDED_OR_SYNTHETIC; any requested intervals are assumption-dependent sensitivity displays only')
    return result


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--assume-independent-families',action='store_true')
    args=parser.parse_args()
    if args.output.exists():parser.error('output exists; preserve earlier summary')
    raw=args.input.read_bytes()
    result=summarize_export(json.loads(raw),inference=args.assume_independent_families)
    result['input_sha256']=hashlib.sha256(raw).hexdigest()
    result['summary_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2,sort_keys=True,allow_nan=False);handle.write('\n')
    print(args.output)


if __name__=='__main__':main()
