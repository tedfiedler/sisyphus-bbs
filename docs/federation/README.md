# Sisyphus Federation

Status: **draft, parked — nothing here is implemented yet.** The operator
reviewed it on 2026-09-20 (answers recorded in protocol.md §14) and wants more
time with the design before building. It stays here as a specification.

Independent Sisyphus BBS nodes, run by different people on their own machines
(laptops included), share a set of *network boards* through one central
**relay**. The relay stores and forwards; it cannot read, forge, or reorder
what passes through it. A node that was offline catches up when it returns.

If this sounds like FidoNet, it is: echomail through a hub, with modern
cryptography and without trusting the hub.

## Decisions this design is built on

| Question | Decision | Consequence |
|---|---|---|
| Who can join? | **Invite-only.** The operator approves each node. | Membership is a signed list, not a sign-up flow. No spam-resistance machinery needed. |
| What may the relay see? | **Ciphertext only.** | Every payload is encrypted before it leaves a node. The relay routes on a small cleartext header. No central moderation of content. |
| What is shared? | **Named network boards**, alongside local-only boards. | A board is either local or networked, and users are told which. Chat, files, games, likes and profiles stay local. |
| How big? | **Small** — a handful to a few dozen nodes. | One relay, one operator, simple data structures (per-message vector of "what I have seen"), manual key ceremonies. |

## Documents

1. [threat-model.md](threat-model.md) — who we defend against, what each
   adversary can and cannot do, and what is explicitly *not* protected. Read
   this first; the protocol only makes sense against it.
2. [protocol.md](protocol.md) — keys, signed documents, the envelope format,
   the relay wire protocol, node behaviour, operator procedures, limits.

## Roles

- **Node** — one Sisyphus BBS instance with its sysop and local users.
- **Relay** — the central store-and-forward server. Untrusted for
  confidentiality and integrity; trusted only for availability.
- **Operator** — the person who decides membership. Holds the **network key**,
  which signs the list of members and boards. The operator usually also runs a
  node and the relay, but the network key lives on neither.

## The shape in one paragraph

Each node has an Ed25519 identity key; the key *is* the node's identity. The
operator signs a **manifest** naming the member nodes and the network boards,
and containing each board's symmetric key wrapped to each member. Nodes dial
*out* to the relay over TLS WebSocket (so they work behind NAT), prove their
identity by signing a challenge, and then publish and subscribe. Every message
is an **envelope**: a small signed header plus an AEAD ciphertext. Each node
numbers and hash-chains its own envelopes per board, and every message records
what its sender had seen from everyone else, so dropped, reordered, or withheld
messages are detectable. The relay keeps about 90 days of ciphertext; a
returning node resumes from its cursor.

## What users and sysops must be told

These are product requirements, not fine print:

- A network board is labelled as such everywhere it appears. Posting there
  sends the post to every member BBS.
- **Deletion is a request, not a guarantee.** A deleted post is removed from
  honest nodes; nothing can recall it from a node that kept it.
- Encryption ends at the BBS, not at the person. Each sysop can read what
  their own node holds, exactly as today.
- The relay operator can see *which nodes* talk and when, but not what is said.

## Roadmap

Each phase ends with something testable; none depends on a later one.

| Phase | Deliverable | Done when |
|---|---|---|
| 0 | This spec, reviewed. | First round answered (protocol.md §14). The operator says go. |
| 1 | `sfp/` library: encodings, envelope seal/open, document sign/verify, chain validation. No networking. | Test vectors in protocol.md Appendix A are generated from it; every MUST in §5–§7 has a negative test. |
| 2 | Operator tool and node key management (`init`, join request, manifest build/sign/verify). | A manifest can be produced for three nodes and verified by the library; tampering anywhere is rejected. |
| 3 | `relay/`: authentication, access control, store, publish/subscribe, limits. Imports `sfp/`, nothing from `lib/`. | In-process tests with scripted nodes cover every error code; malformed and oversized input cannot crash or stall it. |
| 4 | Node integration: schema for remote authors and origin ids, outbox, connector task, network-board UI labelling, local mute/purge tools. | Two nodes and a relay on one machine exchange threads, replies and deletions; one node offline for the exchange catches up correctly. |
| 5 | Hardened deployment of the relay. | Checklist in threat-model.md §6 is met on the real server; 2–3 real nodes soak for two weeks. |
| 6 | Cross-node direct messages (protocol.md §8.4). | As phase 4, for DMs. |
| later | Per-message forward secrecy, attachments, a second relay. | — |

## Impact on the existing codebase (for phase 4)

Noted here so it is not a surprise later:

- `posts.author_id` and `threads.author_id` are `NOT NULL REFERENCES users`.
  Remote authors are not local users and must never become ones; this needs a
  `remote_users` table (or nullable author plus origin columns). It is the same
  design pressure as the open "deleting a user deletes other people's replies"
  question, and should be decided together with it.
- Threads and posts need a globally unique origin id (the envelope id) with a
  `UNIQUE` index, so re-delivery is idempotent.
- The node's identity key and federation state must live **outside** the
  database file, and `admin/reset_db.py` must not delete the identity unless
  asked to explicitly. A reset node rejoins as itself; a node that loses its
  key must be re-enrolled.
- Remote content goes through the same output escaping and length limits as
  local content. The strict Content-Security-Policy already in place is what
  makes displaying other people's text tolerable.
