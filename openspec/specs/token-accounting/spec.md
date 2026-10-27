# token-accounting Specification

## Purpose
Records what the host session spent on each task, as token counts in the durable ledger, and turns that record into a price-bound report and an enforceable per-change budget.

## Requirements

### Requirement: A usage row records a task's token spend

The shim SHALL record token usage as a `usage` ledger row carrying the task, the window of session time it covers, the number of assistant messages counted, and per-model counts of input, output, cache-read and cache-write tokens. The row SHALL store counts only, never transcript text.

#### Scenario: A gated commit records the task's usage

- **WHEN** a task's gated commit passes the commit hook and the hook holds a readable transcript path
- **THEN** a `usage` row for that task is appended, covering the window from the later of the task's latest task start and the task's previous usage row up to now

#### Scenario: Subagent messages are counted with the session

- **WHEN** the session dispatched subagents during the window
- **THEN** their assistant messages are counted in the same row, and the row's message count includes them

#### Scenario: Two consecutive flushes never double count

- **WHEN** a usage row for the task was written and no new assistant message followed
- **THEN** a second record for the task writes a row with zero counts, and the task's total is unchanged

### Requirement: The session stop flushes the task in flight

At every session stop the plugin's hook SHALL record usage for the task in flight, so a task that halts, is abandoned or is resumed later is costed up to that point.

#### Scenario: A halted task is costed

- **WHEN** a task halts and the session stops without a gated commit
- **THEN** the ledger holds a usage row for the task covering the work up to the stop

### Requirement: A missing source is recorded, never a failure

When no readable transcript is available, `usage record` SHALL append a row with null counts and a `source` naming the reason, exit 0, and never block the commit or the stop that invoked it.

#### Scenario: A human session commits

- **WHEN** a commit passes the hook in a session with no transcript path
- **THEN** the commit proceeds and the usage row records null counts with the reason

#### Scenario: An unreadable transcript

- **WHEN** the transcript path exists but cannot be parsed
- **THEN** the row records null counts, names the parse failure, and the hook exits 0

### Requirement: Prices are an adopter binding

`.gates.yaml` MAY declare `economics.prices`, mapping a model name to per-million-token prices for input, output, cache-read and cache-write in one declared currency. The shim SHALL ship no price list. `gates stats --cost` SHALL multiply recorded counts by the declared prices and SHALL name every model it found no price for.

#### Scenario: Cost with prices declared

- **WHEN** the manifest declares prices for every model the ledger recorded and the adopter runs `gates stats --cost`
- **THEN** the report prints a cost per task and per change in the declared currency

#### Scenario: Cost without prices

- **WHEN** the manifest declares no `economics.prices` and the adopter runs `gates stats --cost`
- **THEN** the report prints tokens only and states that no prices are declared

#### Scenario: A model with no price

- **WHEN** the ledger recorded a model absent from `economics.prices`
- **THEN** the report prints the priced subtotal and names the unpriced model and its tokens

### Requirement: A token budget is enforced in code

`.gates.yaml` MAY declare `loop.token-budget`, a positive integer of tokens per change. When a change's recorded usage reaches it, task-bearing `gates run unit` and `gates run ci` SHALL refuse without running the gate, exit 1, and name the budget, the recorded spend and the halt to record. A run with no task SHALL never be budgeted. Without the key no budget applies.

#### Scenario: The budget is reached

- **WHEN** `loop.token-budget` is 2000000 and the change's usage rows sum to 2100000 tokens
- **THEN** `gates run unit --task 1.3` refuses with exit 1, names the budget and the spend, and names `gates halt record budget`

#### Scenario: Spend below the budget

- **WHEN** the change's recorded usage is below `loop.token-budget`
- **THEN** the gate runs normally

#### Scenario: The in-flight task is counted at its next flush

- **WHEN** the task in flight has spent tokens not yet recorded
- **THEN** the refusal considers recorded rows only, and the message says the in-flight task is counted at its commit or the session stop
