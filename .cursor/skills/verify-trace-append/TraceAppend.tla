---- MODULE TraceAppend ----
\* Two overlapping append_trace calls. Each call is the two writes in
\* src/tracker/trace.py append_trace:
\*   handle.write(trace_to_jsonl(trace))  -> WriteBody
\*   handle.write("\n")                    -> WriteNewline
\* One write() is one step. The two writes are not one step.
\* read_traces splits the file on newlines and parses each line as one Trace.

EXTENDS Integers, Sequences, FiniteSets

Writers == {"run_a", "run_b"}
NL == "nl"

VARIABLES pc, file
vars == <<pc, file>>

Init ==
  /\ pc = [w \in Writers |-> "start"]
  /\ file = <<>>

WriteBody(w) ==
  /\ pc[w] = "start"
  /\ file' = Append(file, w)
  /\ pc' = [pc EXCEPT ![w] = "wrote_body"]

WriteNewline(w) ==
  /\ pc[w] = "wrote_body"
  /\ file' = Append(file, NL)
  /\ pc' = [pc EXCEPT ![w] = "done"]

Done ==
  /\ \A w \in Writers : pc[w] = "done"
  /\ UNCHANGED vars

Next ==
  \/ \E w \in Writers : WriteBody(w) \/ WriteNewline(w)
  \/ Done

Spec == Init /\ [][Next]_vars

BothDone == \A w \in Writers : pc[w] = "done"

\* After both appends finish, the file is whole trace lines: body, newline,
\* body, newline, and each run appears once.
RecordsStayWhole ==
  \/ ~ BothDone
  \/ /\ Len(file) = 2 * Cardinality(Writers)
     /\ \A i \in 1..Len(file) :
          IF i % 2 = 1 THEN file[i] \in Writers ELSE file[i] = NL
     /\ \A w \in Writers :
          \E i \in 1..Len(file) : (i % 2 = 1) /\ file[i] = w

====
