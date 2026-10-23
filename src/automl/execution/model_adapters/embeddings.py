"""CPU learned categorical embeddings with fitting-local preprocessing/refit."""
import time
import numpy as np
import pandas as pd
from automl.contracts.embeddings import EmbeddingRequest,EmbeddingResult
from automl.evaluation.api import evaluate


class Encoder:
    def __init__(self,features,categorical):
        self.features=tuple(features);self.categorical=tuple(categorical)
        self.numeric=tuple(c for c in features if c not in categorical)

    def fit(self,frame):
        numeric=frame[list(self.numeric)].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
        self.median=numeric.median().fillna(0.)
        self.scale=(numeric.quantile(.75)-numeric.quantile(.25)).fillna(1.).replace(0.,1.)
        self.vocab={c:{str(value):i+1 for i,value in enumerate(frame[c].dropna().astype(str).value_counts().head(1024).index)} for c in self.categorical}
        return self

    def transform(self,frame):
        value=frame[list(self.numeric)].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
        missing=value.isna().to_numpy(dtype=np.float32)
        scaled=((value.fillna(self.median)-self.median)/self.scale).clip(-10,10).to_numpy(dtype=np.float32)
        numeric=np.concatenate([scaled,missing],axis=1)
        categories=np.column_stack([frame[c].map(lambda v:self.vocab[c].get(str(v),0) if pd.notna(v) else 0).to_numpy(dtype=np.int64) for c in self.categorical]) if self.categorical else np.empty((len(frame),0),dtype=np.int64)
        return numeric,categories


def fit_predict(request,train,test):
    import torch
    from torch import nn
    if not isinstance(request,EmbeddingRequest):raise ValueError('Typed embedding request required')
    if torch.__version__.split('+')[0]!='2.5.1':raise ValueError('Original Torch2.5.1 required')
    started=time.monotonic();deadline=started+request.seconds
    torch.set_num_threads(request.threads)
    torch.use_deterministic_algorithms(True)
    features=request.task.features
    if request.task.target in features or request.task.identifier in features:raise ValueError('Forbidden feature role')
    if max(request.fitting_rows+request.evaluation_rows)>=len(train):raise ValueError('Row exceeds dataset')
    target=train[request.task.target]
    classification=request.task.kind=='classification'
    if classification:
        mapping={label:i for i,label in enumerate(request.classes)}
        y=target.astype(str).map(mapping)
        if y.isna().any() or set(target.iloc[list(request.inner_training_rows)].astype(str))!=set(request.classes):
            raise ValueError('Unknown/missing fitting class')
        y=y.to_numpy(dtype=np.int64)
    else:
        y=pd.to_numeric(target,errors='raise').to_numpy(dtype=np.float32)
        if not np.isfinite(y).all():raise ValueError('Nonfinite regression target')

    class Network(nn.Module):
        def __init__(self,encoder):
            super().__init__()
            cards=[len(encoder.vocab[c])+1 for c in encoder.categorical]
            dimensions=[min(16,max(2,round(2*c**.25))) for c in cards]
            self.embeddings=nn.ModuleList([nn.Embedding(c,d) for c,d in zip(cards,dimensions)])
            width=2*len(encoder.numeric)+sum(dimensions)
            if width==0:raise ValueError('At least one feature required')
            self.head=nn.Sequential(nn.Linear(width,128),nn.LayerNorm(128),nn.ReLU(),nn.Dropout(.1),
                                    nn.Linear(128,64),nn.ReLU(),nn.Linear(64,len(request.classes) if classification else 1))
        def forward(self,numeric,categorical):
            value=torch.cat([numeric]+[layer(categorical[:,i]) for i,layer in enumerate(self.embeddings)],dim=1)
            return self.head(value)

    def setup(rows):
        torch.manual_seed(request.seed)
        encoder=Encoder(features,request.categorical_features).fit(train.iloc[rows])
        numeric,categorical=encoder.transform(train)
        net=Network(encoder)
        if sum(p.numel() for p in net.parameters())>2_000_000:raise ValueError('Embedding parameter guard')
        center,scale=(0.,1.) if classification else (float(y[rows].mean()),max(float(y[rows].std()),1e-6))
        values=y if classification else (y-center)/scale
        return encoder,net,torch.tensor(numeric),torch.tensor(categorical),torch.tensor(values),center,scale

    def train_epoch(net,numeric,categorical,values,rows,optimizer):
        net.train()
        order=torch.tensor(rows)[torch.randperm(len(rows))]
        for batch in order.split(512):
            if time.monotonic()>=deadline:raise TimeoutError('Embedding fitting deadline exceeded')
            optimizer.zero_grad(set_to_none=True)
            output=net(numeric[batch],categorical[batch])
            loss=nn.functional.cross_entropy(output,values[batch]) if classification else nn.functional.mse_loss(output[:,0],values[batch])
            if not torch.isfinite(loss):raise ValueError('Nonfinite embedding loss')
            loss.backward();nn.utils.clip_grad_norm_(net.parameters(),5.);optimizer.step()

    def infer(net,numeric,categorical,center,scale):
        net.eval();outputs=[]
        with torch.no_grad():
            for a,b in zip(numeric.split(2048),categorical.split(2048)):
                if time.monotonic()>=deadline:raise TimeoutError('Embedding inference deadline exceeded')
                value=net(a,b)
                outputs.append((torch.softmax(value,dim=1) if classification else value[:,0]*scale+center).numpy())
        matrix=np.concatenate(outputs)
        if not np.isfinite(matrix).all():raise ValueError('Nonfinite embedding predictions')
        return (np.asarray(request.classes)[matrix.argmax(axis=1)],matrix) if classification else (matrix,None)

    rows=list(request.inner_training_rows);stop=list(request.inner_validation_rows)
    encoder,net,numeric,categorical,values,center,scale=setup(rows)
    inner_vocab_sizes={c:len(v) for c,v in encoder.vocab.items()}
    optimizer=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
    best=None;best_epoch=0;stale=0
    for epoch in range(1,request.epochs+1):
        train_epoch(net,numeric,categorical,values,rows,optimizer)
        predicted,probs=infer(net,numeric[stop],categorical[stop],center,scale)
        score=evaluate(target.iloc[stop],predicted,request.task.kind,request.task.metric,probs,list(request.classes) or None)[request.task.metric]
        if best is None or (score>best if request.task.greater_is_better else score<best):best=float(score);best_epoch=epoch;stale=0
        else:stale+=1
        if stale>=4:break
        if time.monotonic()-started>request.seconds*.55:break
    if best_epoch<1:raise ValueError('No complete embedding epoch')
    # Fresh model, vocabulary, numeric and target statistics on outer-fitting rows.
    rows=list(request.fitting_rows)
    encoder,net,numeric,categorical,values,center,scale=setup(rows)
    optimizer=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
    for _ in range(best_epoch):train_epoch(net,numeric,categorical,values,rows,optimizer)
    evaluation=list(request.evaluation_rows)
    prediction,probabilities=infer(net,numeric[evaluation],categorical[evaluation],center,scale)
    a,b=encoder.transform(test)
    test_prediction,test_probabilities=infer(net,torch.tensor(a),torch.tensor(b),center,scale)
    return EmbeddingResult('ok',prediction,probabilities,test_prediction,test_probabilities,request.classes,
        best_epoch,time.monotonic()-started,True,{'torch_version':torch.__version__,'device':'cpu',
        'inner_best_metric':best,'inner_vocab_sizes':inner_vocab_sizes,'outer_vocab_sizes':{c:len(v) for c,v in encoder.vocab.items()},
        'target_center':center,'target_scale':scale,'refit_epochs':best_epoch,'stopping_source':'inner_fitting_only',
        'parameters':sum(p.numel() for p in net.parameters()),'sampling':'identity','class_weights':'none','pretrained':False})
