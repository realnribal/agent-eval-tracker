function tokens(file) {
  if (file == null || typeof file !== "object") return [];
  const keys = Object.keys(file)
    .map((key) => Number(key))
    .filter((n) => Number.isInteger(n) && n >= 1);
  const last = keys.length === 0 ? 0 : Math.max(...keys);
  const out = [];
  for (let i = 1; i <= last; i += 1) out.push(file[i]);
  return out;
}

const who = { run_a: "run A", run_b: "run B" };

function describe(file) {
  const t = tokens(file);
  if (t.length === 0) return "No traces written yet";
  const parts = [];
  let open = [];
  const flush = (closed) => {
    if (open.length === 0) return;
    const names = open.map((id) => who[id] ?? id);
    if (names.length === 1 && closed) parts.push(`a complete line for ${names[0]}`);
    else if (names.length === 1) parts.push(`${names[0]} wrote JSON, newline still missing`);
    else if (closed) parts.push(`a torn line mixing ${names.join(" and ")}`);
    else parts.push(`JSON from ${names.join(" and ")} with no newline between them`);
    open = [];
  };
  for (const tok of t) {
    if (tok === "nl") {
      if (open.length === 0) parts.push("a blank line");
      else flush(true);
    } else open.push(tok);
  }
  flush(false);
  return parts.join(". Then ");
}

export const title = "Two tracker runs append traces";

export const state = (v) => describe(v.file);

export const step = (action) => {
  if (action === "Done") return null;
  if (action === "WriteBody") return "a run writes its JSON";
  if (action === "WriteNewline") return "a run writes the newline";
  return null;
};

export const group = (v) => {
  const t = tokens(v.file);
  for (let i = 1; i < t.length; i += 1) {
    if (t[i] !== "nl" && t[i - 1] !== "nl") return "torn";
  }
  const bothDone =
    t.length === 4 && t[0] !== "nl" && t[1] === "nl" && t[2] !== "nl" && t[3] === "nl";
  return bothDone ? "whole" : "writing";
};

export const colors = { writing: "blue", torn: "orange", whole: "teal" };
