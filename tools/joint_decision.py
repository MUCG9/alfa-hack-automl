"""Dev-only constrained factors AFTER an already calibrated full ensemble."""
import numpy as np
from sklearn.metrics import f1_score

GRIDS={'JOINT_TIGHT':[.95,1.,1.05],'JOINT_NARROW':[.9,.95,1.,1.05,1.1]}


def safety(base,candidate,support):
    delta=np.asarray(candidate)-np.asarray(base);support=np.asarray(support);rare=int(np.argmin(support))
    primary=float(np.mean(candidate)-np.mean(base));without=float(np.delete(delta,rare).mean())
    violations=np.flatnonzero((support>=100)&(delta<-.01-1e-12)).tolist()
    return {'passed':primary>0 and without>0 and not violations,'oriented_gain':primary,
            'gain_without_rarest':without,'rarest_position':rare,'supported_violation_positions':violations}


def fit_factors(truth,probabilities,classes,support,operation):
    classes=np.asarray(classes,dtype=str);truth=np.asarray(truth,dtype=str);p=np.asarray(probabilities,dtype=float)
    if operation not in GRIDS:raise ValueError('Unknown constrained grid')
    if (classes.ndim!=1 or len(classes)<2 or len(set(classes))!=len(classes) or p.shape!=(len(truth),len(classes))
            or not len(truth) or not np.isfinite(p).all() or (p<0).any() or (p>1).any() or not np.allclose(p.sum(axis=1),1,atol=1e-7,rtol=1e-7)):
        raise ValueError('Aligned finite normalized probabilities/classes required')
    if set(support)!=set(classes) or any(type(v) is not int or v<0 for v in support.values()):raise ValueError('Independent fitting-group support required')
    lookup={c:i for i,c in enumerate(classes)}
    if not set(truth)<=set(classes):raise ValueError('Unknown fitting label')
    counts=np.asarray([support[c] for c in classes]);k=len(classes)
    def score(factors):
        return f1_score(truth,classes[(p*factors).argmax(axis=1)],labels=classes,average=None,zero_division=0)
    factors=np.ones(k);base=score(factors);best=float(base.mean());steps=[]
    for pass_number in range(2):
        changed=False
        for column in range(k):
            step={'pass':pass_number,'column':str(classes[column]),'starting_factors':factors.tolist(),'candidates':[]}
            chosen=factors.copy();chosen_score=best
            for value in GRIDS[operation]:
                trial=factors.copy();trial[column]=value;per_class=score(trial)
                objective=float(per_class.mean()-.004*np.square(np.log(trial)).mean());gate=safety(base,per_class,counts)
                step['candidates'].append({'factor':value,'per_class_f1':dict(zip(classes,map(float,per_class))),
                    'objective':objective,'gate':gate})
                if gate['passed'] and objective>chosen_score:
                    chosen=trial;chosen_score=objective
            if chosen_score>best+.0005:
                factors=chosen;best=chosen_score;changed=True
            step.update(selected_factors=factors.tolist(),selected_objective=best);steps.append(step)
        if not changed:break
    selected=score(factors)
    return {'operation_id':operation,'grid':GRIDS[operation],'classes':classes.tolist(),
        'factors':dict(zip(classes,map(float,factors))),'baseline_per_class_f1':dict(zip(classes,map(float,base))),
        'selected_per_class_f1':dict(zip(classes,map(float,selected))),'regularized_inner_value':best,
        'status':'identity' if np.array_equal(factors,np.ones(k)) else 'learned','history':steps,
        'independent_inner_fitting_groups':support,'calibration_rows':len(truth)}
