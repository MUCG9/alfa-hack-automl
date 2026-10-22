"""Select fixed-recipe CV candidates from completed, same-split paired runs."""
from pathlib import Path
import argparse,json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--control-results',type=Path,required=True)
    parser.add_argument('--results',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    control=json.loads(args.control_results.read_text()); metric=control['spec']['metric']
    reference={r['seed']:r for r in control['results'] if r['status']=='ok'}
    higher=control['spec']['greater_is_better']; ranked=[]
    for path in args.results:
        data=json.loads(path.read_text())
        if data['inputs']!=control['inputs']: raise ValueError('Finalist input hashes differ')
        for candidate in data['candidates']:
            rows={r['seed']:r for r in data['results'] if r['name']==candidate['name'] and r['status']=='ok'}
            if set(rows)!=set(reference): continue
            if any(rows[s]['split']['split_sha256']!=reference[s]['split']['split_sha256'] for s in rows): raise ValueError('Finalist splits differ')
            values=[rows[s]['metrics'][metric] for s in sorted(rows)]
            deltas=[(rows[s]['metrics'][metric]-reference[s]['metrics'][metric])*(1 if higher else -1) for s in sorted(rows)]
            ranked.append({'source':str(path),'name':candidate['name'],'recipe':candidate['recipe'],'mean':sum(values)/len(values),'deltas':deltas,'stable_improvement':min(deltas)>0})
    ranked.sort(key=lambda r:r['mean'],reverse=higher)
    stable=[r for r in ranked if r['stable_improvement']]
    selected=[{'name':'control','recipe':control['candidates'][0]['recipe']}]
    for index,item in enumerate(stable[:1]): selected.append({'name':f'finalist-{index+1}','recipe':item['recipe']})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(selected,ensure_ascii=False,indent=2))
    args.output.with_suffix('.selection.json').write_text(json.dumps({'ranked':ranked,'scope':'reused public holdouts; CV is another robustness check, not an untouched private test'},ensure_ascii=False,indent=2))
    print(json.dumps({'selected':[c['name'] for c in selected],'best':stable[0]['name'] if stable else 'control'}),flush=True)


if __name__=='__main__': main()
