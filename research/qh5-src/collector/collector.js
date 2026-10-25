// QH5 prospective collector. Execute only after final independent review and actual launch.
// No campaign output is parsed. Native Close/Post owns bounded local metadata handling.
const meta = load("QH5LaunchMeta");
const quote = value => "'" + String(value).replace(/'/g, "''") + "'";
const actual = {
  schema: "qh5-actual-terminal-tool-results-v2",
  launch: load("QH5LaunchTool"), main: null, negative_closer: null,
  wrapper: null, post: null, collector_error: null, receipt_save_error: null
};
function need(value, code) { if (!value) throw Error(code); }
function ref(value) {
  return value && typeof value.path === "string" && /^[A-Za-z]:[\\/]/.test(value.path) &&
    typeof value.sha256 === "string" && /^[0-9a-f]{64}$/.test(value.sha256);
}
function chunk(value) {
  return typeof value === "string" && /^[a-zA-Z0-9_-]+$/.test(value) &&
    value !== "undefined" && value !== "null" && !value.includes("PENDING");
}
function saveState() { store("QH5TerminalTools", actual); }
async function terminal(role, initial) {
  const record = { result: initial, history: [initial] };
  actual[role] = record;
  saveState();
  let current = initial;
  while (current && current.exit_code == null) {
    need(Number.isInteger(current.session_id) && current.session_id > 0,
      "actual_" + role + "_running_session_missing");
    current = await tools.write_stdin({
      session_id: current.session_id, chars: "", yield_time_ms: 10000, max_output_tokens: 1600
    });
    record.history.push(current);
    record.result = current;
    saveState();
  }
  need(current && Number.isInteger(current.exit_code) && chunk(current.chunk_id),
    "actual_" + role + "_terminal_exit_or_tool_missing");
  return current;
}
async function host(path, value) {
  const raw = JSON.stringify(value, null, 2) + "\n";
  const result = await tools.apply_patch("*** Begin Patch\n*** Add File: " + path + "\n" +
    raw.split("\n").slice(0, -1).map(line => "+" + line).join("\n") + "\n*** End Patch");
  need(result != null && result.isError !== true, "hosted_receipt_failed");
  if (typeof result === "string") {
    need(!/^(error|failed|failure)\b/i.test(result.trim()), "hosted_receipt_failed");
  }
  return result;
}
async function executeNative(mode, args) {
  const argv = ["-Mode", mode, "-SelfSha256", meta.bootstrap.sha256, ...args];
  const allowed = new Set(["-Mode", "-SelfSha256", "-Template", "-TemplateSha256",
    "-ActualMainExit", "-ActualMainTool", "-ActualMainSession", "-ActualWrapperExit", "-ActualWrapperTool"]);
  const parts = [];
  for (let i = 0; i < argv.length; i += 2) {
    need(allowed.has(argv[i]) && i + 1 < argv.length, "native_parameter_pairs_required");
    parts.push(argv[i], quote(argv[i + 1]));
  }
  return await tools.exec_command({
    cmd: "& " + quote(meta.bootstrap.path) + " " + parts.join(" "),
    yield_time_ms: 1000, max_output_tokens: 1600
  });
}
store("QH5AutoCollectorActive", true);
try {
  need(ref(meta?.bootstrap) && ref(meta?.atomic_template), "frozen_native_bootstrap_and_template_missing");
  const initialRunning = actual.launch && actual.launch.exit_code == null &&
    Number.isInteger(actual.launch.session_id) && actual.launch.session_id > 0;
  const initialCompleted = actual.launch && Number.isInteger(actual.launch.exit_code) &&
    chunk(actual.launch.chunk_id);
  need(initialRunning || initialCompleted, "actual_initial_launch_evidence_required");
  const main = await terminal("main", actual.launch);
  store("QH5MainTerminal", main);
  await host("work/private/qh5-actual-main-terminal-tools-r1.json", {
    schema: "qh5-actual-main-terminal-tools-v1", launch: actual.launch, main: actual.main
  });
  const args = [
    "-Template", meta.atomic_template.path, "-TemplateSha256", meta.atomic_template.sha256,
    "-ActualMainExit", String(main.exit_code), "-ActualMainTool", main.chunk_id
  ];
  if (Number.isInteger(actual.launch.session_id) && actual.launch.session_id > 0) {
    args.push("-ActualMainSession", String(actual.launch.session_id));
  }
  const role = main.exit_code === 0 ? "wrapper" : "negative_closer";
  const close = await terminal(role, await executeNative("Close", args));
  if (main.exit_code === 0 && close.exit_code === 0) {
    // This is a NEW exec PowerShell after the previous whole shell has exited.
    await terminal("post", await executeNative("Post", [
      "-ActualWrapperExit", "0", "-ActualWrapperTool", close.chunk_id
    ]));
  }
} catch (error) {
  const message = String(error?.message || "collector_exception");
  actual.collector_error = /^[a-z0-9_]+$/.test(message) ? message : "collector_tool_or_metadata_error";
  actual.collector_error_detail = message;
}
saveState();
try {
  await host("work/private/qh5-actual-terminal-tools-r1.json", actual);
} catch (error) {
  actual.receipt_save_error = "receipt_save_failed";
  actual.receipt_save_error_detail = String(error?.message || "receipt_save_exception");
}
saveState();
store("QH5AutoCollectorActive", false);
store("QH5CollectorCompleted", true);
text({
  collector_completed: true, main_exit: actual.main?.result?.exit_code ?? null,
  negative_closer_exit: actual.negative_closer?.result?.exit_code ?? null,
  wrapper_exit: actual.wrapper?.result?.exit_code ?? null, post_exit: actual.post?.result?.exit_code ?? null,
  error: actual.collector_error, receipt_save_error: actual.receipt_save_error, quality_not_read: true
});
