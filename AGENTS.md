# Project working rules

At session start, read [AGENT_MEMORY.md](./AGENT_MEMORY.md) and keep its collaboration guidance in mind. Re-read it after context loss, when it changes, or when needed to resolve a relevant preference. Before finishing, incorporate durable new preferences and verified lessons using its maintenance rules; keep it concise and avoid duplicating project documentation.

Before planning, coding, committing, or proposing a new project version, read [TODO.md](./TODO.md). It is the canonical roadmap derived from the original project brief.

Map every requested change to the roadmap before acting. Do not infer version scope from a branch name or an abbreviated user request. Flag a mismatch, out-of-sequence feature, or material scope ambiguity before implementation; do not silently reframe it.

Keep the product incremental and portfolio-realistic. Explain relevant trade-offs at the level of a senior .NET engineer learning Python, React, and TypeScript.

Unless the user explicitly says otherwise, finish each implementation task by running the relevant verification, committing the work, pushing its working branch, and opening a pull request into `master`.
