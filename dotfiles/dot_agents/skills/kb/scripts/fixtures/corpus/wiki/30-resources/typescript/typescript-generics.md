---
title: TypeScript generics
created: 2026-08-09
type: concept
tags: [typescript, generics, types]
---
# TypeScript generics

Generics let a function or type work over many types while keeping the relationship between input and output.

    function first<T>(items: T[]): T | undefined { return items[0]; }

Constraints
- `T extends { id: string }` requires an `id`.
- `K extends keyof T` limits `K` to the keys of `T`; then `T[K]` is the value type.

Defaults: `type Page<T = unknown> = { items: T[]; next?: string }`.

Conditional types
- `type ElementOf<T> = T extends (infer U)[] ? U : never`.
- Distributive over unions when `T` is a naked type parameter; wrap it as `[T]` to stop that.

Pitfalls
- Over-generic signatures: if `T` appears only once, it is probably not needed.
- Inference widens literals; use `const` type parameters to keep them.
