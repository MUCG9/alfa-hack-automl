"""Experimental CPU embedding jobs; standard-library-only boundary."""
from dataclasses import dataclass
import math
from automl.contracts.messages import TaskSpec


@dataclass(frozen=True)
class EmbeddingRequest:
    task:TaskSpec
    categorical_features:tuple[str,...]
    classes:tuple[str,...]
    fitting_rows:tuple[int,...]
    inner_training_rows:tuple[int,...]
    inner_validation_rows:tuple[int,...]
    evaluation_rows:tuple[int,...]
    seconds:float=120.
    epochs:int=20
    threads:int=2
    seed:int=42

    def __post_init__(self):
        if self.task.kind not in ('classification','regression'):raise ValueError('Unsupported embedding task')
        if not set(self.categorical_features)<=set(self.task.features):raise ValueError('Unknown categorical feature')
        if len(set(self.categorical_features))!=len(self.categorical_features):raise ValueError('Duplicate categorical feature')
        if (self.task.kind=='classification')!=bool(self.classes) or len(set(self.classes))!=len(self.classes):
            raise ValueError('Declared class order required for classification only')
        for name in ('fitting_rows','inner_training_rows','inner_validation_rows','evaluation_rows'):
            rows=getattr(self,name)
            if not isinstance(rows,tuple) or not rows or any(type(r) is not int or r<0 for r in rows) or len(set(rows))!=len(rows):
                raise ValueError('Unique nonnegative integer row positions required')
        fitting=set(self.fitting_rows);inner=set(self.inner_training_rows);stop=set(self.inner_validation_rows)
        if not inner.isdisjoint(stop) or not inner|stop<=fitting or not fitting.isdisjoint(self.evaluation_rows):
            raise ValueError('Fitting/inner/evaluation isolation violated')
        if type(self.epochs) is not int or not 1<=self.epochs<=20 or type(self.threads) is not int or not 1<=self.threads<=8:
            raise ValueError('Invalid embedding resource cap')
        if type(self.seconds) not in (int,float) or not math.isfinite(self.seconds) or not 5<=self.seconds<=10800:
            raise ValueError('Finite bounded embedding deadline required')
        if type(self.seed) is not int or not 0<=self.seed<2**31:raise ValueError('Invalid embedding seed')


@dataclass(frozen=True)
class EmbeddingResult:
    status:str
    evaluation_prediction:object
    evaluation_probabilities:object
    test_prediction:object
    test_probabilities:object
    classes:tuple[str,...]
    best_epoch:int
    seconds:float
    full_fit_ok:bool
    metadata:dict
