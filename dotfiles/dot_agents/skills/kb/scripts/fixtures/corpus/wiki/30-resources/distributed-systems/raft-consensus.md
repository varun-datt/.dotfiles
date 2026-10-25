---
title: Raft consensus
created: 2026-09-07
type: concept
tags: [distributed-systems, consensus, raft]
---
# Raft consensus

Raft keeps a replicated log consistent across a cluster, so a set of servers behaves like one state machine.

## Roles and terms
- Every server is a follower, candidate or leader.
- Time is split into terms; each term has at most one leader.
- A follower that hears nothing for its election timeout becomes a candidate, increments the term and asks for votes.

## Leader election
- A candidate wins with votes from a majority.
- Election timeouts are randomized so two followers rarely time out together (a split vote).
- A server votes for at most one candidate per term, and only for one whose log is at least as up to date as its own (the election restriction).

## Log replication
- The leader appends the client command to its log and sends AppendEntries to the followers.
- An entry is committed once a majority stores it; the leader then applies it and replies to the client.
- Followers with conflicting entries have them overwritten by the leader's log.

## Why a majority
Any two majorities overlap, so a new leader always holds every committed entry.
