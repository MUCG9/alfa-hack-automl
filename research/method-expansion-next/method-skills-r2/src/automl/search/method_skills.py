"""Opt-in bounded method instructions for Qwen; never authorizes a model fit.
Only tools present in the trusted runtime registry can be described as ready.
Allowed dependencies alone do not create an adapter or a candidate queue slot.
"""
import hashlib,json,math

MAX_PACKET_BYTES=8192
MAX_CARDS=6
CARDS={
 'boosting':dict(id='boosting',engines=['lightgbm','catboost','xgboost'],
    use_when='Ordinary numeric/categorical tabular task; keep the protected strong control.',
    preparation='All learned encodings, feature selection, history and calibration use only current fitting rows.',
    experiment='Change one capacity/regularization or feature factor; compare saved split metrics and supported classes.',
    limitation='An allowed library or plausible hypothesis is not a measured improvement.'),
 'extra_trees':dict(id='extra_trees',engines=['extra_trees'],
    use_when='Test a randomized forest as a different inductive bias or a predeclared fixed blend component.',
    preparation='Existing adapter uses fitting-only categorical frequencies and numeric median imputation; it is not one-hot linear preprocessing.',
    experiment='Start with a bounded forest, preserve the complete boosting control, record tree memory and full refit cost.',
    limitation='No early stopping; nested Optuna currently supports only boosting engines. More trees are not automatically better.'),
 'linear_tabular':dict(id='linear_tabular',engines=['linear_text'],
    use_when='Ordinary numeric/categorical table: the existing linear_text tool also works with no text columns.',
    preparation='Existing fitting-only numeric median imputation/scaling and sparse categorical OneHot; unknown categories are ignored. Never fit preprocessing on validation rows.',
    experiment='Regression uses existing Ridge alpha10/lsqr. Classification can set text_classifier=logistic and text_C=1, or separately test the SGD path. Keep the strong boosting control.',
    limitation='The engine key is linear_text, not ridge or logistic. No nested HPO support for this engine. Bound transformed size/fit cost and check row/class/probability output before admission.'),
 'linear_text':dict(id='linear_text',engines=['linear_text'],
    use_when='Schema discovery identifies actual long-text features and a sparse text representation is appropriate.',
    preparation='Use the existing fitting-only sparse text tool. The same tool also supports numeric/category-only data; use the tabular instruction card when no text features are present.',
    experiment='Compare under the same time/group partitions and complete output contract.',
    limitation='Do not request this engine for ordinary categorical/numeric tables solely because it is linear.'),
 'feature_preparation':dict(id='feature_preparation',engines=[],
    use_when='The task has missingness, categorical columns or a documented temporal structure.',
    preparation='Keep original features. Test engineered features separately; target encodings and selectors must refit inside each fitting partition.',
    experiment='Separate features, sampling and class weights into distinguishable experiments.',
    limitation='Target/ID access, external data and changes to validation are forbidden.'),
 'validation_and_budget':dict(id='validation_and_budget',engines=[],
    use_when='Every experiment, especially imbalanced classes, duplicate patterns or future-period tasks.',
    preparation='Use the fixed declared evaluator/partitions, class order and resource limits.',
    experiment='Check per-cut metrics, supported-class losses, rarest-class contribution, actual fit cost and final CSV/refit.',
    limitation='Remaining time is advisory context; only the coordinator can admit jobs. Reused search metrics are not official/private scores.')}

def select_method_skills(spec,capabilities,remaining_seconds,export_reserve_seconds):
    if spec.get('kind') not in {'classification','regression'} or spec.get('task_family')=='pointwise_ranking':
        raise ValueError('Method-skill pilot supports ordinary supervised tasks only')
    if type(capabilities) is not dict or len(capabilities)>64:
        raise ValueError('Trusted bounded capability registry required')
    for value in [remaining_seconds,export_reserve_seconds]:
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise ValueError('Finite actual remaining/reserved time required')
    allowed={'lightgbm','catboost','xgboost','extra_trees','linear_text'}
    ready=[engine for engine in sorted(allowed&set(capabilities))
        if spec['kind'] in capabilities[engine].get('kinds',[])]
    names=[]
    if any(e in ready for e in ['lightgbm','catboost','xgboost']):names.append('boosting')
    if 'extra_trees' in ready and not spec.get('text_features'):names.append('extra_trees')
    if 'linear_text' in ready:names.append('linear_text' if spec.get('text_features') else 'linear_tabular')
    names+=['feature_preparation','validation_and_budget']
    cards=[]
    for name in names:
        card=dict(CARDS[name]);card['engines']=[e for e in card['engines'] if e in ready]
        cards.append(card)
    packet=dict(version='method-skills-v1',selection='Deterministic retrieval from task kind/text and actual tool registry; Qwen chooses experiments within those tools.',
        implemented_tools=ready,selected_cards=cards,
        unavailable_AutoML_neural_tools='LightAutoML/FLAML/NN are not exposed until their adapters, gates and budgets are actually ready. Ridge/LogisticRegression already exist through the registered linear_text tool, without dedicated engine keys.',
        usable_search_seconds=max(0,int(remaining_seconds-export_reserve_seconds)),
        authority='Instructions only. Does not modify portfolio, metric, splits, model parameters, HPO or job caps.')
    raw=json.dumps(packet,ensure_ascii=False,allow_nan=False).encode('utf-8')
    if len(cards)>MAX_CARDS or len(raw)>MAX_PACKET_BYTES:raise ValueError('Method skill packet overflow')
    return packet,dict(status='method_skills_selected',packet_sha256=hashlib.sha256(raw).hexdigest(),
        packet_UTF8_bytes=len(raw),card_ids=names,tool_names=ready,
        model_fits=0,API_calls=0,quality_metric=None)

def attach_method_skills(context,spec,capabilities,remaining_seconds,export_reserve_seconds):
    if 'method_skills' in context:raise ValueError('Method skill field already present')
    packet,receipt=select_method_skills(spec,capabilities,remaining_seconds,export_reserve_seconds)
    # Preserve the exact inherited objects; this adds one bounded field only.
    return dict(context,method_skills=packet),receipt
