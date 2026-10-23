"""Aggregate-only application assistants; no model/API/data dependencies."""
from dataclasses import dataclass
import math
import re


@dataclass(frozen=True)
class MetricEvidence:
    reference:str
    value:float

    def __post_init__(self):
        if not isinstance(self.reference,str) or not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,80}',self.reference):
            raise ValueError('Bounded aggregate reference required, not prose/rows')
        if type(self.value) not in (float,int) or not math.isfinite(self.value):
            raise ValueError('Finite aggregate evidence required')


@dataclass(frozen=True)
class AssistantRequest:
    kind:str
    metric:str
    evidence:tuple[MetricEvidence,...]
    incumbent_json:str
    catalog_json:tuple[str,...]

    def __post_init__(self):
        if (self.kind,self.metric) not in (('classification','macro_f1'),('regression','rmse')):
            raise ValueError('Unsupported assistant objective')
        if not isinstance(self.evidence,tuple) or not 1<=len(self.evidence)<=24 or any(not isinstance(v,MetricEvidence) for v in self.evidence):
            raise ValueError('Bounded typed aggregate evidence required')
        if len({e.reference for e in self.evidence})!=len(self.evidence):raise ValueError('Duplicate evidence reference')
        if not isinstance(self.incumbent_json,str) or len(self.incumbent_json)>24000:
            raise ValueError('Bounded immutable incumbent JSON required')
        if not isinstance(self.catalog_json,tuple) or not 1<=len(self.catalog_json)<=8 or any(not isinstance(v,str) or len(v)>24000 for v in self.catalog_json):
            raise ValueError('Finite immutable recipe catalog required')


@dataclass(frozen=True)
class AssistantResult:
    status:str
    selected_ids:tuple[str,...]=()
    recipe_json:tuple[str,...]=()
    diagnosis:object=None
    roles_completed:int=0
