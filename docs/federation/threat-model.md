# Sisyphus Federation — Threat Model

Status: draft for review. Companion to [protocol.md](protocol.md).

## 1. What we are protecting

| Asset | Why it matters |
|---|---|
| **Content confidentiality** — network-board posts, cross-node DMs | Members expect a private club, not a public feed. |
| **Authenticity** — which node (and which of its users) said what | Forgery destroys a discussion board faster than downtime does. |
| **Completeness and order** — nothing silently dropped, reordered, or withheld | A relay that can quietly edit the conversation by omission can steer it. |
| **Membership** — who is in, who is out, which boards they hold keys for | Invite-only is meaningless if the server can invite. |
| **Node secrets** — identity key, encryption keys, board keys | Everything above rests on these. |
| **Availability** | Wanted, but ranked last: see non-goals. |
| **Metadata** — who talks, when, how much | Protected from the network, *not* from the relay. |

## 2. Trust assumptions

1. **The operator is trusted for membership.** They decide who joins, and their
   offline tool generates board keys, so they can read every network board.
   In an invite-only network run by one person this is inherent, and they are
   a member of every board anyway. The operator's *relay server* gets no such
   trust. (Accepted by the operator on 2026-09-20 "for now"; see protocol.md
   §14 for when to revisit.)
2. **A sysop is trusted by their own users, and by nobody else.** A node
   vouches for its users' names and words. Other nodes accept that vouching at
   face value and can mute the node if it proves worthless.
3. **The relay is trusted for nothing except trying to deliver.** Design as if
   it is already compromised.
4. **libsodium and TLS are sound.** We compose standard primitives and invent
   none.

## 3. Adversaries

**A1 — Network attacker.** On the path between a node and the relay. Passive
or active.

**A2 — Malicious or compromised relay.** Full control of the server: its disk,
memory, TLS private key, and software. The most important adversary, because
the relay is the one machine exposed to the whole internet and the one place
all traffic meets.

**A3 — Malicious or compromised member node.** A legitimate member whose sysop
turns hostile, or whose laptop is taken over.

**A4 — Revoked ex-member.** Was A3 or simply left; still has everything they
ever downloaded, and their old keys.

**A5 — Outsider.** No credentials. Can reach the relay's public port.

**A6 — Hostile user on an honest node.** Posts spam, abuse, or payloads aimed
at other BBSes' web interfaces.

**A7 — Thief of a machine.** Steals a node's laptop, or the operator's.

## 4. What each adversary can and cannot do

"Detectable" means honest nodes notice and alert their sysop; it does not mean
they can fix it.

### A1 — Network attacker

| Can | Cannot |
|---|---|
| See that a machine talks to the relay, when, and roughly how much. | Read anything: TLS outside, AEAD inside. |
| Block or degrade the connection. | Inject, alter, or replay: signatures, per-chain sequence numbers, duplicate suppression by id. |

### A2 — Malicious relay

| Can | Cannot |
|---|---|
| See cleartext headers: sender node, scope (board id or recipient node), sequence number, size bucket, timing. Hence the full who-talks-to-whom-and-when graph. | Read any payload. It holds no board key, no node encryption key, and board names are encrypted too. |
| See the manifest: node ids, node names, which nodes belong to which board id. | Forge or alter an envelope: it has no node's identity key. |
| Refuse service to anyone: drop everything, or everything from one node. **Detectable** once any later message from that chain, or any other member's `seen` vector, arrives. | Drop or reorder *inside* a chain undetectably: `seq` + `prev` hash chain. |
| Withhold the newest messages ("tail drop") from some nodes. **Detectable** as soon as any delivered message's `seen` vector mentions what was withheld. | Hide a tail from a node forever unless it also censors every message from every member who saw it — i.e. partitions the network outright. |
| Show different nodes different subsets (split view). **Detectable** the moment the partitions exchange one message, or two sysops compare notes out of band. | Add a member, restore a revoked one, change board membership, or mint board keys: the manifest is signed by the network key, which is not on the relay. |
| Serve a stale manifest or node descriptor (freeze) for a while. | Roll a manifest back (monotonic `seq`), or freeze one past its `expires`. Serve a descriptor whose encryption keys have all expired. |
| Lie to a rejoining node about its own chain heads. **Detectable**: produces a visible fork or gap, never a forgery. | Impersonate a node to another node. |
| Deliver old-epoch ciphertext to a revoked member (if colluding with A4). | Make members keep encrypting to an old epoch once they have the new manifest. |

Residual risk accepted: **a malicious relay is a complete denial of service and
a complete metadata tap.** One relay is a single point of failure by choice
(small scale). The mitigation is that everything it does beyond dropping is
evident, so the operator can rebuild it elsewhere with the same network key and
no node needs to re-enrol.

### A3 — Malicious member node

| Can | Cannot |
|---|---|
| Read every board it is a member of, and leak it. **No protocol prevents a member from copying what it can read.** | Read boards it is not a member of, or DMs between other nodes. |
| Invent users and posts *under its own node name*. | Post as another node or as `user@othernode`: envelopes are signed by node identity keys and the author's node is taken from the signature, never from the payload. |
| Flood. Bounded by relay rate limits and per-node quotas at receivers; ended by local mute or by revocation. | Delete or alter other nodes' items: a `delete` is honoured only when signed by the node that published the target. |
| Equivocate: sign two different envelopes with the same sequence number. **Detectable** as a fork; receivers keep the first and alert. (A relay replaying an envelope it had refused looks the same; either way a human is told and nothing displayed changes.) | Re-attribute someone else's ciphertext to itself in a way that survives decryption: the header (sender included) is bound as AEAD associated data, and DM keys are direction- and pair-specific. |
| Send hostile *content* (see A6). | Forge history before it joined, or make others accept envelopes after it is revoked. |

### A4 — Revoked ex-member

| Can | Cannot |
|---|---|
| Keep and publish everything it downloaded while a member. | Publish: the relay rejects non-members, and honest nodes reject envelopes from a node their manifest marks revoked, even if a colluding relay delivers them. |
| Decrypt old-epoch ciphertext if a colluding relay hands it over. Bounded: revocation bumps the epoch, the relay refuses stale-epoch publishes, so exposure is limited to what was sent before honest senders learned of the new manifest. | Read anything encrypted under the new epoch: its key was never wrapped to them. |

### A5 — Outsider

| Can | Cannot |
|---|---|
| Open connections to the relay and send garbage until cut off. | Get past the challenge: authentication is a signature by a key in the manifest. There are no passwords to guess and no sign-up endpoint. |
| Attempt resource exhaustion. Bounded by pre-auth limits: 1 KiB frames, 10 s to authenticate, per-address connection caps, no work done on unauthenticated input beyond parsing one small message and verifying one signature. | Learn the membership, board ids, or anything else: nothing is served before authentication. |

### A6 — Hostile user on an honest node

The realistic day-to-day threat. Remote text is attacker-controlled input
arriving in *your* web application.

| Threat | Control |
|---|---|
| Script injection into other BBSes' pages | Items are plain text only — no HTML, no markup, no automatic links. Rendering uses the same autoescaping as local posts, under a CSP with no `unsafe-inline`. |
| Oversized or malformed items | Strict parsing, hard size limits, unknown item types ignored, all before anything touches the database. |
| Name spoofing (`admin@here`) | Remote users are *never* mapped to local accounts, always display as `user@node`, user and node names are ASCII with a narrow character set, and the node part comes from the verified signature. |
| Bidirectional-text and control-character tricks | C0/C1 control characters other than newline and tab are stripped on receipt; remote text is rendered in direction-isolated elements. |
| Spam and harassment | Local mute of a user or a whole node; purge of stored content by origin; escalation to the operator, who can revoke the node. Each sysop's own content policy (e.g. the no-links rule) applies to remote items as it does to local ones. |
| Files | Not federated in v1. Attachments are the largest attack surface a BBS has and are out of scope until the rest has proven itself. |

### A7 — Thief of a machine

| Stolen | Consequence | Control |
|---|---|---|
| A node's laptop | Attacker becomes that node (A3) and can read its boards' history and its stored DMs. | Full-disk encryption; key directory `0700`, files `0600`; optional passphrase on the identity key; operator revokes on report, which rotates every board epoch the node belonged to. Encryption keys rotate, so captured DM traffic older than the retained keys stays sealed. |
| The operator's laptop | Attacker can sign manifests: total compromise of membership and board keys. | Network key is stored passphrase-encrypted (Argon2id), ideally on removable media, and used only by the offline tool. There is no recovery short of founding a new network; treat the key accordingly. |
| The relay's disk | Ciphertext, headers, the manifest, logs. Equivalent to A2's passive view, nothing more. | Payloads were never there in the clear; logs never contain payloads; delivered DMs are deleted on acknowledgement. |

## 5. Non-goals

Stated so nobody assumes otherwise.

1. **Person-to-person end-to-end encryption.** Encryption ends at the node.
   Sisyphus renders pages on the server, so the server necessarily holds
   plaintext; doing crypto in browser JavaScript served by that same server
   would protect nobody from the sysop. Users are told this.
2. **Hiding metadata from the relay.** Payload sizes are bucketed, and board
   names are hidden, but the communication graph is visible to the relay.
3. **Protection from your own sysop**, or from a member who leaks what they
   were entitled to read.
4. **Reliable deletion.** Tombstones are honoured by honest nodes only.
5. **Availability against the relay itself.** Detected, not prevented.
6. **Per-message forward secrecy.** Provided coarsely instead: node encryption
   keys rotate monthly and old secrets are destroyed; board epochs rotate on
   every membership change. A reserved header field allows an ephemeral-key
   upgrade later without a format break. The Signal-style ratchet was
   considered and rejected for v1: its per-peer session state does not survive
   a database reset or a restore from backup, both of which are routine here.
7. **Anonymity or deniability.** Everything is signed, deliberately.
8. **A global total order.** Each author's chain is ordered; display order
   across authors is by clamped timestamp and is advisory.

## 6. Relay deployment requirements

The relay is designed to be worthless to compromise. It should still be hard.

- Minimal OS install; only the relay and a TLS-terminating reverse proxy
  listen publicly (443). SSH key-only, not on the public interface if a VPN or
  provider console makes that possible.
- Dedicated unprivileged user. systemd sandboxing: `NoNewPrivileges`,
  `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `PrivateDevices`,
  `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`, a `SystemCallFilter`,
  a single writable state directory.
- Automatic security updates. Pinned, hash-checked Python dependencies.
- TLS 1.3 only. HSTS is irrelevant (no browsers) but certificate renewal must
  be automated; nodes may additionally pin the key.
- **No admin interface on the network.** Administration is SSH plus files. A
  new manifest is copied up and the relay verifies the network-key signature
  and sequence number before activating it, so even root-by-mistake cannot
  install a manifest the operator did not sign.
- The network *public* key is installed once, by hand. The network *secret*
  key never touches this machine.
- Logs record node ids, scopes, sizes, result codes — never payload bytes,
  never signatures' inputs. Short retention.
- Hard disk quota for the store; per-node and global rate limits; bounded
  memory per connection (protocol.md §13).
- Backups are unnecessary by design: the store is a cache of ciphertext with a
  retention window. Losing it costs catch-up for nodes that were offline, and
  nothing else.

## 7. Implementation requirements that follow from this model

These are as much a part of the security design as the cryptography.

1. **One implementation of the security-critical code.** Envelope sealing and
   opening, document verification, and chain validation live in one library
   used by nodes, the relay, and the operator tool alike, with published test
   vectors and a negative test for every MUST.
2. **Verify before you parse deeply, and parse strictly.** Size-check, then
   strict JSON (reject duplicate keys, non-finite numbers, integers beyond
   2^53, unknown header fields), then signature, then decrypt, then validate
   the item. Nothing reaches the database before all of it passes.
3. **Fail closed.** Unknown version, unknown header field, unknown key id,
   expired manifest, revoked sender: reject. Unknown *item type* inside a valid
   envelope: store nothing, advance the chain, carry on — that is how new
   features roll out without breaking old nodes.
4. **No deserialisation of code-capable formats** (pickle, YAML loaders) on any
   network path. JSON and raw bytes only.
5. **Secrets never in logs, tracebacks, or the database file** that
   `reset_db.py` deletes and that sysops casually copy around.
6. **Every alert in §4 marked "detectable" must actually reach the sysop** —
   an admin-page notice at minimum. Detection nobody sees is not a control.
