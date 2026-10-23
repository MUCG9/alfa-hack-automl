"""Pure preflight for a future one-factor OFF/ON generation pair; no gateway.
Both complete views are checked before either logical API call is permitted by
the later harness. Runtime default OFF is not routed through this screen helper.
"""
from copy import deepcopy
from automl.search.class_support import (PreparationBudget,ContextRejected,validate_task,
    validate_fitting_rows,validate_support_packet,bounded_messages,bounded_context_copy,add_support_context)


def prepare_generation_pair(system_prompt,base_context,spec,support,records,
                            primary_bindings,signature_fn,fitting_rows,budget=None):
    """An optional shared budget retains prior support/capture wall and IO.
    Without one, this function bounds only work since screen entry. The future
    parent must still charge all earlier preparation; this is not a free reset.
    """
    supplied_budget=budget is not None
    if supplied_budget and not isinstance(budget,PreparationBudget):
        raise ContextRejected('preparation_budget_type_required')
    budget=budget if supplied_budget else PreparationBudget()
    validate_task(spec);validate_fitting_rows(fitting_rows)
    support=validate_support_packet(spec,support,budget)
    if sum(support['raw_fitting_rows_per_class'].values())!=fitting_rows:
        raise ContextRejected('screen_fitting_row_snapshot_mismatch')
    # OFF receives exactly the inherited saved context; no arm marker is sent.
    off_receipt=bounded_messages(system_prompt,base_context,budget)
    off=bounded_context_copy(base_context,budget)
    on,packet_receipt=add_support_context(base_context,spec,support,records,primary_bindings,signature_fn,budget)
    on_receipt=bounded_messages(system_prompt,on,budget)
    restored=deepcopy(on);restored.pop('class_support',None)
    for row in restored.get('feedback_read_first',[]):row.pop('protected_control_comparison',None)
    if restored!=off:raise ContextRejected('OFF_ON_changed_more_than_declared_packet')
    return dict(OFF=off,ON=on),dict(status='both_views_preflighted_no_API',
        factor='fitting support plus lineage-bound primary-relative diagnostics only',
        OFF=off_receipt,ON=on_receipt,packet=packet_receipt,
        future_shared_parent_accounting_required=True,
        preparation_budget_scope='caller_supplied_cumulative_budget' if supplied_budget else 'screen_entry_only',
        earlier_support_capture_requires_same_budget_or_parent_accounting=True,
        class_count=len(spec['classes']),fitting_rows=fitting_rows,
        no_API_until_both_views_and_inputs_frozen=True,**budget.receipt())
