"""Prospective verdict×budget interaction power; fully synthetic four-cell blocks."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
import random
from bisect import bisect_left
from pathlib import Path
from statistics import fmean
from analysis.power_simulation import student_t_critical_one_sided
from analysis.c5_budget_statistics import CELLS,SIGNS,_csv

PATTERNS=list(itertools.product((0,1),repeat=4))
D=[sum(SIGNS[c]*v for c,v in zip(CELLS,pattern)) for pattern in PATTERNS]


def joint_distribution(interaction:float,shared_fraction:float)->dict:
    if not -0.75<interaction<0.25 or not 0<=shared_fraction<=1:
        raise ValueError('invalid interaction or shared fraction')
    marginal=[0.65,0.75,0.65,0.75+interaction]
    independent=[math.prod(p if value else 1-p for value,p in zip(pattern,marginal)) for pattern in PATTERNS]
    shared=[0.0]*16
    boundaries=sorted({0.0,1.0,*marginal})
    for lo,hi in zip(boundaries,boundaries[1:]):
        pattern=tuple(int((lo+hi)/2<p) for p in marginal)
        shared[PATTERNS.index(pattern)]+=hi-lo
    probabilities=[(1-shared_fraction)*a+shared_fraction*b for a,b in zip(independent,shared)]
    mean=sum(d*p for d,p in zip(D,probabilities))
    if not math.isclose(sum(probabilities),1,abs_tol=1e-12) or not math.isclose(mean,interaction,abs_tol=1e-12):
        raise ValueError('joint distribution moment mismatch')
    variance=sum((d-mean)**2*p for d,p in zip(D,probabilities))
    return {'cell_probabilities':dict(zip(CELLS,marginal)),'patterns':[list(p) for p in PATTERNS],
            'pattern_probabilities':probabilities,'interaction_mean':mean,
            'interaction_variance':variance,'shared_uniform_fraction':shared_fraction}


def simulate(*,families:int=19,slots_per_family:int=30,interaction:float=-0.2,
             shared_fraction:float=0.5,difference_icc:float=0.2,reach:float=0.5,
             branch_loss:float=0.05,replicates:int=5000,seed:int=20261124)->dict:
    if (type(families) is not int or families<15 or type(slots_per_family) is not int or slots_per_family<1
            or type(replicates) is not int or replicates<1 or not 0<=difference_icc<1
            or not 0<reach<=1 or not 0<=branch_loss<1):raise ValueError('invalid simulation settings')
    joint=joint_distribution(interaction,shared_fraction)
    base=joint['pattern_probabilities'];rng=random.Random(seed)
    critical={n:student_t_critical_one_sided(n-1,0.0125/2) for n in range(15,families+1)}
    rejected=estimable=onsets=complete=family_total=0;estimates=[]
    complete_probability=(1-branch_loss)**4
    for _ in range(replicates):
        means=[]
        for _ in range(families):
            if difference_icc:
                concentration=(1-difference_icc)/difference_icc
                draws=[rng.gammavariate(p*concentration,1) if p else 0 for p in base]
                total=sum(draws)
                if total==0:raise ValueError('Dirichlet underflow; no arbitrary probability fallback')
                probabilities=[v/total for v in draws]
            else:probabilities=base
            cumulative=[];running=0
            for p in probabilities:running+=p;cumulative.append(running)
            cumulative[-1]=1.0
            ds=[]
            for _ in range(slots_per_family):
                if rng.random()>=reach:continue
                onsets+=1
                if rng.random()>=complete_probability:continue
                ds.append(D[bisect_left(cumulative,rng.random())])
            complete+=len(ds)
            if ds:means.append(fmean(ds))
        n=len(means);family_total+=n
        if n<15:continue
        mean=fmean(means);ss=sum((v-mean)**2 for v in means)
        if not ss:continue
        estimable+=1;estimates.append(mean)
        rejected+=abs(mean)/math.sqrt(ss/(n*(n-1)))>critical[n]
    probability=rejected/replicates;z=1.959963984540054
    denominator=1+z*z/replicates
    center=(probability+z*z/(2*replicates))/denominator
    half=z*math.sqrt(probability*(1-probability)/replicates+z*z/(4*replicates**2))/denominator
    return {'families':families,'slots_per_family':slots_per_family,'interaction':interaction,
            'shared_uniform_fraction':shared_fraction,'interaction_icc':difference_icc,
            'interaction_variance':joint['interaction_variance'],'onset_reach':reach,
            'technical_loss_per_branch':branch_loss,'complete_block_probability_given_onset':complete_probability,
            'alpha_first_four_model_holm':0.0125,'replicates':replicates,'seed':seed,
            'rejections':rejected,'rejection_probability':probability,
            'monte_carlo_95_low':max(0.0,center-half),'monte_carlo_95_high':min(1.0,center+half),
            'nonestimable':replicates-estimable,'mean_observed_onsets':onsets/replicates,
            'mean_complete_blocks':complete/replicates,'mean_contributing_families':family_total/replicates,
            'mean_estimate_when_estimable':fmean(estimates) if estimates else None}


def budget(*,models:int=4,families:int=19,prompts:int=3,repeats:int=5)->dict:
    if models!=4 or min(families,prompts,repeats)<1:raise ValueError('four-model positive design required')
    precursors=models*families*2*prompts*repeats
    return {'models':models,'families':families,'prompts':prompts,'repeats':repeats,
            'precursors':precursors,'precursor_decisions_max':6*precursors,
            'onset_reservations_max':precursors,'branches_max':4*precursors,
            'continuation_decisions_max':10*precursors,'total_decisions_max':16*precursors,
            'by_cell_decisions_max':{c:int(c[-1])*precursors for c in CELLS},
            'assumption':'One provider request per decision, no retries; token/latency/financial costs not estimated.'}


def generate(core_replicates:int=5000,sensitivity_replicates:int=2000)->dict[str,str]:
    scenarios=[]
    for families in (19,40,80):
        for shared in (0.5,0.9):
            for icc in (0.0,0.2):
                for effect in (0.0,-0.1,-0.2):
                    settings=dict(families=families,slots_per_family=30,interaction=effect,
                                  shared_fraction=shared,difference_icc=icc,reach=0.5,branch_loss=0.05)
                    seed=int(hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:12],16)
                    n=core_replicates if families==19 and shared==0.5 else sensitivity_replicates
                    scenarios.append(simulate(**settings,replicates=n,seed=seed))
    root=Path(__file__).resolve().parents[1]
    result={'version':'c5-budget-interaction-planning-v1','status':'SYNTHETIC_PLANNING_ONLY',
            'eligible_for_main_analysis':False,'core_replicates':core_replicates,
            'sensitivity_replicates':sensitivity_replicates,'joint_models':[
                joint_distribution(effect,shared) for shared in (0.5,0.9) for effect in (0,-0.1,-0.2)],
            'scenarios':scenarios,'budget':budget(),
            'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                            ('analysis/c5_budget_power_20261124.py','analysis/c5_budget_statistics.py',
                             'analysis/c5_statistical_plan_20261123.py','analysis/power_simulation.py')},
            'limitations':['Four endpoint joint distribution specified explicitly; not calibrated to real models.',
             'Dirichlet family distribution makes ICC apply to the interaction D, not individual outcomes.',
             'Independent branch loss0.05 implies complete-block probability0.95^4, not0.95.',
             'First Holm threshold provides conservative per-model power, not joint four-model replication power.',
             'This design does not power or amend the older C5 early-stop primary.',
             'These simulations are not empirical model runs or registration.']}
    return {'planning.json':json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n',
            'power.csv':_csv(scenarios),'budget.json':json.dumps(budget(),indent=2,sort_keys=True)+'\n'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory',type=Path,required=True)
    parser.add_argument('--core-replicates',type=int,default=5000)
    parser.add_argument('--sensitivity-replicates',type=int,default=2000)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.output_directory.exists() and not args.check:parser.error('preserve existing output')
    outputs=generate(args.core_replicates,args.sensitivity_replicates)
    if args.check:
        for name,text in outputs.items():
            if (args.output_directory/name).read_text()!=text:raise ValueError('planning artifact differs:'+name)
        print('VERIFIED_C5_BUDGET_INTERACTION_PLANNING')
    else:
        args.output_directory.mkdir(parents=True,exist_ok=False)
        for name,text in outputs.items():
            with (args.output_directory/name).open('x',encoding='utf-8',newline='') as handle:handle.write(text)
        print(args.output_directory)


if __name__=='__main__':main()
