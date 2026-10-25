---
title: TypeScript generics deep dive
created: 2026-08-11
type: project
tags: [project, typescript, generics]
---
# TypeScript generics deep dive

Outcome: a small typed event bus where `on<K extends keyof Events>(name: K, fn: (e: Events[K]) => void)` type-checks every handler.

Steps
1. Re-read [[typescript-generics]] and do the exercises at the end.
2. Constraint inference: when does the compiler widen `K` to `string`?
3. Build the bus; add a test file that must fail to compile (`// @ts-expect-error`).
4. Write up what surprised me.

Progress log
- 2026-08-14: `keyof` on a mapped type works as expected; distributive conditional types bit me twice.
- 2026-08-20: bus compiles; the `@ts-expect-error` checks pass.
