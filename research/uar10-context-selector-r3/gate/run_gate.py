"""Fixed prospective UAR10 context/selector technical gate; no READY clock."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, re, shutil, sys, tempfile, time
sys.dont_write_bytecode=True
COMMON,PARENT,CHILD,FINAL,ROOT_CLOSE,MINIMUM_REMAINING=1200,900,840,180,60,1140
HELPERS={'coordinator':'bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76',
 'sampling':'d65ee39eb80c9fc4590cbbf474ee6c09e84cb65abe2d2c367ebcfa415a390cf0',
 'owner':'8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
 'processes':'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d',
 'lock':'78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
 'awake':'9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'}
BASE_SHA='c3e87a486e0b4bdd9a2189dd6151e6871d838923f04efde1f884cf0fda7d9ae3'

# Exact source-derived target constants; NOT actual root integration or runtime qualification.
FINAL_SOURCE_SCRIPTS=66
FINAL_SOURCE_CHECKS=704
FINAL_FLAT_MEMBERS=78
PACKET=Path(__file__).resolve().parent;WORK=PACKET.parent;OUT=PACKET/'attempt-r1'
C5_BASE_PATH=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
C5_BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
COMPOSITION_HANDOFF_SHA='1e08cd7915e067dc264fce5bcbe46ca2a770760b04843479f74511df5a263acf'
COMPOSITION_PEER_SHA='94b29ff1f4370f7167ffda71d27ec5316e85ee6698a88b2a41726088963c0961'
COMPAT_HANDOFF_SHA='83dcc7a5e69b7896339e6b5a4ddcd30b122af32ae32698090dd3b1a4d5f2699b'
COMPAT_PEER_SHA='0c96d47bfa0117ff61b7f084cef9f1ec9f6e6d1ac174dea49c39049c786db85a'
COMPAT_REPLACEMENTS={'tests/test_uar_hpo_fair_reserve.py': {'before_sha256': '8bfe59fa6bd0114c3867e1ef426f1f155cd83fbe3ba90709a332046b903d5643', 'after_sha256': 'b51ce05a2533515647ec04f521828c6c23e223bf3d4dbbfc287191f05eaa7252', 'candidate_path': 'candidate/tests/test_uar_hpo_fair_reserve.py'}, 'tests/test_uar_loss_backend.py': {'before_sha256': 'b882f673692ef758f3505c456a98d5883d25a37a2d75f3e611c3958b9aa58a7f', 'after_sha256': '2240cef09e932130cd3d5350b02e2f5260b90f5b54259168695aa0936cced787', 'candidate_path': 'candidate/tests/test_uar_loss_backend.py'}}
NEW_SUITE_METHODS={'test_uar_fitting_context_builder.py': {'FitContextContracts.test_regression_reduces_only_aligned_fitting_vectors': '82a186f792b62e62290bb3b0107d413855a3f09a008508537c76554419f4273e', 'FitContextContracts.test_class_counts_do_not_accept_or_infer_nonfitting_classes': '19e3c8bfa546f30f1299ff98d075a40b51b78f7a54640651b870817de2f7667a', 'FitContextContracts.test_full_length_target_rejected_before_values_are_inspected': '9e4532cf192c162ae27c1f8e21ae203094abcc3ebf0f74e7a3ad2fe00cacc2a4', 'FitContextContracts.test_target_and_ID_roles_rejected_before_feature_reduction': '2c034ea5a52023d5c5b93c6beb21758fcb4716cf96ebbf99a2b7edfd5787d2dd', 'FitContextContracts.test_positions_reject_duplicates_boolean_and_outside_rows': '10f4a81f1e11db97fae33164a40378090fe205b06e5281f0370affd3c2a2670a', 'FitContextContracts.test_closed_feature_mapping_and_vector_lengths': 'b797a6ea7409c81cf7f7f33c4640ce45a411ea4d3515ae7f0faeb365b52ed479', 'FitContextContracts.test_order_fingerprints_change_but_inputs_do_not_mutate': '8be96bc088ede9710f88d1b1f8114fd5b958cb064864d96a4168c8f0d62d569d', 'FitContextContracts.test_nonfinite_features_are_described_but_target_is_not_imputed': 'fae0c4186f873c7c9afa19696129ecb617e8b6320708b48e04d2f9a2c80ad9fb', 'FitContextContracts.test_cardinality_is_explicitly_lower_bounded_after_cap': '29bdb2cd5d6a51ec6aad0c1593164ce5a85de48f7618641ef3cd8b3d00734342', 'FitContextContracts.test_UTF8_packet_limit_is_measured_without_column_name_heuristics': '54cd8722c354c25b19a5ec13c90337795bcd4dde2ea1539c96d4fa1e1f331d71', 'FitContextContracts.test_separate_advice_copy_and_exact_gateway_serialization': '6d766ec1e7d9c3e501604de297d70f591aa96d8108bc52798813529752ba3711', 'FitContextContracts.test_receipt_recheck_shared_budget_and_complete_message_overflow': '46d81948e70a59e8979daf1ca439084b57026583bada54f1a96227299b383020'}, 'test_uar_fitting_extractor.py': {'FittingExtractorContracts.test_ordered_projection_reads_only_fitting_and_matches_statistics': '08dedcdd0a5b03595a91c79b34271d000ac47c9c53cf5ef4ec9ffdb16ffe8849', 'FittingExtractorContracts.test_poisoned_validation_unselected_and_unused_tail_never_read': 'bfe4910b85367d3f12e8bfa935416116f5532d4ab14eab4154e7aceb2d7e9b96', 'FittingExtractorContracts.test_ID_extra_test_or_unsupported_role_rejects_before_column_access': 'fbb5194de35727ffcc2fea640ef820f2ec789a005ad772f3f8d6689ea4ad64b9', 'FittingExtractorContracts.test_input_dictionary_roles_and_split_file_bindings_are_pre_read': 'f8fd61b2558da2363b67a7b4fccd1cd24b6bff35093ed438a11825802d62f066', 'FittingExtractorContracts.test_duplicates_boolean_outside_and_inner_relative_positions_reject': '838a875a89b02db20bea1c728d031274556ab040acb4cd8ada55fa589e8f8eca', 'FittingExtractorContracts.test_order_and_validation_disjointness_are_not_set_only_bindings': 'da79edeae5208717e9e448221577ba34501496e3abac681e53f41f300fcbc671', 'FittingExtractorContracts.test_column_shapes_all_checked_before_first_scalar': '716958fedb44690826a3c97936ff2b925da41c0901eeac969baf19893f9ceed5', 'FittingExtractorContracts.test_finite_scalar_and_no_target_imputation_policy': '3f24db70732577563202ef79fb231a1ce1e0583dc043446f1e3f66348b76b291', 'FittingExtractorContracts.test_class_labels_NA_and_001_are_lexical_and_no_outside_class': '6ae8b640ebd030048a3e0b614976f3e7461bd554dc9fbca829a092cfbd49cb47', 'FittingExtractorContracts.test_falsey_original_or_non_adapter_budget_rejects_without_reads': '789d96adf280cabd82010bf260a9991b999442fa64ad5ef8a59e9509e44b1058', 'FittingExtractorContracts.test_same_original_deadline_rollback_and_denial_are_sticky': '14240dd8405428d48dbea30ccc76e4e945c8dce5c0a05e4c9d33ec7cf9ebf102', 'FittingExtractorContracts.test_IO_counter_additive_limit_and_no_local_IO_or_clock': '0ff1e1ae8dedf7cea695f8d546f454de899d65f0f25d987a61a70c265242fa50', 'FittingExtractorContracts.test_scalar_and_projection_memory_limits_fail_without_truncation': '09b461417a3f19df38f5b202d0423a2e36535d26dab5251522c0b89b63044198', 'FittingExtractorContracts.test_renamed_unicode_schema_has_same_stats_and_UTF8_role_cap': '1c2ded7bdc0b7c22bcb5a523924035fc76b2a8a25b89d12d44bbed2d59c5ac1f', 'FittingExtractorContracts.test_packet_message_caps_reuse_existing_preflight_and_are_fresh': 'e6690c1202fc689ffe5dd17e9ab1784e6193dcacb23131cc414359e280e00634', 'FittingExtractorContracts.test_no_network_and_no_legacy_profile_or_advice_authority_surface': 'e13146dda837a6f021bb36dc1f0400a0f6cec6ecf6981194e4d2d6917ed63725'}, 'test_uar_fitting_frame.py': {'NativeFittingContracts.test_real_numpy_scalars_in_pandas_views_match_native_fitting_reductions': '83f49eb6694216416ee5d839188533bef77c46e6bed6fa00f1cefe83394a441b', 'NativeFittingContracts.test_pandas_string_labels_preserve_NA_001_without_unselected_label_leak': '6f927edc0a55bfe12cbbe0a9aef8ba9cc561f19b67edee21e8b7007551b3861d', 'NativeFittingContracts.test_native_missing_features_allowed_but_targets_and_infinite_values_reject': 'f083cdb32a03caed6aec8d7d223d565942445bba576ea1d51e4d6cda29c01931', 'NativeFittingContracts.test_numpy_bool_regression_and_non_scalar_objects_are_not_silently_coerced': '2a311781a0afca51960a43808166c271f1a4934241b8143a9e5ebaf69a1461d8', 'ValidatedFrameContracts.test_exact_frame_reuse_hash_IO_scope_and_original_RSS_no_parser_or_clock': '944548fb68eaf019d4eec98381602ccba3a159299c9f22bbe38921cfd841c08f', 'ValidatedFrameContracts.test_different_producer_objects_stop_before_fresh_hash_IO': 'a461cc5bf767fd40765fdad024437b1c6d6da26ea9f5fdcaa81d73587257fe0e', 'ValidatedFrameContracts.test_missing_resource_authority_or_unconfirmed_sample_never_starts_IO': '5d767bce670ec789bcfb4a627406f2aa42dcc802ae842a200b40f03702439e23', 'ValidatedFrameContracts.test_actual_input_hash_drift_and_post_projection_change_return_no_context': 'eee656aafc2e9e7dec6b1de3319820aab19be93c688078aa96a2025e3974449f', 'ValidatedFrameContracts.test_guard_denial_and_original_deadline_are_sticky_without_recovery': 'fa34d84a28d0cb460ae3f307a53c6baad33ede78bbd15026219da5dbe1abe3af', 'ValidatedFrameContracts.test_schema_role_and_original_position_witness_mismatches_fail_closed': '391eea531427f6500f082aa1edad99d378df94057add38d92550ff237cb47a9c'}, 'test_uar_fitting_context_initial.py': {'InitialFittingConsumerContracts.test_optin_requires_both_strict_modes_and_four_stage': 'ebfc00e3bd284e580910238685ea57c129c5aa5ca2e032cba2ef8a99a5d09ac7', 'InitialFittingConsumerContracts.test_direct_solver_without_live_authority_stops_before_discovery': '1b127d851d413ae381e1f41a0906a0d3ceccdc8ab15f5557dacb5c8a34d4b546', 'InitialFittingConsumerContracts.test_scoped_producer_authority_reset_is_in_finally': '26a0c066dcf50df190483dc3a29e1ddeaef69a3b56b660b88930a43be8fc5fb8', 'InitialFittingConsumerContracts.test_frame_and_original_budget_identity_are_required': 'ec525dfcf30c4014f7cccab93d0bf05d4925ad8e4e7990483ae0585c47ca8466', 'InitialFittingConsumerContracts.test_derived_validation_copy_allows_only_existing_four_fields': '43e193b6c44dc313eb43b1e6d08ae016d782179d54b33835dbfb59fc5885d306', 'InitialFittingConsumerContracts.test_mutated_strict_source_or_input_witness_rejects': '0698672c65d866ea4d08b2ac18ecb8f742d5f35eaa2d1296e659484afa21a879', 'InitialFittingConsumerContracts.test_unknown_metric_and_incompatible_resolved_objective_do_not_default': '9c5db5aacc85126153dfea1382c212dcf2d950a9725d55334d643ad2fd6a1125', 'InitialFittingConsumerContracts.test_original_row_order_preserved_and_invalid_indices_not_coerced': 'c58dd97535d8913f11c3097f019fc3977a61c5088b19553b5d67460b47b91856', 'InitialFittingConsumerContracts.test_fresh_context_itself_has_no_profile_split_feedback_or_retention_merge': 'bf4b4ada255b494f58821d09d435ebad317065d43ecb3dc6f785185a1ae67dbd', 'InitialFittingConsumerContracts.test_exact_prompt_and_packet_are_rechecked_immediately_before_request': 'b9d5c76e4daafe9cf18175dcee16f7efe0841ecd8935ad8c2e0994ccf8ca6438', 'InitialFittingConsumerContracts.test_packet_and_complete_message_UTF8_caps_fail_before_gateway': '40d685689874f9a6bdced55155f8615bf2e99dc36e96fbf45418d9a9ce513f3a', 'InitialFittingConsumerContracts.test_original_guard_failure_propagates_without_new_clock_or_request': 'ff769f275aa5888eb738d39651f47d5204388c6d50f728a5e2cb21e34e8fc1f5', 'InitialFittingConsumerContracts.test_gateway_arguments_unchanged_and_preflight_precedes_each_initial_call': 'd5da4bff516b4710ed5cfc4bae6b6711e53326329f381eda394b2db1703c2800', 'InitialFittingConsumerContracts.test_bounded_split_byte_read_and_no_gateway_parser_or_clock_owner': 'd7d6fb180509c40d563a0874ff91c12f8ff40fd83033124d6645cfc0495efece'}, 'test_teacher_importance_cache.py': {'TeacherCacheTests.test_default_off_fits_normally_and_does_not_compute_keys': '77e64ec515611920dc034d85b706b720f47830431ebe978fd11e5c4f4873ae6a', 'TeacherCacheTests.test_identical_actual_teacher_context_reuses_importances_and_preserves_outputs': 'c33f1632fc672df5ea82f33af11ffce494f414c67831e72312ca767aeadcfe94', 'TeacherCacheTests.test_nonfitting_values_labels_and_test_values_cannot_affect_key': 'fd6030ef1794d87e48243795200df3d385c8152cce83651faa9d114e194eaa13', 'TeacherCacheTests.test_each_teacher_input_or_scope_change_is_a_miss': '1b683a166858dd6df7de99c31d53d1607348a688c4a5a75e85076b1fd22dc9f8', 'TeacherCacheTests.test_library_identity_and_inner_outer_phase_cannot_share': '7014bb9fc8d33631cb9ff06c26fbe2b9e5230db51a003cd9c51724e566138a68', 'TeacherCacheTests.test_fresh_worker_cache_cannot_reuse_another_worker': 'c255f5246f0117f0c4057480eec82dce72ae0ae1223ee488a5ca5093fff34411', 'TeacherCacheTests.test_duplicate_content_on_different_row_positions_is_not_same_scope': 'a9e7179dd96c26cbb8c73260617ad3831033660045262b75b5047db9cebc52fd', 'TeacherCacheTests.test_only_importance_and_column_metadata_are_retained_and_copies_are_defensive': '531ed3c43f0dee9a29a8ab53f1695796783add4d041edbff550dd0d167329801', 'TeacherCacheTests.test_unsupported_exact_key_type_bypasses_without_changing_fit_behavior': '2eb6eed8cb77d868baa1b0fece55a4b8809607375d945cc2a6d60f2a71d69940', 'TeacherCacheTests.test_lru_entry_and_byte_bounds_and_nonfinite_rejection': 'ef60f4b49d82644d34e34c677a27c2921534215eca444429a57e2c671c9ee3de', 'TeacherCacheTests.test_opt_in_requires_explicit_scope_and_invalid_job_flag_fails_before_io': '8e972e2c64cd68fa84d293fc231bab2d1dbdd0e56352de4ad21b373d5b30083b', 'TeacherCacheTests.test_leaf_worker_matching_inner_refit_hits_but_outer_refit_does_not': '2e8972d06bc91c653409d540a558eff3cbdf0f5a90bb86bfc764c96b151a9159'}, 'test_selector_cache_consumer.py': {'SelectorCacheConsumerTests.test_real_strict_and_legacy_jobs_forward_only_explicit_scope': '4e281fb446c192140d51bec9fe7b06b379658fd5360cca55fad51e9928ec5ed7', 'SelectorCacheConsumerTests.test_plain_cli_defaults_off_and_explicit_cli_scope_restores_after_error': 'fd7540baa2dff37aa3dc1f8eab06e2cc41fd7f14754759b2dedf4fad073a39f2', 'SelectorCacheConsumerTests.test_invalid_trusted_scope_fails_before_job_write_or_child_launch': '9efc3f7b23ae6187610ac45f47c12d86af6d3345a8e3b6f8086db4d67a2b3c14', 'SelectorCacheConsumerTests.test_default_off_ignores_recipe_spec_environment_lookalikes': 'e887c64bdcbb9cddd871ae17f745240b18bc0c79a109ad75707ef5d1935447b8'}, 'test_uar_fitting_selector_combined.py': {'FittingSelectorInteractionContracts.test_four_independent_flag_combinations_use_real_scope_and_restore_after_exception': '59ba722fb83e076d12a9f5f821737bf0fcf7e5dafc76e2bccd555739803734f3', 'FittingSelectorInteractionContracts.test_followup_feedback_is_unchanged_and_never_relabelled_fitting_only': '68144866684083736e16c811fc7145b467f30e48da6a0b5349bf00b2770ac832'}}

HPO_TEST_PATH='tests/test_uar_hpo_fair_reserve.py'
HPO_METHODS=['FairReserveTests.test_numerical_REG300_and_missing_strict_reject_before_discovery_or_API', 'FairReserveTests.test_exact_anchor_feasibility_and_soft_equal_share_arithmetic', 'FairReserveTests.test_original_clock_invalid_rollback_and_deadline_remain_sticky', 'FairReserveTests.test_late_anchor_setup_stops_without_callback_or_fake_trial', 'FairReserveTests.test_share_recomputed_after_persist_does_not_launch_stale_proposal', 'FairReserveTests.test_eight_actual_callbacks_preserve_anchor_template_space_and_truthful_phases', 'FairReserveTests.test_ordinary_confirmed_timeout_is_null_consumes_slot_and_continues', 'FairReserveTests.test_actual_cleanup_overrun_stops_later_slots_without_reset_or_retry', 'FairReserveTests.test_resource_kill_late_cleanup_stays_timeout_but_parent_origin_forces_STOP', 'FairReserveTests.test_ordinary_late_clean_result_has_complete_nonresource_origin', 'FairReserveTests.test_original_cleanup_exception_propagates_and_trusted_scope_restores', 'FairReserveTests.test_missing_or_incomplete_parent_receipt_is_technical_STOP', 'FairReserveTests.test_resource_or_unknown_technical_origin_STOPs_without_extra_draw', 'FairReserveTests.test_duplicate_proposal_is_not_callback_or_valid_or_padding', 'FairReserveTests.test_final_save_crossing_original_deadline_cannot_return_ok', 'FairReserveTests.test_trusted_flag_cannot_be_enabled_by_recipe_context_and_scope_is_local', 'FairReserveTests.test_OFF_strict_worker_late_classification_does_not_add_provenance', 'FairReserveTests.test_default_OFF_whole_module_ASTs_match_independent_original_bases']
HPO_OFF_AST_METHOD='FairReserveTests.test_default_OFF_whole_module_ASTs_match_independent_original_bases'

def need(value,code):
    if not value:raise RuntimeError(code)

def read(path):return json.loads(Path(path).read_text('utf-8'))

def digest(path,pulse=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            pulse();block=stream.read(2**20)
            if not block:break
            h.update(block)
    pulse();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def config(path,expected,self_sha):
    need(all(type(v) is int and v>0 for v in (FINAL_SOURCE_SCRIPTS,FINAL_SOURCE_CHECKS,FINAL_FLAT_MEMBERS))
         and type(HPO_TEST_PATH) is str and re.fullmatch(r'tests/test_uar_[a-z0-9_]+\.py',HPO_TEST_PATH)
         and type(HPO_METHODS) is list and 1<=len(HPO_METHODS)<=256
         and len(HPO_METHODS)==len(set(HPO_METHODS)) and HPO_OFF_AST_METHOD in HPO_METHODS
         and all(type(v) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.test_[A-Za-z0-9_]+',v) for v in HPO_METHODS),
         'NOT_READY_exact_final_HPO_methods_and_combined_counts_required')
    need(Path(path).is_absolute() and Path(path).stat().st_size<=2**20,'bounded_absolute_manifest_required')
    need(digest(path)==expected,'private_manifest_changed');cfg=read(path)
    need(type(cfg) is dict and cfg.get('schema')=='uar-full-private-manifest-v1'
         and cfg.get('readiness')=='READY_FROZEN_SOURCE_REVIEWED' and cfg.get('missing_bindings')==[],
         'NOT_READY_combined_source_review_and_freeze_required')
    need(cfg.get('common_seconds')==COMMON,'exact_fresh_common1200_required')
    for key in ('work_root','canonical_root','python','output','lock_path','technical_entry','contracts','focused_helper'):
        need(type(cfg.get(key)) is str and Path(cfg[key]).is_absolute(),'all_forwarded_paths_must_be_absolute')
    root=Path(cfg['canonical_root']);work=Path(cfg['work_root']);packet=Path(__file__).resolve().parent
    need(root.resolve()==(work/'alfa-hack-automl').resolve()
         and Path(cfg['output']).resolve()==OUT
         and Path(cfg['technical_entry']).resolve()==packet/'technical_entry.py'
         and Path(cfg['contracts']).resolve()==packet/'contracts.py'
         and Path(cfg['focused_helper']).resolve()==work/'uar-focused-gate-next-dev/run_gate.py'
         and Path(cfg['lock_path']).resolve()==root/'test-runs/.owned-research.lock','fixed_gate_paths_required')
    pins=cfg.get('files_sha256')
    need(type(pins) is dict and 1<=len(pins)<=4096 and all(type(k) is str and Path(k).is_absolute()
        and type(v) is str and re.fullmatch('[0-9a-f]{64}',v) for k,v in pins.items()),'typed_frozen_hash_inventory')
    need(pins.get(str(Path(__file__).resolve()))==self_sha and digest(__file__)==self_sha,'driver_changed')
    need(pins.get(cfg['focused_helper'])==BASE_SHA,'proven_focused_helper_pin_required')
    for name,expected_sha in HELPERS.items():
        ref=cfg['helpers'][name];need(ref['sha256']==expected_sha and pins.get(ref['path'])==expected_sha
            and Path(ref['path']).is_absolute(),'proven_guard_changed')
    need(cfg['candidate_process_sha256']=='9f84f64199b63dc4cef095e026d23084e338f1e42a97d5b4bd083e10f687bdb3'
         and pins.get(str((root/'src/automl/infrastructure/processes.py').resolve()))==cfg['candidate_process_sha256'],
         'candidate_process_separate_from_historical_fac3_guard')
    need(pins.get(str((root/'src/automl/search/hpo.py').resolve()))==
         'e11ac8f7ca8b9c844b1524f4f3d43e95b91374ac214e75aacb873c3b4ed89d51',
         'current_reviewed_HPO_R3_runtime_required_no_R2_reuse')
    need(type(cfg.get('canonical_python_inventory')) is list and len(cfg['canonical_python_inventory'])<=2048
         and len(set(cfg['canonical_python_inventory']))==len(cfg['canonical_python_inventory'])
         and all(v in pins and Path(v).is_relative_to(root) for v in cfg['canonical_python_inventory']),
         'exact_canonical_python_inventory_required')
    need(type(cfg.get('registry')) is dict and type(cfg.get('flat_inventory')) is list,
         'actual_registry_and_flat_inventory_required')
    need(type(cfg.get('mapped_suites')) is list and len(cfg['mapped_suites'])==14,'bounded_mapped_whitelist_required')
    ids=[];testpaths=[]
    for suite in cfg['mapped_suites']:
        need(type(suite) is dict and set(suite)=={'id','test','test_relative_path','expected_tests','all_methods',
            'selected_methods','excluded_methods','exclusion_reason','source_review_ref'},'typed_mapped_suite_no_commands')
        rel=suite['test_relative_path'];need(type(rel) is str and re.fullmatch(r'tests/test_[a-z0-9_]+\.py',rel),
            'reviewed_uar_test_path_required')
        need(re.fullmatch('[a-z][a-z0-9_]{0,31}',suite['id']) and Path(suite['test']).is_absolute()
             and Path(suite['test']).resolve()==(root/rel).resolve() and suite['test'] in pins,'fixed_test_path_required')
        for name in ('all_methods','selected_methods','excluded_methods'):
            need(type(suite[name]) is list and len(suite[name])<=256
                 and len(set(suite[name]))==len(suite[name]) and all(type(v) is str and
                 re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.test_[A-Za-z0-9_]+',v) for v in suite[name]),
                 'explicit_qualified_method_whitelist_required')
        need(type(suite['expected_tests']) is int and 1<=suite['expected_tests']==len(suite['selected_methods'])<=256,
             'exact_selected_test_count_required')
        expected_exclusion=(['LossContractTests.test_default_OFF_all_six_modules_preserve_base_UAR_AST']
                            if rel=='tests/test_uar_loss_backend.py' else [HPO_OFF_AST_METHOD] if rel==HPO_TEST_PATH else [])
        if suite['excluded_methods']:
            need(rel in {'tests/test_uar_loss_backend.py',HPO_TEST_PATH} and suite['excluded_methods']==expected_exclusion
                 and suite['exclusion_reason']=='modular_source_AST_assertion_covered_by_full_source_not_flat',
                 'only_two_exact_predeclared_modular_source_AST_exclusions_allowed')
        else:need(suite['exclusion_reason'] is None,'unannounced_mapped_exclusion')
        ref=suite['source_review_ref'];need(type(ref) is dict and set(ref)=={'path','sha256'}
             and Path(ref['path']).is_absolute() and pins.get(ref['path'])==ref['sha256'],'actual_source_review_required')
        ids.append(suite['id'].casefold());testpaths.append(rel.casefold())
    mandatory={'tests/test_uar_early_declaration.py':(14,14),
               'tests/test_uar_vertical_contract.py':(14,14),
               'tests/test_uar_loss_backend.py':(17,16),
               'tests/test_uar_strong_retention.py':(15,15),
               'tests/test_uar_metric_contrast.py':(16,16),
               'tests/test_uar_task_checkpoint_cadence.py':(12,12)}
    need(HPO_TEST_PATH not in mandatory,'new_HPO_suite_path_must_be_unique')
    mandatory[HPO_TEST_PATH]=(len(HPO_METHODS),len(HPO_METHODS)-1)
    mandatory.update({'tests/test_uar_fitting_context_builder.py': (12, 12), 'tests/test_uar_fitting_extractor.py': (16, 16), 'tests/test_uar_fitting_frame.py': (10, 10), 'tests/test_uar_fitting_context_initial.py': (14, 14), 'tests/test_teacher_importance_cache.py': (12, 12), 'tests/test_selector_cache_consumer.py': (4, 4), 'tests/test_uar_fitting_selector_combined.py': (2, 2)})
    need(len(ids)==len(set(ids)) and len(testpaths)==len(set(testpaths)) and set(testpaths)==set(mandatory),
         'exact_fourteen_mandatory_mapped_suites_required')
    for suite in cfg['mapped_suites']:
        rel=suite['test_relative_path'];all_count,selected_count=mandatory[rel]
        need(len(suite['all_methods'])==all_count and suite['expected_tests']==selected_count
             and cfg['registry'].get(Path(rel).name)==all_count
             and suite['selected_methods']==[n for n in suite['all_methods'] if n not in suite['excluded_methods']],
             'mandatory_full_source_and_flat_coverage_required')
        if Path(rel).name in NEW_SUITE_METHODS:
            need(suite['all_methods']==list(NEW_SUITE_METHODS[Path(rel).name])
                 and suite['selected_methods']==suite['all_methods'] and suite['excluded_methods']==[],
                 'all70_new_method_names_mandatory_no_exclusions')
        if rel=='tests/test_uar_loss_backend.py':
            need(suite['excluded_methods']==
                 ['LossContractTests.test_default_OFF_all_six_modules_preserve_base_UAR_AST']
                 and suite['exclusion_reason']=='modular_source_AST_assertion_covered_by_full_source_not_flat',
                 'LOSS17_source_and_exact16_applicable_flat_required')
        elif rel==HPO_TEST_PATH:
            need(suite['all_methods']==HPO_METHODS
                 and suite['selected_methods']==[n for n in HPO_METHODS if n!=HPO_OFF_AST_METHOD]
                 and suite['excluded_methods']==[HPO_OFF_AST_METHOD]
                 and suite['exclusion_reason']=='modular_source_AST_assertion_covered_by_full_source_not_flat',
                 'HPO_all_source_and_exact_applicable_flat_methods_required')
        else:
            need(suite['excluded_methods']==[] and suite['exclusion_reason'] is None,
                 'all_IO03_vertical_retention_methods_mandatory')
    need(len(cfg['registry'])==FINAL_SOURCE_SCRIPTS and sum(cfg['registry'].values())==FINAL_SOURCE_CHECKS
         and len(cfg['flat_inventory'])==FINAL_FLAT_MEMBERS,'declared_final_combined_source_flat_counts_required')
    need(type(cfg.get('predecessors')) is list and any(r.get('id')=='uar03' and r.get('sha256')==
         'e86a151481b5b2849d9d0b6b4dc8ef6787a6ccf766dd97486b65de9d05cbf5d9' for r in cfg['predecessors']),
         'actual_UAR03_terminal_root_required')
    latest=[r for r in cfg['predecessors'] if r.get('id')=='uq2']
    need(cfg.get('latest_predecessor_id')=='cx2' and len(latest)==1
         and cfg.get('requires_whole_UQ2_terminal_and_fresh_closure') is True,
         'whole_UQ2_terminal_fresh_root_required_before_new_gate')
    ref=latest[0]
    need(Path(ref['path']).resolve()==work/'uq2-audit-close-repair-r1/terminal-root-closure.json'
         and ref.get('sha256')=='5c9bfc7f8f4f9c5d760e52963f89a4983172144698b7dd334d252a5dce18eabd'
         and ref.get('actual_exec_session')==3588 and type(ref.get('actual_exit_code')) is int
         and ref['actual_exit_code']==1 and ref.get('actual_tool_evidence')=='d7f40a'
         and pins.get(ref['path'])==ref['sha256'] and digest(ref['path'])==ref['sha256'],
         'exact_actual_UQ2_clean_negative_audit_root_required')
    admission=cfg.get('latest_UQ2_negative_audit')
    need(type(admission) is dict and set(admission)=={'schema','root_confirmation','helper_source','helper_review'}
         and admission['schema']=='uq2-clean-negative-root-admission-v1',
         'explicit_separate_negative_audit_confirmation_required')
    fixed={
        'root_confirmation':('uq2-audit-close-repair-r1/root-confirmation.json','ec6ee6b4e4e0452d787f69a8735edc4ea56da8d782fe1fd62210fbd1a222997e'),
        'helper_source':('uq2-audit-close-repair-next-dev/close_pair.py','45639bdbf9433588ffdda8145693d585b040a715b761215b1de5823ceb3b95aa'),
        'helper_review':('uq2-audit-close-repair-independent-review-r3.json','820834b95ab3ab5cd2e8b285701010de29d8d9dd239862fd448b59eba34b11b9')}
    for name,(relative,expected_sha) in fixed.items():
        receipt=admission[name]
        need(type(receipt) is dict and set(receipt)=={'path','sha256'}
             and Path(receipt['path']).is_absolute() and Path(receipt['path']).resolve()==work/relative
             and receipt['sha256']==expected_sha and pins.get(receipt['path'])==expected_sha
             and digest(receipt['path'])==expected_sha,'fixed_negative_audit_source_review_or_confirmation_changed')
    uq2_proof=read(ref['path']);confirmation=read(admission['root_confirmation']['path'])
    need(uq2_proof.get('schema')=='uq2-clean-negative-audit-root-closure-v1'
         and uq2_proof.get('cleanup_confirmed') is True and uq2_proof.get('source_unchanged') is True
         and uq2_proof.get('active_owned_processes')==[] and uq2_proof.get('uncertain_owned')==[]
         and uq2_proof.get('technical_procedure_passed') is False
         and uq2_proof.get('original_full_procedure_passed') is False
         and uq2_proof.get('original_global_qualification')=='FAIL'
         and uq2_proof.get('qualified_ML_metrics') is None
         and uq2_proof.get('audit_helper_source')==dict(path=fixed['helper_source'][0],sha256=fixed['helper_source'][1]),
         'clean_known_scope_must_not_relabel_UQ2_technical_or_ML_failure')
    need(confirmation.get('schema')=='uq2-negative-audit-root-exec-confirmation-v1'
         and confirmation.get('audit_root_sha256')==ref['sha256']
         and confirmation.get('audit_helper_sha256')==fixed['helper_source'][1]
         and confirmation.get('audit_actual_exec_session') is None
         and confirmation.get('audit_actual_exit')==0 and confirmation.get('audit_actual_tool')=='1d6371'
         and confirmation.get('campaign_actual_session')==3588 and confirmation.get('campaign_actual_exit')==1
         and confirmation.get('campaign_actual_tool')=='d7f40a'
         and confirmation.get('original_failed_closer_actual_exit')==1
         and confirmation.get('original_failed_closer_tool')=='80def1'
         and confirmation.get('known_exact_live')==[] and confirmation.get('uncertain')==[]
         and confirmation.get('root_and_closure_preparer_union_included') is True
         and confirmation.get('observed_root_cleanup_confirmed') is True
         and confirmation.get('observed_root_source_unchanged') is True
         and confirmation.get('technical_procedure_passed') is False
         and confirmation.get('original_UQ2_FAIL_preserved') is True
         and confirmation.get('original_closer_FAIL_preserved') is True
         and confirmation.get('old87_false_flags_unchanged') is True
         and confirmation.get('old87_unknown_leaf_not_retroqualified') is True,
         'actual_new_audit_exit0_fresh_confirmation_and_old_FAILURES_required')
    need(confirmation.get('original_deadline_unix')==1792836868.8239975
         and confirmation.get('original_deadline_monotonic')==95873.953
         and type(confirmation.get('checked_unix')) in (int,float) and math.isfinite(confirmation['checked_unix'])
         and type(confirmation.get('checked_monotonic')) in (int,float) and math.isfinite(confirmation['checked_monotonic'])
         and confirmation['checked_unix']<confirmation['original_deadline_unix']
         and confirmation['checked_monotonic']<confirmation['original_deadline_monotonic'],
         'separate_audit_confirmation_must_be_inside_its_original10800')
    def identity_set(rows):
        need(type(rows) is list and len(rows)<=20000,'bounded_exact_confirmation_identities_required')
        need(all(type(v) is dict and type(v.get('pid')) is int and v['pid']>0
             and type(v.get('create_time')) in (int,float) and math.isfinite(v['create_time'])
             and v['create_time']>0 for v in rows),'typed_confirmation_pid_birth_required')
        return {(v['pid'],v['create_time']) for v in rows}
    confirmed=identity_set(confirmation['known_identities'])
    need(len(confirmed)==confirmation.get('known_count')==6300
         and identity_set(uq2_proof['owned_identities']+uq2_proof['closure_preparer_identities'])<=confirmed,
         'negative_audit_root_and_new_preparers_must_be_in_actual_confirmed_union')
    # A current clean-negative root grants only known ownership closure, never prior technical PASS.
    u8=[r for r in cfg['predecessors'] if r.get('id')=='uar08_failed']
    need(len(u8)==1 and Path(u8[0]['path']).is_absolute()
         and Path(u8[0]['path']).resolve()==work/'uar08-combined-gate-next-dev/attempt-r1/terminal-root-closure.json'
         and u8[0].get('sha256')=='bca0d1bbdf1dba98b03ca17be3d8dd5a584e0d5cf72034073fc35f5fc32c3842'
         and u8[0].get('actual_exec_session')==68067 and type(u8[0].get('actual_exit_code')) is int
         and u8[0]['actual_exit_code']==1 and u8[0].get('actual_tool_evidence')=='848481'
         and pins.get(u8[0]['path'])==u8[0]['sha256'] and digest(u8[0]['path'])==u8[0]['sha256'],
         'actual_UAR08_clean_negative_root_required')
    current=cfg.get('latest_UAR08_negative')
    need(type(current) is dict and set(current)=={'schema','root_confirmation','closer_source','original_private_manifest'}
         and current['schema']=='uar08-clean-negative-root-admission-v1',
         'explicit_UAR08_negative_confirmation_and_original_closer_binding_required')
    fixed8={
        'root_confirmation':('uar08-combined-gate-next-dev/attempt-r1/root-confirmation.json','67942a2aa68e9757d590f36bf689bbe349751470de166690f7429801f0ae3f86'),
        'closer_source':('uar08-combined-gate-next-dev/close_gate.py','8d4c47a32a7a874a2982fc020b655d04341d0151895fc07dc529c746a67fc0fe'),
        'original_private_manifest':('uar08-combined-gate-next-dev/private-manifest-uar08-r1.json','4a1030bb2b987a746870fe99709d151ad6cd3d9f00abb7592a249194524c6141')}
    for name,(relative,expected_sha) in fixed8.items():
        value=current[name]
        need(type(value) is dict and set(value)=={'path','sha256'} and type(value['path']) is str
             and Path(value['path']).is_absolute() and Path(value['path']).resolve()==work/relative
             and value['sha256']==expected_sha and pins.get(value['path'])==expected_sha
             and digest(value['path'])==expected_sha,'fixed_UAR08_negative_evidence_changed')
    u8proof=read(u8[0]['path']);u8confirmation=read(current['root_confirmation']['path'])
    original8=read(current['original_private_manifest']['path'])
    need(u8proof.get('schema')=='uar-full-root-closure-v1'
         and u8proof.get('actual_exec_session')==68067
         and type(u8proof.get('actual_exec_exit_code_observed_by_root')) is int
         and u8proof['actual_exec_exit_code_observed_by_root']==1
         and u8proof.get('actual_tool_evidence')=='848481'
         and u8proof.get('cleanup_confirmed') is True and u8proof.get('source_unchanged') is True
         and u8proof.get('active_owned_processes')==[] and u8proof.get('uncertain_owned')==[]
         and u8proof.get('technical_procedure_passed') is False and u8proof.get('qualified_checks') is None
         and u8proof.get('private_manifest_sha256')==fixed8['original_private_manifest'][1]
         and original8.get('files_sha256',{}).get(current['closer_source']['path'])==fixed8['closer_source'][1],
         'UAR08_FAIL_and_original_closer_source_must_remain_bound')
    need(u8confirmation.get('schema')=='uar08-negative-root-exec-confirmation-v1'
         and u8confirmation.get('root_sha256')==u8[0]['sha256']
         and u8confirmation.get('gate_actual_exec')==dict(session=68067,exit_code=1,tool='848481')
         and u8confirmation.get('closer_actual_exec')==dict(session=None,exit_code=1,tool='fd47c3')
         and u8confirmation.get('known_count')==6649
         and u8confirmation.get('known_exact_live')==[] and u8confirmation.get('uncertain')==[]
         and u8confirmation.get('root_and_closure_preparer_union_included') is True
         and u8confirmation.get('metadata_and_prelaunch_preparers_included') is True
         and u8confirmation.get('cleanup_confirmed') is True and u8confirmation.get('source_unchanged') is True
         and u8confirmation.get('technical_procedure_passed') is False
         and u8confirmation.get('original_FAIL_preserved') is True,
         'actual_UAR08_gate_and_negative_closer_exits_fresh_union_required')
    observed8=identity_set(u8confirmation.get('known_identities'))
    need(len(observed8)==len(u8confirmation['known_identities'])==6649
         and identity_set(u8proof['owned_identities']+u8proof['closure_preparer_identities'])<=observed8,
         'all_UAR08_root_closer_and_five_extra_preparers_required')
    need(u8confirmation.get('original_deadline_unix')==1792836857.0601652
         and u8confirmation.get('original_deadline_monotonic')==95862.328
         and type(u8confirmation.get('checked_unix')) in (int,float)
         and math.isfinite(u8confirmation['checked_unix'])
         and type(u8confirmation.get('checked_monotonic')) in (int,float)
         and math.isfinite(u8confirmation['checked_monotonic'])
         and u8confirmation['checked_unix']<u8confirmation['original_deadline_unix']
         and u8confirmation['checked_monotonic']<u8confirmation['original_deadline_monotonic'],
         'saved_UAR08_confirmation_must_have_closed_its_original_clock')
    cfg['_latest_full_gate_confirmation_identities']=u8confirmation['known_identities']
    # Normal source_union checks actual cleanup/source and current absence. A
    # false/unqualified root needs a separately reviewed typed observation;
    # this fixed source does not coerce a negative receipt into normal success.
    for ref in cfg['predecessors']:
        need(type(ref) is dict and pins.get(ref['path'])==ref['sha256'],'predecessor_must_be_frozen')
    history=cfg.get('historical_failure_evidence',[])
    need(any(r.get('sha256')=='87f691b5774ed6f604069d952041bdd6af6a6022f9ea1268ac77a8364180a106'
         and r.get('scope')=='immutable_evidence_only_not_owned_grant' and pins.get(r['path'])==r['sha256']
         for r in history),'unqualified_UAR02_failure_must_remain_evidence_only')
    for pathkey in ('technical_entry','contracts','focused_helper'):
        need(cfg[pathkey] in pins,'gate_dependency_pin_missing')
    need(len(cfg['canonical_python_inventory'])==183,'exact183_current_canonical_python_required')
    for relative,h in [('fitting-context-selector-combined-next-dev/source-handoff.json',COMPOSITION_HANDOFF_SHA),
                       ('fitting-context-selector-combined-independent-review-r1.json',COMPOSITION_PEER_SHA),
                       ('br-standard-release-qualification-next-dev/controller-r5/run_controller.py',C5_BASE_SHA)]:
        path=str(work/relative)
        need(pins.get(path)==h and digest(path)==h,'reviewed_composition_and_current_guard_required')
    # Exactly TWO reviewed test helpers may differ; every runtime/other test
    # stays byte bound to the immutable composition. No generic override map.
    compat_path=work/'combined-legacy-test-compatibility-next-dev/source-handoff.json'
    compat_peer=work/'combined-legacy-test-compatibility-independent-review-r1.json'
    for source,h in [(compat_path,COMPAT_HANDOFF_SHA),(compat_peer,COMPAT_PEER_SHA)]:
        need(pins.get(str(source))==h and digest(source)==h,'exact_two_test_overlay_and_peer_required')
    compat=read(compat_path)
    need(compat.get('canonical_replacements')==COMPAT_REPLACEMENTS
         and set(COMPAT_REPLACEMENTS)=={'tests/test_uar_hpo_fair_reserve.py','tests/test_uar_loss_backend.py'},
         'only_two_exact_reviewed_test_helper_replacements_allowed')
    composition=read(work/'fitting-context-selector-combined-next-dev/source-handoff.json')
    for relative,h in composition['files_sha256'].items():
        if relative.startswith('candidate/'):
            target=relative[len('candidate/'):];path=str(root/target)
            if target in COMPAT_REPLACEMENTS:
                replacement=COMPAT_REPLACEMENTS[target]
                need(replacement['before_sha256']==h,'overlay_original_test_pin_changed')
                candidate=compat_path.parent/replacement['candidate_path']
                h=replacement['after_sha256']
                need(pins.get(str(candidate))==h and digest(candidate)==h,
                     'exact_reviewed_test_helper_source_required')
            need(pins.get(path)==h and digest(path)==h,'actual_canonical_must_equal_reviewed_composition_or_two_exact_tests')
    need(pins.get(str(packet/'test_gate_plumbing.py'))==digest(packet/'test_gate_plumbing.py'),
         'fixed_six_gate_plumbing_contracts_source_required')
    fixture=cfg.get('mapped_fixture_modules')
    need(type(fixture) is list and len(fixture)==1 and set(fixture[0])=={'test_relative_path','test','target','sha256'}
         and fixture[0]['test_relative_path']=='tests/test_feature_views.py'
         and fixture[0]['test']==str(root/'tests/test_feature_views.py')
         and fixture[0]['target']=='tests/test_feature_views.py'
         and pins.get(fixture[0]['test'])==fixture[0]['sha256'],
         'exact_unrun_import_only_feature_views_fixture_required')
    native=[s for s in cfg['mapped_suites'] if s['test_relative_path']=='tests/test_uar_fitting_extractor.py']
    need(len(native)==1 and native[0]['id']=='test_uar_fitting_extractor',
         'native_fixture_dependency_filename_required')
    refs=[r for r in cfg['predecessors'] if r.get('id')=='cx2']
    need(len(refs)==1 and refs[0]==dict(id='cx2',path=str(work/'cx2/terminal-root-closure.json'),
         sha256='9525e4eb4a90a50c7eab4894b00080f032c782455cd360f39a7777f32fffb131',
         actual_exec_session=72141,actual_exit_code=0,actual_tool_evidence='ea9a27'),
         'closed_current_CX2_actual_driver_required')
    current=cfg.get('latest_CX2')
    need(type(current) is dict and set(current)=={'fresh','wrapper_exit','post_tool_confirmation_actual'},
         'exact_CX2_atomic_and_actual_wrapper_confirmation_required')
    for name,relative,h in [('fresh','cx2/root-confirmation.json','b9f5cd2c86ad150cb710c45f3fbc097b802d2f1ab6974a2fc1640ad3d772ac47'),
                            ('wrapper_exit','cx2/actual-wrapper-exit-confirmation.json','51fb764051ecb1147b95377ff420a5a8ae96ea0128ed5a5f15aa115c368f1d46')]:
        ref=current[name]
        need(ref==dict(path=str(work/relative),sha256=h) and pins.get(ref['path'])==h
             and digest(ref['path'])==h,'actual_CX2_confirmation_changed')
    need(current['post_tool_confirmation_actual']==dict(exit_code=0,tool='180656'),
         'root_actual_post_tool_exit_evidence_required')
    root_cx=read(refs[0]['path']);fresh=read(current['fresh']['path']);post=read(current['wrapper_exit']['path'])
    need(pins.get(refs[0]['path'])==refs[0]['sha256'] and digest(refs[0]['path'])==refs[0]['sha256']
         and root_cx.get('schema')=='class-xgb-cache-root-closure-v1'
         and all(root_cx.get(k) is True for k in ['technical_procedure_passed','source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed'])
         and root_cx.get('active_owned_processes')==[] and root_cx.get('uncertain_owned')==[],
         'positive_clean_CX2_root_required_not_quality_promotion')
    need(fresh.get('schema')=='class-cache-atomic-root-confirmation-v1'
         and fresh.get('root_sha256')==refs[0]['sha256']
         and fresh.get('actual_driver')==dict(session=72141,exit_code=0,tool='ea9a27')
         and fresh.get('actual_closer_exit')==0 and fresh.get('known_exact_live')==[] and fresh.get('uncertain')==[]
         and all(fresh.get(k) is True for k in ['technical_procedure_passed','source_unchanged','current_temporary_absent',
              'current_cleanup_confirmed','inside_actual_closer_birth60','inside_original600','inside_existing_driver_final240'])
         and fresh.get('old_CX1_status')=='FAIL_ROOT_FRESH60_MISSED' and fresh.get('old_CX1_requalified') is False,
         'atomic_current_scope_must_preserve_CX1_FAILURE')
    confirmed_cx=identity_set(fresh['known_identities'])
    wrapper_cx=identity_set(fresh['wrapper_preparer_identities'])
    need(len(confirmed_cx)==fresh.get('known_count')==7340 and len(wrapper_cx)==3
         and not confirmed_cx&wrapper_cx
         and identity_set(root_cx['owned_identities']+root_cx['closure_preparer_identities'])<=confirmed_cx,
         'exact_saved_CX2_known7340_plus_three_actual_wrapper_preparers_required')
    # The pinned post-tool receipt has a COUNT, not an identity array or source
    # map. Only the explicitly saved fresh+wrapper tuples grant known scope.
    known_cx=confirmed_cx|wrapper_cx
    need(post.get('schema')=='class-cache-CX2-actual-wrapper-exit-confirmed-v1'
         and post.get('actual_wrapper')==dict(exit_code=0,tool='ea00b8')
         and post.get('root_confirmation_sha256')==current['fresh']['sha256']
         and post.get('known_count')==len(known_cx)==7343
         and type(post.get('source_pins')) is int and post['source_pins']==747
         and post.get('known_exact_live')==[] and post.get('uncertain')==[] and post.get('source_unchanged') is True
         and post.get('original_root_window_saved_and_verified') is True and post.get('post_tool_confirmed') is True
         and post.get('no_new_root60') is True
         and post.get('original_CX1_status')=='FAIL_ROOT_FRESH60_MISSED',
         'actual_wrapper_exit_and_explicit_saved_preparer_union_required')
    root_clock_fields=('original_start_unix','original_start_monotonic','original_deadline_unix','original_end_monotonic')
    fresh_clock_fields=('actual_closer_birth','finished_unix','finished_monotonic')
    need(all(type(root_cx.get(k)) in (int,float) and math.isfinite(root_cx[k]) for k in root_clock_fields)
         and all(type(fresh.get(k)) in (int,float) and math.isfinite(fresh[k]) for k in fresh_clock_fields)
         and root_cx.get('original_common_seconds')==600
         and root_cx['original_deadline_unix']==root_cx['original_start_unix']+600
         and root_cx['original_end_monotonic']==root_cx['original_start_monotonic']+600
         and root_cx['original_start_unix']<=fresh['actual_closer_birth']<=fresh['finished_unix']
         and fresh['finished_unix']<fresh['actual_closer_birth']+60
         and fresh['finished_unix']<root_cx['original_deadline_unix']
         and root_cx['original_start_monotonic']<=fresh['finished_monotonic']<root_cx['original_end_monotonic'],
         'saved_CX2_fresh_must_remain_inside_actual_birth60_and_original600')
    for ref in cfg.get('additional_preparer_receipts',[]):
        need(type(ref) is dict and set(ref)=={'path','sha256'} and Path(ref['path']).is_absolute()
             and pins.get(ref['path'])==ref['sha256'] and digest(ref['path'])==ref['sha256'],
             'pinned_actual_additional_preparer_receipt_required')
        known_cx|=identity_set(read(ref['path'])['identities'])
    cfg['_latest_full_gate_confirmation_identities']=[dict(pid=p,create_time=b) for p,b in sorted(known_cx)]
    return cfg

def current_guard_source():
    need(digest(C5_BASE_PATH)==C5_BASE_SHA,'qualified_C5_capture_guard_changed')
    return imported('_uar10_C5_guard',C5_BASE_PATH)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',action='store_true',required=True)
    for name in ('private-manifest','private-manifest-sha256','self-sha256','latest-root-closure-sha256'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True);p.add_argument('--launch-parent-create-time',type=float,required=True)
    a=p.parse_args();start,mono=time.time(),time.monotonic();unix,end=start+COMMON,mono+COMMON;final_end=None
    import psutil
    current=current_guard_source();preparers,launch_parent=current.capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    early=PACKET/'driver-preparer-identity.json'
    with early.open('x',encoding='utf-8') as stream:json.dump(dict(identities=preparers,launch_parent_observation=launch_parent),stream,indent=2,allow_nan=False)
    need(launch_parent.get('verified') is True,'actual_launch_parent_unconfirmed')
    a.private_manifest=str(Path(a.private_manifest).resolve())
    def clock():
        need(time.time()<unix and time.monotonic()<end,'original1200_deadline_exhausted')
        need(abs((unix-time.time())-(end-time.monotonic()))<=5,'clock_disagreement')
        if final_end is not None:need(time.monotonic()<final_end,'actual_final180_cap_exhausted')
    cfg=config(a.private_manifest,a.private_manifest_sha256,a.self_sha256)
    need(__debug__ and Path(cfg['python']).resolve()==Path(sys.executable).resolve(),'pinned_nonoptimized_interpreter_required')
    refs={r['id']:r for r in cfg['predecessors']}
    need(refs[cfg['latest_predecessor_id']]['sha256']==a.latest_root_closure_sha256,'actual_latest_closure_pin_required')
    for name in ('contracts','focused_helper'):
        need(digest(cfg[name],clock)==cfg['files_sha256'][cfg[name]],'standalone_dependency_changed')
    contract=imported('_uar04_contracts',cfg['contracts']);base=imported('_uar04_focused_helpers',cfg['focused_helper'])
    for name in HELPERS:need(digest(cfg['helpers'][name]['path'],clock)==HELPERS[name],'guard_dependency_changed')
    modules={n:imported('_uar04_'+n,cfg['helpers'][n]['path']) for n in HELPERS}
    coor,owner,proc=(modules[n] for n in ('coordinator','owner','processes'))
    need(coor.WORK.resolve()==Path(cfg['work_root']).resolve(),'proven_work_root_mismatch')
    root,boot=preparers[0],preparers[1:];out=Path(cfg['output']);need(not out.exists(),'exclusive_attempt_no_reset')
    out.mkdir();state=dict(schema='uar-full-campaign-v1',status='starting',start_unix=start,start_monotonic=mono,
        absolute_deadline_unix=unix,common_deadline_monotonic=end,common_seconds=COMMON,
        phase_caps_seconds=dict(parent=PARENT,child=CHILD,actual_final=FINAL,root_close=ROOT_CLOSE),
        private_manifest_sha256=a.private_manifest_sha256,owned_root=root,coordinator_bootstrap_identities=boot,
        supervisors=[],active_supervisor=None,error_history=[],cleanup_confirmed=False,source_unchanged=False,
        fixture_learner_fits=None,external_API_calls=None,public_experiment_fits=0,quality_metric=None,
        root_actual_exec_confirmation_pending=True,promotion=False,submit=False,_manifest={},
        temporary_root=None,temporary_cleanup_confirmed=False)
    known=set();children=set();suite_ob=owner.StrictOwnedObserver();awake=None;temporary_root=None;power_released=False;lease=None
    def persist():coor.save(out/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    parent_pulse=current.guard(mono,end,unix,owner,preparers,state,sampling=modules['sampling'])
    parent_clock=state['_resource_checkpoint'];last_technical_sample=mono;pulse_maximum_gap=0.;pulse_sticky_error=None
    sampler=modules['sampling'].VerifiedResourceSampler();required=(root['pid'],root['create_time'])
    def resource_clock():
        nonlocal pulse_maximum_gap,pulse_sticky_error
        if pulse_sticky_error is not None:raise RuntimeError(pulse_sticky_error)
        try:
            parent_clock();clock();now=time.monotonic()
            pulse_maximum_gap=max(pulse_maximum_gap,now-last_technical_sample)
            need(now-last_technical_sample<=10,'technical_observation_gap10')
            return now
        except BaseException as exc:
            pulse_sticky_error=str(exc) if isinstance(exc,RuntimeError) else 'technical_resource_unconfirmed'
            raise
    def pulse(force=False):
        nonlocal last_technical_sample,pulse_sticky_error
        try:
            now=resource_clock();parent_pulse(force=force)
            if not force and now-last_technical_sample<.25:return
            active=state.get('active_supervisor')
            if active:
                record=read(Path(cfg['work_root'])/active)
                if record.get('owned_root'):suite_ob.remember(coor.identities([record['owned_root']]))
            live=suite_ob.observe();need(not suite_ob.denials,'technical_tree_observation_denied')
            children.update(suite_ob.seen)
            sample=sampler.sample(set(suite_ob.seen)|set(live)|coor.identities(preparers),required=[required],checkpoint=resource_clock)
            child_rss=sum(row['rss_bytes'] for row in sample['sampled'] if (row['pid'],row['create_time']) in suite_ob.seen)
            need(child_rss<=1536*2**20,'technical_child_tree_memory_limit')
            need(sum(row['rss_bytes'] for row in sample['sampled'])<=2048*2**20,'whole_technical_parent_memory_limit')
            state['peak_technical_tree_rss_mib']=max(state.get('peak_technical_tree_rss_mib',0.),child_rss/2**20)
            state['verified_technical_resource_sample']=sample
            last_technical_sample=resource_clock()
        except BaseException as exc:
            pulse_sticky_error=str(exc) if isinstance(exc,RuntimeError) else 'technical_resource_observation_unconfirmed'
            raise
    state['_resource_checkpoint']=resource_clock
    def guard(parent_end=None,code='parent_cap_exhausted'):
        coor.cooperative_checkpoint(awake,end,unix,parent_end,code);clock()
        need(digest(a.private_manifest,pulse)==a.private_manifest_sha256,'private_manifest_changed');contract.frozen(cfg,pulse)
    state['_pulse']=pulse
    try:
        need(time.monotonic()-mono<10,'pre_power_guard_setup_gap')
        awake=modules['awake'].PowerRequestGuard('UAR08 cadence combined serial technical fixtures',10)
        awake.__enter__();state['_awake']=awake;pulse(force=True)
        guard();known=base.source_union(cfg,coor,pulse)
        known |= coor.identities(cfg['_latest_full_gate_confirmation_identities']);base.absence(owner,known)
        lease=modules['lock'].ResearchLock(cfg['lock_path']);lease.__enter__()
        lease.write_identity(root);base.absence(owner,known);persist();guard()
        need(unix-time.time()>=MINIMUM_REMAINING and end-time.monotonic()>=MINIMUM_REMAINING,
             'mandatory_remaining1140_unavailable')
        need(time.monotonic()<mono+PARENT-CHILD,'setup60_consumed_full_child_admission')
        temporary_base=Path(cfg['work_root'])/'t'
        need(not temporary_base.is_symlink() and temporary_base.resolve()==temporary_base,
             'temporary_base_symlink_or_junction_denied')
        temporary_base.mkdir(exist_ok=True)
        temporary_root=Path(tempfile.mkdtemp(prefix='u10-',dir=temporary_base)).resolve()
        need(temporary_root.parent==temporary_base.resolve() and not temporary_root.is_symlink(),
             'exclusive_shallow_temporary_root_required')
        (temporary_root/'m').mkdir()
        state['temporary_root']=str(temporary_root)
        coor.save(out/'temporary-root.json',dict(schema=1,root=str(temporary_root),
            owner=root,run_id='UAR10',scope='exclusive_shallow_leaf_environment'),True)
        persist();guard()
        child_end=min(mono+PARENT,time.monotonic()+CHILD)
        command=[cfg['python'],'-B','-X','utf8',cfg['technical_entry'],
            '--private-manifest',a.private_manifest,'--private-manifest-sha256',a.private_manifest_sha256,
            '--deadline-monotonic',str(child_end),'--deadline-unix',str(start+child_end-mono),
            '--temporary-root',str(temporary_root)]
        sup=coor.supervise(command,Path(cfg['work_root']),out/'technical.json','technical',mono,PARENT,CHILD,
            end,unix,MINIMUM_REMAINING,state,persist,guard,owner,proc,boot)
        final_start=time.monotonic();final_end=min(final_start+FINAL,end-ROOT_CLOSE)
        state.update(final_start_monotonic=final_start,final_deadline_monotonic=final_end);coor.child_errors(state,sup)
        children.update(coor.identities(sup.get('owned_process_identities',[])))
        if sup.get('owned_root'):children.update(coor.identities([sup['owned_root']]))
        for name in ('technical-results.json','mapped-results.json'):
            if (out/name).exists():
                raw=read(out/name);state[name.replace('.json','')+'_first_failure']=raw.get('first_failure')
                for row in raw.get('leaves',[]):
                    if row.get('owned_root'):children.update(coor.identities([row['owned_root']]))
                    children.update(coor.identities(row.get('owned_process_identities',[])))
        persist();base.absence(owner,known|children)
        need(sup['status']=='ok' and sup['exit_code']==0 and sup['cleanup_confirmed'] is True
             and not sup.get('error_history'),'mandatory_technical_child_failed')
        summary,artifacts=contract.artifact_checks(cfg,out,pulse);state.update(summary);state['qualified_checks']=summary
        state['technical_artifacts']=artifacts;guard();base.absence(owner,known|children)
        state.update(status='technical_completed_pending_root',technical_procedure_passed=True,
            cleanup_confirmed=True,source_unchanged=True);persist();guard()
    except BaseException as exc:
        coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'full_gate_operation_failed','full_gate',exc)
        state.update(status='technical_failure',technical_procedure_passed=False)
    finally:
        if final_end is None:
            now=time.monotonic();final_end=min(now+FINAL,mono+PARENT+FINAL,end-ROOT_CLOSE)
            state.update(final_start_monotonic=now,final_deadline_monotonic=final_end)
        try:
            state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(children)]
            state.update(cleanup_confirmed=False,source_unchanged=False)
            try:
                started=False
                for phase in ('technical',):
                    pulse();path=out/'technical.json';record=read(path) if path.exists() else {}
                    started|=bool(record.get('owned_root'))
                    if record.get('owned_root'):children.update(coor.identities([record['owned_root']]))
                    children.update(coor.identities(record.get('owned_process_identities',[])))
                    for name in ('technical-results.json','mapped-results.json'):
                        raw=read(out/name) if (out/name).exists() else {}
                        for row in raw.get('leaves',[]):
                            if row.get('owned_root'):children.update(coor.identities([row['owned_root']]))
                            children.update(coor.identities(row.get('owned_process_identities',[])))
                state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(children)]
                leaf_ok,uncertain=contract.cleanup_status(cfg,out,started)
                state.update(leaf_cleanup_confirmed=leaf_ok,leaf_cleanup_uncertainty=uncertain)
                pulse();base.absence(owner,known|children);pulse()
                need(state.get('active_supervisor') is None and all(r.get('cleanup_confirmed') is True
                     for r in state['supervisors']) and leaf_ok,'saved_leaf_or_supervisor_cleanup_unconfirmed')
                # Delete only our exclusive shallow tree, after exact owned absence.
                pulse();cleanup_start=time.monotonic()
                if temporary_root is not None:
                    expected_base=(Path(cfg['work_root'])/'t').resolve()
                    need(temporary_root.parent==expected_base and temporary_root.resolve()==temporary_root
                         and not temporary_root.is_symlink()
                         and re.fullmatch(r'u10-[a-z0-9_]{8}',temporary_root.name),
                         'temporary_cleanup_path_or_identity_changed')
                    shutil.rmtree(temporary_root)
                    need(not temporary_root.exists(),'temporary_root_remains_after_cleanup')
                pulse();need(time.monotonic()-cleanup_start<10,'temporary_cleanup_gap10_exhausted')
                coor.save(out/'temporary-cleanup.json',dict(schema=1,root=str(temporary_root) if temporary_root else None,
                    created=temporary_root is not None,cleanup_confirmed=True,
                    elapsed_seconds=time.monotonic()-cleanup_start),True)
                temp_ok,temp_uncertain=contract.temporary_status(cfg,out,state['temporary_root'])
                state.update(temporary_cleanup_confirmed=temp_ok,temporary_cleanup_uncertainty=temp_uncertain)
                need(temp_ok,'saved_temporary_cleanup_unconfirmed');pulse()
                state['cleanup_confirmed']=True
            except BaseException as exc:
                coor.error(state,'final_owned_cleanup_unconfirmed','final_cleanup',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
            try:
                pulse();contract.frozen(cfg,pulse);need(digest(a.private_manifest,pulse)==a.private_manifest_sha256,'private_manifest_changed')
                state['source_unchanged']=True;pulse()
            except BaseException as exc:
                coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'final_guard_failed','final',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
        finally:
            # A prior gap/denial stays sticky; release is attempted even if its pulse fails.
            try:pulse()
            except BaseException as exc:
                coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'final_pulse_unconfirmed','final_guard',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
            finally:
                try:
                    if awake is not None:awake.close()
                except BaseException as exc:
                    coor.error(state,'power_request_cleanup_unconfirmed','power_release',exc)
                    state.update(status='technical_failure',technical_procedure_passed=False)
                finally:
                    power_released=True
                    if awake is not None:state['awake_guard']=awake.record
            try:
                pulse()
                need(awake is not None and awake.record.get('release_API_verified') is True,
                     'power_request_cleanup_unconfirmed')
            except BaseException as exc:
                coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'released_guard_unconfirmed','power_release',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
        state.update(parent_guard_sticky_error=pulse_sticky_error,parent_maximum_observed_gap_seconds=pulse_maximum_gap)
        if state.get('technical_procedure_passed') is not True and state.get('qualified_checks') is not None:
            state['unqualified_completed_checks']=state['qualified_checks'];state['qualified_checks']=None
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-mono)
        persist()
        try:pulse(force=True)
        except BaseException as exc:
            coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'terminal_guard_unconfirmed','terminal_save',exc)
            state.update(status='technical_failure',technical_procedure_passed=False,
                parent_guard_sticky_error=pulse_sticky_error,parent_maximum_observed_gap_seconds=pulse_maximum_gap)
            if state.get('qualified_checks') is not None:
                state['unqualified_completed_checks']=state['qualified_checks'];state['qualified_checks']=None
            persist()
        try:
            if lease is not None:lease.__exit__(None,None,None)
            pulse(force=True);clock()
        except BaseException as exc:
            coor.error(state,'postlease_final_guard_unconfirmed','postlease',exc)
            state.update(status='technical_failure',technical_procedure_passed=False)
            persist()
    passed=state.get('technical_procedure_passed') is True and not state['error_history'] and state['cleanup_confirmed'] and state['source_unchanged'] and pulse_sticky_error is None and state.get('awake_guard',{}).get('release_API_verified') is True
    print(json.dumps({k:state.get(k) for k in ('status','qualified_checks',
        'source_unique_checks','mapped_repeated_checks','technical_procedure_passed','cleanup_confirmed','source_unchanged')},allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='blocked_before_or_during_gate',error_type=type(exc).__name__,
            error_code=str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'preflight_operation_failed',quality_metric=None)))
        raise SystemExit(1)
