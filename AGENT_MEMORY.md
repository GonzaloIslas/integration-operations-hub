# Shared working memory

Portable collaboration guidance for future AI agents. Seeded on 2026-10-03 from the user's memory request and existing project instructions/history; this is not an exhaustive record of past conversations.

## Read and apply

Read once at session start, before planning or changing files, and keep it in mind throughout the task. Re-read after context loss, when this file changes, or when a relevant preference is uncertain; otherwise reuse the loaded context. Current user instructions and applicable project rules take precedence over these defaults, subject to the agent's higher-priority instructions. Keep project state in its canonical documentation.

## Explicit goals

- Standardize collaboration across agents and projects. Carry useful preferences and lessons forward so the user does not need to explain them again.
- Minimize token use while preserving correctness and completing the requested work.
- Maintain this memory as relevant new information emerges.

## Established working defaults

These defaults come from prior project guidance; adapt them when the user or a new project's instructions say otherwise.

- Calibrate explanations to a senior .NET engineer. Python, React, and TypeScript were learning areas in the source project. Explain meaningful trade-offs with .NET comparisons when useful, without reteaching basic engineering or assuming mastery from repository contents.
- Establish scope from the agreed brief and roadmap before acting. Surface material ambiguity, mismatches, and out-of-sequence work; do not silently reinterpret a request from a branch name or version label.
- Build incrementally around a concrete product need. Keep complexity proportionate; avoid architecture added merely to demonstrate technologies.
- Start new coding work from the current integration branch, preserving earlier work. Check an existing task branch before creating another. Determine branch names and targets from the current repository.
- Finish implementation with relevant verification, a commit, a push, and a pull request unless the user opts out. Respect the current repository's delivery rules and authorization boundaries.

## Lessons to retain

- Scope labels can hide unfinished requirements. Earlier provider simulation was mislabeled as V2 although the agreed V2 was a frontend. Check deliverables against the roadmap before calling a version complete.
- Code using a technology is evidence of project exposure, not proof of mastery. Describe experience and completion accurately.

## Token discipline

- Reuse settled decisions; reopen them only when requirements or evidence change.
- Read targeted files or sections after loading required instructions. Avoid repeatedly loading entire documents, histories, or unchanged tool output.
- Give concise explanations of decisions, material trade-offs, verification, and blockers. Do not repeat plans or settled context.
- Link to detailed project documentation instead of copying it here. Keep this file near 600 words or less; consolidate before expanding.

## Maintain the memory

Before finishing a task, check for durable user corrections, explicit preferences, or verified lessons that would prevent repeated work. If any emerged, update the smallest relevant entry and briefly report the change; otherwise leave the file alone.

Record actionable rules with a short source or example where useful. Label unconfirmed inferences rather than promoting them to preferences. Replace superseded entries, merge duplicates, and remove stale guidance. Keep project-specific lessons in project documentation. Do not store transcripts, temporary status, secrets, or unrelated personal details, and do not generalize one project's technology choices into universal preferences.

To reuse elsewhere, carry this file into the new project and add an instruction to its agent entry point to read and maintain it. Separate copies do not synchronize automatically.
