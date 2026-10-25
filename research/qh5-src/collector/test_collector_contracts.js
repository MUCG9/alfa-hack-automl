// Pure source contract harness for collector.js; all tools are injected mocks.
// Run only after source review. No filesystem, process, models, network or real tools.
const collector = load("QH5CollectorContractProgram");
if (typeof collector !== "string") throw Error("collector_contract_source_missing");
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const run = new AsyncFunction("tools", "load", "store", "text", collector);
const assert = (ok, message) => { if (!ok) throw Error(message); };
const terminal = (exit_code, chunk_id) => ({exit_code, chunk_id, output: ""});
const running = session_id => ({session_id, exit_code: null, chunk_id: "running", output: ""});
async function scenario(options = {}) {
  const state = {
    QH5LaunchMeta: {
      bootstrap: {path: "C:\\mock\\close_native.ps1", sha256: "a".repeat(64)},
      atomic_template: {path: "C:\\mock\\template.json", sha256: "b".repeat(64)}
    },
    QH5LaunchTool: options.launch || running(11)
  };
  const events = [], emitted = [], patches = [];
  const poll = [...(options.poll || [terminal(0, "main_tool")])];
  const exec = [...(options.exec || [terminal(0, "wrapper_tool"), terminal(0, "post_tool")])];
  const fake = {
    async write_stdin(args) {
      events.push({kind: "poll", args});
      if (!poll.length) throw Error("unexpected_poll");
      const result = poll.shift();
      if (result instanceof Error) throw result;
      return result;
    },
    async exec_command(args) {
      events.push({kind: "exec", args});
      if (!exec.length) throw Error("unexpected_exec");
      const result = exec.shift();
      if (result instanceof Error) throw result;
      return result;
    },
    async apply_patch(patch) {
      patches.push(patch);
      events.push({kind: "host"});
      if (options.hostError && patch.includes(options.hostError)) throw Error("injected_receipt_save");
      return {isError: false};
    }
  };
  await run(fake, key => state[key], (key, value) => {state[key] = JSON.parse(JSON.stringify(value));}, value => emitted.push(value));
  return {state, events, emitted, patches};
}
const passed = [];
{
  const r = await scenario({
    poll: [running(11), terminal(0, "main_tool"), running(22), terminal(0, "wrapper_tool")],
    exec: [running(22), terminal(0, "post_tool")]
  });
  const calls = r.events.filter(x => x.kind === "exec");
  assert(calls.length === 2 && calls[0].args.cmd.includes("-Mode 'Close'") &&
    calls[1].args.cmd.includes("-Mode 'Post'"), "separate_native_close_post_required");
  assert(!calls.some(x => /python|pwsh|powershell|ConvertFrom-Json|Get-Content/i.test(x.args.cmd)),
    "collector_must_not_start_metadata_reader_or_nested_shell");
  assert(calls[0].args.cmd.includes("-ActualMainTool 'main_tool'") &&
    calls[1].args.cmd.includes("-ActualWrapperTool 'wrapper_tool'"), "actual_role_chunks_not_initial_chunks");
  assert(!calls.some(x => /'-Mode'|'-SelfSha256'/.test(x.args.cmd)), "named_PS_flags_cannot_be_quoted");
  assert(r.state.QH5TerminalTools.main.history.length === 3 &&
    r.state.QH5TerminalTools.wrapper.history.length === 3, "yielded_role_history_must_be_retained");
  assert(r.events.findIndex(x => x.kind === "host") < r.events.findIndex(x => x.kind === "exec"),
    "main_receipt_must_precede_close");
  assert(r.state.QH5TerminalTools.post.result.exit_code === 0 && r.state.QH5CollectorCompleted === true,
    "successful_post_terminal_not_saved");
  passed.push("positive_yielded_whole_shells_and_actual_chunks");
}
{
  const result = terminal(1, "main_failed");
  result.output = "Warning: tool truncation\nnot JSON";
  const r = await scenario({poll: [result], exec: [terminal(1, "negative_closer")]});
  assert(r.events.filter(x => x.kind === "exec").length === 1 &&
    r.state.QH5TerminalTools.negative_closer.result.exit_code === 1 &&
    r.state.QH5TerminalTools.wrapper === null && r.state.QH5TerminalTools.collector_error === null,
    "warning_prefixed_failed_main_must_reach_one_negative_closer_without_JSON_parse");
  passed.push("warning_prefixed_stdout_not_parsed");
}
{
  const r = await scenario({poll: [terminal(0, "undefined")]});
  assert(!r.events.some(x => x.kind === "exec") &&
    r.state.QH5TerminalTools.collector_error === "actual_main_terminal_exit_or_tool_missing",
    "invalid_actual_main_tool_must_prevent_closure");
  passed.push("invalid_main_chunk_stops_before_close");
}
{
  const r = await scenario({exec: [terminal(0, "")]});
  assert(r.events.filter(x => x.kind === "exec").length === 1 &&
    r.state.QH5TerminalTools.post === null &&
    r.state.QH5TerminalTools.collector_error === "actual_wrapper_terminal_exit_or_tool_missing",
    "wrapper_chunk_missing_must_prevent_post");
  passed.push("missing_wrapper_chunk_blocks_post");
}
{
  const r = await scenario({exec: [terminal(1, "wrapper_failed")]});
  assert(r.events.filter(x => x.kind === "exec").length === 1 &&
    r.state.QH5TerminalTools.wrapper.result.exit_code === 1 && r.state.QH5TerminalTools.post === null,
    "nonzero_wrapper_must_not_post_or_retry");
  passed.push("nonzero_wrapper_preserved_no_post");
}
{
  const r = await scenario({hostError: "qh5-actual-main-terminal-tools-r1.json"});
  assert(!r.events.some(x => x.kind === "exec") && r.state.QH5TerminalTools.main.result.exit_code === 0 &&
    r.state.QH5TerminalTools.collector_error === "injected_receipt_save",
    "main_receipt_failure_must_prevent_close_and_preserve_terminal");
  passed.push("main_receipt_failure_is_fatal_before_close");
}
{
  const r = await scenario({hostError: "qh5-actual-terminal-tools-r1.json"});
  assert(r.state.QH5TerminalTools.receipt_save_error === "receipt_save_failed" &&
    r.emitted.at(-1).receipt_save_error === "receipt_save_failed" &&
    r.state.QH5AutoCollectorActive === false &&
    r.patches.filter(x => x.includes("qh5-actual-terminal-tools-r1.json")).length === 1,
    "late_host_save_error_must_be_visible_restored_and_never_retried");
  passed.push("final_receipt_failure_visible_and_stored");
}
{
  const r = await scenario({poll: [{exit_code: null, output: "orphan"}]});
  assert(!r.events.some(x => x.kind === "exec") && r.state.QH5TerminalTools.main.history.length === 2 &&
    r.state.QH5TerminalTools.collector_error === "actual_main_running_session_missing",
    "unknown_running_session_must_not_be_invented_or_retried");
  passed.push("missing_running_handle_is_fatal");
}
{
  const r = await scenario({exec: [terminal(0, "wrapper_tool"), terminal(1, "post_failed")]});
  assert(r.state.QH5TerminalTools.post.result.exit_code === 1 &&
    r.events.filter(x => x.kind === "exec").length === 2 && r.emitted.at(-1).post_exit === 1,
    "post_failure_must_remain_actual_failure_without_retry");
  passed.push("post_failure_preserved");
}
{
  const r = await scenario({launch: terminal(1, "direct_main"), poll: [], exec: [terminal(1, "direct_negative")]});
  const calls = r.events.filter(x => x.kind === "exec");
  assert(!r.events.some(x => x.kind === "poll") && calls.length === 1 &&
    !calls[0].args.cmd.includes("-ActualMainSession") &&
    calls[0].args.cmd.includes("-ActualMainTool 'direct_main'") &&
    r.state.QH5TerminalTools.main.history.length === 1 &&
    r.state.QH5TerminalTools.negative_closer.result.exit_code === 1,
    "direct_completed_initial_exec_must_reach_closer_without_fabricated_session");
  passed.push("direct_initial_terminal_without_session");
}
text({schema: "qh5-collector-pure-contract-results-v1", passed: passed.length, names: passed,
  actual_models: 0, actual_API: 0, actual_OS_processes: 0, injected_tools_only: true});
