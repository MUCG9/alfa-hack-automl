"""Compact verified BASE/ERR diagnoses, aggregate-only; no ML fitting."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.error_analysis.api import ErrorProfile
from automl.error_analysis.reporting import read_section,write_json
from automl.error_analysis.preparation import sha


def summarize(closure_path):
    closure_path=Path(closure_path).resolve()
    closed=json.loads(closure_path.read_text())
    if closed.get('baseline_complete') is not True:
        raise ValueError('Completed BASE verification required')
    results=[]
    for run in closed['original_runs']:
        for scope in run['scopes']:
            p=Path(scope['path'])
            if sha(p)!=scope['profile_sha256']: raise ValueError('Profile changed')
            profile=ErrorProfile.from_json(p.read_text())
            models=read_section(profile,'models')
            control=models['models'][profile.request.control_model_id]
            record=control['folds'][scope['scope']]
            slices=read_section(profile,'slices')
            subset=next(x for x in slices['models'] if x['model']==profile.request.control_model_id and x['fold']==scope['scope'])
            selected=[s for s in subset['slices'] if s['dimension']=='missing_feature_count' or s['dimension'].startswith('context_support:')]
            # Classification slice confusion matrices are intentionally omitted.
            selected=[{k:s[k] for k in ('dimension','slice','rows','independent_groups','low_support','squared_error_share') if k in s}
                      | {'metric':s['metrics'].get(profile.request.task.metric) if s.get('metrics') else None}
                      for s in selected]
            comparisons=read_section(profile,'comparisons')
            ablations=[]
            for blend in comparisons['declared_blends']:
                if blend['name']=='selected-fixed-ensemble':
                    fold=blend['folds'][scope['scope']]
                    ablations=fold['ablations']
            result={'version':run['version'],'kind':run['kind'],'scope':scope['scope'],
                'control_id':profile.request.control_model_id,'profile_status':profile.status,
                'original_rows':profile.request.dataset.rows,'validation_rows':record['rows'],
                'profile_sha256':scope['profile_sha256'],'request_sha256':profile.request_sha256,
                'analysis_source_sha256':profile.analysis_source_sha256,
                'metrics':record['metrics'],'control_slices':selected,'fixed_weight_ablations':ablations,
                'section_status':{s.name:{'status':s.status,'reason':s.reason} for s in profile.sections}}
            if run['kind']=='classification':
                result.update(label_conflicts_full_dataset=models['label_conflicts'],
                    independent_fitting_groups_per_class=record['independent_fitting_groups_per_class'],
                    most_common_confusions=record['most_common_confusions'])
            else:
                result.update({k:record[k] for k in ('bias','largest_error_concentration','residual_quantiles')})
            results.append(result)
    return {'schema_version':'1.0','baseline_complete':True,'closure_sha256':sha(closure_path),
        'new_model_fits':0,'raw_rows_exported':False,'predictions_exported':False,'runs':results,
        'scope':'Recomputed fixed-prediction reused-public diagnostics, not independent/private assessment',
        'limits':['search/confirmation participated in model and blend selection; not full OOF',
                  'classification group bootstrap conditional on saved predictions, adaptive comparisons unadjusted',
                  'regression each forward scope has too few independent periods for a reliable interval',
                  'duplicate label conflicts are not a proven irreducible MacroF1 ceiling',
                  'overlapping slices cannot be added as disjoint error shares']}


def markdown(data):
    v11=[r for r in data['runs'] if r['version']=='v11-featureviews1']
    lines=['# ERR-01 — локальные численные диагнозы,23октября2026','',
           'BASE-01 завершён:8паспортов,4исходных запуска V11/V16,0новых обучений.',
           'Контроль качества: SHA,порядок строк/классов,исходные splits,метрики и реальные итоговые CSV сверены.',
           'Это диагностика повторно используемого public, НЕ официальный score или независимая оценка.','',
           '|Задача V11|Срез|Строк проверки|Метрика|','|---|---|---:|---:|']
    for r in v11:
        metric='macro_f1' if r['kind']=='classification' else 'rmse'
        lines.append(f"|{r['kind']}|{r['scope']}|{r['validation_rows']}|{r['metrics'][metric]:.12f}|")
    lines+=['','## Диагнозы классификации','',
        'Слабые классы устойчивы на обоих срезах: Backdoor и Analysis; низкий F1 не сводится к Worms.',
        '|Срез|Backdoor F1/recall|Analysis F1/recall|Backdoor→DoS|Analysis→DoS|','|---|---|---|---:|---:|']
    for r in v11:
        if r['kind']!='classification':continue
        m=r['metrics'];f=m['per_class_f1'];d=m['per_class_diagnostics'];cs=m['confusion_matrix'];labels=cs['classes']
        count=lambda a,b:cs['counts'][labels.index(a)][labels.index(b)]
        lines.append(f"|{r['scope']}|{f['Backdoor']:.4f}/{d['Backdoor']['recall']:.4f}|{f['Analysis']:.4f}/{d['Analysis']['recall']:.4f}|{count('Backdoor','DoS')}|{count('Analysis','DoS')}|")
    c=next(r for r in v11 if r['kind']=='classification')
    conflict=c['label_conflicts_full_dataset'];rows=conflict['rows_in_conflicting_groups']
    lines+=['',f"В полном train:{conflict['groups_with_conflicting_labels']}групп одинаковых признаков с разными метками;{rows}/{c['original_rows']}строк ({100*rows/c['original_rows']:.2f}%). Это не доказанный потолок MacroF1 и не основание автоматически удалять такие строки.",
            'Worms имеет лишь46/54 независимые fitting-группы на этих двух срезах; улучшение только этого класса ненадёжно. Пропусков входных признаков в проверочных срезах классификации нет.','',
            'Практический вывод: проверять дополняющие предсказания третьего участника; не включать глобально inverse-frequency weights/SMOTE/пороговую настройку без внешней групповой проверки.','',
            '## Диагнозы регрессии','',
            '|Срез|Доля SSE в худшем1%|Доля SSE в худшем5%|Bias(pred−true)|SSE без истории context0|','|---|---:|---:|---:|---:|']
    for r in v11:
        if r['kind']!='regression':continue
        tail=r['largest_error_concentration']
        unseen=next(s for s in r['control_slices'] if s['dimension']=='context_support:0' and s['slice']=='unseen')
        lines.append(f"|{r['scope']}|{100*tail['0.01']['squared_error_share']:.2f}%|{100*tail['0.05']['squared_error_share']:.2f}%|{r['bias']:.4f}|{100*unseen['squared_error_share']:.2f}% ({unseen['rows']}строк)|")
    lines+=['','Ненаблюдавшиеся fitting-контексты и длинный хвост остатков — более явные источники потерь, чем единый постоянный bias: знак смещения меняется между периодами.',
            '5+пропущенных признаков:34.47% SSE на search,но12.41% на confirmation; эффект зависит от периода, одной общей поправки недостаточно.',
            'Второй участник исходного регрессионного ансамбля имеет смешанную пользу: его удаление меняет RMSE на +.148874(search),−.145474(confirmation). Первый участник явно полезен на обоих срезах.',
            'Практический вывод: одно отдельное семейство HPO при неизменных признаках; оценивать на forward-срезах и против сильного актуального контроля, включая LONG-01 (RMSE34.696921mean). Не смешивать одновременно FE/selection/HPO.',
            '','## Ограничения и следующие действия','',
            'Регрессионные паспорта partial только из-за недоступной временной uncertainty; обязательные alignment/models/comparisons/slices завершены, это не ошибка обучения.',
            'SEL-01: сначала ОДНА недостающая confirmation для заранее выбранного XGBoost; любой смешанный результат оставляет selector OFF. HPO-01 — только следующий отдельный эксперимент.',
            'Машиночитаемые агрегаты и fingerprints: соседний JSON. Исходные прогнозы/строки в Git не экспортируются.']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.md').exists():raise FileExistsError('Never overwrite previous diagnoses')
    data=summarize(args.closure)
    write_json(args.output,data)
    args.output.with_suffix('.md').write_text(markdown(data),encoding='utf-8')
    print(json.dumps({'profiles':len(data['runs']),'new_model_fits':0,'output':str(args.output)}))
