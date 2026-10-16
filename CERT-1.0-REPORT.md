| 1 | `_write` | file fsync dropped | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[create] | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] |
| 2 | `_write` | flush before metadata dropped | test_linux_trace::test_the_real_system_calls_come_in_the_documented_order[create] | survived |
| 3 | `_write` | directory fsync condition inverted | test_cli::test_an_unsynced_directory_exits_with_status_three | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] |
| 4 | `_write` | write-through tied to the file level | survived | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[file-True-None] |
| 5 | `_write` | temp removed only after publishing | test_atomic::test_error_removes_the_temp_file | test_atomic::test_error_removes_the_temp_file |
| 6 | `_write` | create-only check ignores links and directories | test_contract_edges::test_create_only_refuses_a_dangling_link_before_the_block * | test_contract_edges::test_create_only_refuses_a_dangling_link_before_the_block |
| 7 | `_write` | replaced private file gets a world-readable temp | test_hardening::test_temp_file_is_private_when_replacing_a_private_file | survived |
| 8 | `_write` | default text encoding is the locale | survived | test_contract_edges::test_text_mode_defaults_to_utf8_whatever_the_locale |
| 9 | `_write` | temp beside the link instead of the target | test_metadata::test_symlink_into_another_directory_keeps_the_temp_beside_the_target | test_metadata::test_symlink_into_another_directory_keeps_the_temp_beside_the_target |
| 10 | `_write` | directory sync error names the file | test_hardening::test_directory_sync_failure_is_reported_after_the_replace | survived |
| 11 | `_atomic` | append mode accepted | test_atomic::test_invalid_mode_is_rejected | test_atomic::test_invalid_mode_is_rejected |
| 12 | `_atomic` | retry type unchecked | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs16-TypeError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs16-TypeError] |
| 13 | `_atomic` | overwrite flag ignored | test_cli::test_no_overwrite_fails_on_an_existing_file | test_cli::test_no_overwrite_fails_on_an_existing_file |
| 14 | `_atomic` | follow_symlinks ignored | test_hardening::test_no_follow_replaces_a_symlink_to_a_directory | test_contract_edges::test_create_only_refuses_a_dangling_link_before_the_block |
| 15 | `_atomic` | preserve_owner ignored | test_contract_edges::test_preserve_owner_restores_another_users_file (root run) * | survived |
| 16 | `_check` | NUL check misses NUL | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs20-ValueError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs20-ValueError] |
| 17 | `_check` | permission range too wide | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs11-ValueError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs11-ValueError] |
| 18 | `_check` | bool permissions accepted | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs13-TypeError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs13-TypeError] |
| 19 | `_check` | tab newline accepted | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs6-ValueError] | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs6-ValueError] |
| 20 | `_check` | infinity accepted | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs4-ValueError] | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs4-ValueError] |
| 21 | `_check` | minimum made exclusive | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets |
| 22 | `_check` | bytes paths accepted | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs17-TypeError] * | test_contract_api::test_bad_arguments_raise_at_call_time_with_short_messages[kwargs17-TypeError] |
| 23 | `_options` | zero attempts accepted | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs0-ValueError] | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs0-ValueError] |
| 24 | `_options` | shrinking multiplier accepted | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs9-ValueError] | test_contract_api::test_retry_policy_rejects_values_that_cannot_wait[kwargs9-ValueError] |
| 25 | `_options` | cap not applied to the first delay | test_contract_edges::test_the_first_delay_is_capped_too * | test_contract_edges::test_the_first_delay_is_capped_too |
| 26 | `_options` | one delay too many | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets | test_contract_api::test_retry_delays_are_floats_capped_even_for_huge_budgets |
| 27 | `_options` | file level also syncs the directory | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[replace-file] | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[file-True-None] |
| 28 | `_options` | legacy fsync_dir ignored | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] * | test_contract_edges::test_legacy_flags_choose_the_file_and_directory_syncs[True-False-0] |
| 29 | `_replace` | sharing violation not retried | survived | test_hardening::test_a_locked_temp_file_is_still_removed_once_released |
| 30 | `_replace` | read-only target retried | survived | test_sharing::test_read_only_target_is_not_retried |
| 31 | `_replace` | attempt count off by one | survived | test_sharing::test_exhausted_retry_raises_and_leaves_target_and_no_temp |
| 32 | `_replace` | write-through never used on Windows | test_atomic::test_write_text_atomic_creates_the_file | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[full-True-9] |
| 33 | `_replace` | temp name kept after create-only link | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[exclusive] | survived |
| 34 | `_replace` | create-only ignored without write-through | test_crash_points::test_the_call_sequence_is_flush_then_rename_then_directory[exclusive] | test_overwrite::test_no_overwrite_detects_a_file_created_during_the_write[none]* |
| 35 | `_win` | flags swapped | survived | test_contract_platform::test_only_full_writes_the_rename_through_on_windows[full-False-8] |
| 36 | `_win` | error names swapped | survived | test_contract_platform::test_write_through_errors_look_like_os_replace_errors |
| 37 | `_fs` | stem limit off | test_contract_edges::test_names_up_to_48_characters_appear_whole_in_the_temp_name[30] * | test_contract_edges::test_names_up_to_48_characters_appear_whole_in_the_temp_name[30] |
| 38 | `_fs` | new files ignore the group write bit of the umask | test_contract_edges::test_new_files_take_every_bit_the_umask_allows * | survived |
| 39 | `_fs` | no fsync when F_FULLFSYNC fails | test_contract_platform::test_full_fsync_is_used_where_the_platform_has_it[True] | test_contract_platform::test_full_fsync_is_used_where_the_platform_has_it[True] |
| 40 | `_fs` | preserve_mode ignored | test_metadata::test_preserve_mode_can_be_turned_off | equivalent here (mode bits are not applied on Windows); the run stopped on a transient process-test failure |
| 41 | `_fs` | replaced link inherits the mode | test_hardening::test_no_follow_replaces_a_symlink_to_a_directory | survived |
| 42 | `_fs` | locked temp treated as read-only | survived | survived |
| 43 | `_cleanup` | age cutoff loosened | test_contract_edges::test_cleanup_respects_the_exact_age_boundary * | test_contract_edges::test_cleanup_respects_the_exact_age_boundary |
| 44 | `_cleanup` | pattern without the leading dot | test_json_cleanup::test_cleanup_never_touches_other_files | run stopped on a transient process-test failure; name matching is the same on both platforms, so the Linux kill applies |
| 45 | `_cleanup` | links to files are removed | test_contract_edges::test_cleanup_never_follows_a_link_named_like_a_temp_file * | test_contract_edges::test_cleanup_never_follows_a_link_named_like_a_temp_file |
| 46 | `_cli` | cli mode range narrowed | test_contract_edges::test_cli_accepts_special_permission_bits * | test_contract_edges::test_cli_accepts_special_permission_bits |
| 47 | `_cli` | unsynced directory exit status | test_cli::test_an_unsynced_directory_exits_with_status_three | survived |
| 48 | `_cli` | append swallows read errors | test_contract_edges::test_cli_append_fails_when_the_current_content_cannot_be_read * | survived |
| 49 | `_helpers` | json without trailing newline | test_contract::test_every_writer_replaces_completely_and_leaves_no_temp[json] | test_contract::test_every_writer_replaces_completely_and_leaves_no_temp[json] |
| 50 | `_helpers` | NaN allowed in json | test_hardening::test_json_refuses_nan_unless_allowed | test_hardening::test_json_refuses_nan_unless_allowed |
