"""Structural checks of semantic file roles; never reinterpret the ML objective."""
import pandas as pd


class RoleContractError(ValueError):
    """Safe schema-only feedback; messages must not contain raw row values."""


def validate_role_tables(tables):
    train,test,sample,dictionary=(tables[n] for n in ['train','test','sample','dictionary'])
    if len(sample)!=len(test): raise RoleContractError('Selected sample/test row counts differ')
    if 'role' in dictionary and 'feature' not in dictionary:
        raise RoleContractError('Selected dictionary has roles but lacks its feature column')
    roles=dictionary['role'].astype(str).str.strip().str.lower() if 'role' in dictionary else pd.Series(dtype=str)
    targets=dictionary.loc[roles.eq('target'),'feature'].tolist() if len(roles) else []
    if not targets or any(c not in train for c in targets): targets=[c for c in train if c not in test]
    if not targets: raise RoleContractError('Selected fitting table has no identifiable target columns')
    all_ids=dictionary.loc[roles.eq('id'),'feature'].tolist() if len(roles) else []
    ids=[c for c in all_ids if c in sample and c in test and c not in targets]
    if not ids: ids=[c for c in sample if c in test and c not in targets]
    if len(ids)>1: raise RoleContractError('Selected sample/test have ambiguous identifier columns')
    features=[c for c in test if c in train and c not in set(all_ids+ids+targets)]
    if not features: raise RoleContractError('Selected fitting/test tables have no common predictor columns')
    if ids:
        identifier=ids[0]
        if test[identifier].isna().any() or test[identifier].duplicated().any():
            raise RoleContractError('Selected test identifiers are missing or duplicated')
        if sample[identifier].isna().any() or sample[identifier].duplicated().any():
            raise RoleContractError('Selected sample identifiers are missing or duplicated')
        if (pd.Index(test[identifier]).get_indexer(sample[identifier])<0).any():
            raise RoleContractError('Selected sample/test identifier values do not match')
