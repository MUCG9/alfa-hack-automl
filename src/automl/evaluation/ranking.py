"""Mean query-wise NDCG with tie averaging and explicit relevance gain semantics."""
import numpy as np
import pandas as pd


class NDCGByQuery:
    def __init__(self,groups,top_k=None,gain='linear'):
        groups=np.asarray(groups)
        if groups.ndim!=1 or not len(groups): raise ValueError('NDCG requires aligned query groups')
        codes,_=pd.factorize(groups,sort=False)
        if (codes<0).any(): raise ValueError('NDCG query groups cannot be missing')
        if top_k is not None and (isinstance(top_k,bool) or not isinstance(top_k,(int,np.integer)) or top_k<1):
            raise ValueError('NDCG top-k must be a positive integer')
        if gain not in {'linear','exponential'}: raise ValueError('Unsupported NDCG relevance gain')
        self.order=np.argsort(codes,kind='stable'); ordered=codes[self.order]
        edges=np.r_[0,np.flatnonzero(np.diff(ordered))+1,len(groups)]
        self.parts=[self.order[a:b] for a,b in zip(edges[:-1],edges[1:])]
        self.top_k=top_k; self.gain=gain; self.truth=None; self.gains=None; self.ideal=None
        largest=max(map(len,self.parts))
        self.discount=1/np.log2(np.arange(largest)+2.)

    def __call__(self,y,pred):
        y=np.asarray(y,dtype=float); pred=np.asarray(pred,dtype=float)
        if y.shape!=(len(self.order),) or pred.shape!=y.shape or not np.isfinite(y).all() or not np.isfinite(pred).all():
            raise ValueError('Invalid NDCG truth/prediction shape or values')
        if (y<0).any(): raise ValueError('NDCG relevance must be non-negative')
        if self.gain=='exponential' and y.max()>50: raise ValueError('Exponential relevance exceeds supported finite grade range')
        if self.truth is None or not np.array_equal(self.truth,y):
            self.truth=y.copy(); self.gains=np.expm1(y*np.log(2.)) if self.gain=='exponential' else y.copy()
            self.ideal=[]
            for rows in self.parts:
                width=len(rows) if self.top_k is None else min(len(rows),self.top_k)
                self.ideal.append(float(np.dot(np.sort(self.gains[rows])[::-1][:width],self.discount[:width])))
        scores=[]
        for rows,ideal in zip(self.parts,self.ideal):
            if ideal==0: scores.append(0.); continue
            order=np.argsort(-pred[rows],kind='stable'); values=self.gains[rows][order]; predicted=pred[rows][order]
            if len(rows)>1 and np.any(np.diff(predicted)==0):
                starts=np.r_[0,np.flatnonzero(np.diff(predicted)!=0)+1]
                counts=np.diff(np.r_[starts,len(rows)])
                values=np.repeat(np.add.reduceat(values,starts)/counts,counts)
            width=len(rows) if self.top_k is None else min(len(rows),self.top_k)
            scores.append(float(np.dot(values[:width],self.discount[:width])/ideal))
        return float(np.mean(scores))


def metric_context(spec,frame,rows):
    if spec.get('task_family')!='pointwise_ranking': return {}
    return {'groups':frame[spec['group_column']].iloc[rows].to_numpy(),
            'top_k':spec.get('ranking_k'),'gain':spec.get('ranking_gain','linear')}
