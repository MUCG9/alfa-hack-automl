"""Independent pinned-LAMA boundary, with no data/model dependencies."""
from dataclasses import dataclass
import math
from automl.contracts.messages import TaskSpec,SplitPlan


@dataclass(frozen=True)
class LamaRequest:
    task:TaskSpec
    categorical_features:tuple[str,...]
    classes:tuple[str,...]
    fitting_rows:tuple[int,...]
    inner_training_rows:tuple[int,...]
    inner_validation_rows:tuple[int,...]
    evaluation_rows:tuple[int,...]
    seconds:float=165.
    iterations:int=400
    threads:int=2

    def validate(self,size):
        if self.task.kind not in ('classification','regression') or self.task.metric not in ('macro_f1','rmse'):
            raise ValueError('LAMA pilot supports MacroF1/RMSE only')
        SplitPlan(self.fitting_rows,self.evaluation_rows).validate(size)
        SplitPlan(self.inner_training_rows,self.inner_validation_rows).validate(size)
        if not set(self.inner_training_rows+self.inner_validation_rows)<=set(self.fitting_rows):
            raise ValueError('Inner rows outside fitting partition')
        if not set(self.categorical_features)<=set(self.task.features):raise ValueError('Unknown category')
        if len(set(self.classes))!=len(self.classes) or (self.task.kind=='classification')!=bool(self.classes):
            raise ValueError('Explicit class order required')
        if type(self.seconds) not in (int,float) or not math.isfinite(self.seconds) or not 5<=self.seconds<=10800:
            raise ValueError('Finite LAMA deadline required')
        if type(self.iterations) is not int or not 1<=self.iterations<=400 or type(self.threads) is not int or not 1<=self.threads<=8:
            raise ValueError('Invalid LAMA resource cap')


@dataclass(frozen=True)
class LamaResult:
    evaluation_prediction:object
    evaluation_probabilities:object
    test_prediction:object
    test_probabilities:object
    classes:tuple[str,...]
    best_iteration:int
    seconds:float
    full_fit_ok:bool
    metadata:dict
