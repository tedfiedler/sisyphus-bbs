# Sisyphus Federation Protocol (SFP) — version 1

Status: **draft, parked.** Reviewed by the operator on 2026-09-20; the answers
to the first round of questions are recorded in §14. Not scheduled for
implementation yet. Read [threat-model.md](threat-model.md) first.

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are used as in
RFC 2119.

---

## 1. Overview

```
   node A ──┐                         ┌── node C
  (laptop)  │  outbound TLS WebSocket │  (home server)
            ├────────►  RELAY  ◄──────┤
   node B ──┘   stores ciphertext,    └── node D
                enforces the manifest,
                holds no secret that matters

   OPERATOR (offline tool + network key) ──signs──► MANIFEST ──copied to──► relay
```

- Nodes always connect **to** the relay; the relay never connects to a node
  and nodes never connect to each other.
- The operator's signed **manifest** (§5.2) says who the members are, which
  network boards exist, who belongs to each, and carries each board's key
  wrapped to each member.
- Everything a node publishes is an **envelope** (§6): a cleartext routing
  header, an AEAD ciphertext, and an Ed25519 signature over both.
- Each node's envelopes form a hash-linked, numbered **chain** per scope (§7).
- What is inside the ciphertext is an **item** (§8): a thread, a reply, a
  deletion, later a direct message.

## 2. Cryptographic primitives

All from libsodium (expected binding: PyNaCl ≥ 1.5).

| Purpose | Primitive |
|---|---|
| Signatures | Ed25519 (`crypto_sign_detached`) |
| Key agreement | X25519 (`crypto_box_beforenm`) |
| Payload encryption | XChaCha20-Poly1305-IETF AEAD, 24-byte random nonce |
| Wrapping a board key to one node | `crypto_box_seal` (X25519 + XSalsa20-Poly1305, anonymous sender; authenticity comes from the manifest signature around it) |
| Hashing, ids | SHA-256 |
| Key derivation | BLAKE2b-256, keyed, with personalisation |
| Passphrase protection of stored secret keys | Argon2id (`crypto_pwhash`) + XChaCha20-Poly1305 |

Implementations MUST use the library's verification functions as-is (they
reject non-canonical signatures and small-order points) and MUST treat any
library error as rejection of the input.

Every signature has a **domain-separation prefix** so that a signature made for
one purpose can never be valid for another:

| Context | Prefix (ASCII, followed by one `0x00` byte) |
|---|---|
| Envelope | `SFP1-envelope` |
| Relay authentication | `SFP1-auth` |
| Manifest | `SFP1-manifest` |
| Node descriptor | `SFP1-descriptor` |

## 3. Encodings

- **Binary in JSON**: base64url without padding (RFC 4648 §5). Decoders MUST
  reject padding, characters outside the alphabet, and non-canonical trailing
  bits.
- **JSON**: UTF-8, no BOM. Parsers MUST reject duplicate object keys,
  `NaN`/`Infinity`, and integers outside `0 … 2^53−1`. Wire messages are JSON
  text frames, one object per frame.
- **Signed things are transmitted as the exact bytes that were signed.**
  Headers and documents travel as base64url-encoded byte strings; the receiver
  verifies the signature over those bytes and only then interprets them as
  JSON. There is no canonicalisation step to get wrong.
- **Time**: integer milliseconds since the Unix epoch, UTC.
- `u16be(x)`, `u32be(x)`: unsigned big-endian integers. `‖` is concatenation.

## 4. Identities and keys

| Key | Type | Held by | Lifetime | Identifies / protects |
|---|---|---|---|---|
| **Network key** `NK` | Ed25519 | Operator, **offline** | Life of the network | Signs the manifest. `net` = base64url(`NK` public). |
| **Node identity key** `IK` | Ed25519 | Each node | Life of the node | `node_id` = base64url(`IK` public), 43 characters. Signs envelopes, descriptors, and the relay challenge. |
| **Node encryption key** `EK` | X25519 | Each node | 30 days, overlapping | Receives wrapped board keys and direct messages. `kid` = base64url(first 8 bytes of SHA-256(`EK` public)). |
| **Board epoch key** | 32 random bytes | Every member of the board | Until the next epoch | Encrypts that board's items. Identified by `(board_id, epoch)`. |

**Fingerprint.** For humans comparing keys out of band: the first 20 bytes of
SHA-256(`IK` public) as ten groups of four hex digits.

**Names.** A node has a name matching `^[a-z0-9][a-z0-9-]{1,31}$`, unique in
the network, assigned in the manifest. Users appear as `user@nodename`. The
name is a label; the key is the identity.

**Storage.** A node keeps `IK`, its `EK` secrets, and its unwrapped board keys
in a directory outside the database (`federation/`, mode `0700`, files `0600`),
optionally passphrase-encrypted. `admin/reset_db.py` MUST NOT remove it unless
explicitly asked. Losing `IK` means re-enrolment as a new node.

**Encryption-key rotation.** A node generates a new `EK` every 30 days and
publishes it at least 7 days before the old one's `not_after`. It MUST keep an
old `EK` secret until `not_after` + 90 days (the relay's retention window),
then destroy it. Senders MUST NOT encrypt to a key outside its validity window.

## 5. Signed documents

Both documents use one wire form:

```json
{ "d": "<base64url of the document's JSON bytes>", "s": "<base64url signature>" }
```

signature = Ed25519(key, prefix ‖ 0x00 ‖ d_bytes).

### 5.1 Node descriptor

Signed by the node's `IK`. Tells others how to encrypt to this node.

```json
{
  "v": 1,
  "net": "<NK public>",
  "node": "<node_id>",
  "seq": 7,
  "issued": 1790000000000,
  "enc": [
    { "kid": "q83vEjRWeJA", "pk": "<X25519 public>",
      "not_before": 1789000000000, "not_after": 1791592000000 }
  ]
}
```

A verifier MUST check: signature by `node`; `net` matches; `seq` is greater
than any descriptor already held for that node (equal with identical bytes is
a no-op); at least one `enc` entry is currently valid; at most 4 entries.

Descriptors are uploaded to and served by the relay. A stale descriptor from a
malicious relay is bounded by `not_after`.

### 5.2 Manifest

Signed by `NK`. The single source of truth for membership.

```json
{
  "v": 1,
  "net": "<NK public>",
  "seq": 12,
  "issued": 1790000000000,
  "expires": 1797776000000,
  "relay": "relay.example.net",
  "nodes": [
    { "id": "<node_id>", "name": "sisyphus", "status": "active",  "joined": 1788000000000 },
    { "id": "<node_id>", "name": "tantalus", "status": "revoked", "joined": 1788500000000,
      "revoked": 1789900000000 }
  ],
  "boards": [
    {
      "id": "<16 random bytes>",
      "epoch": 3,
      "members": ["<node_id>", "<node_id>"],
      "meta": "<AEAD ciphertext of {\"name\":…,\"description\":…} under the epoch key>",
      "meta_n": "<24-byte nonce>",
      "wraps": [
        { "epoch": 3, "to": "<node_id>", "kid": "q83vEjRWeJA", "box": "<crypto_box_seal of the 32-byte key>" },
        { "epoch": 2, "to": "<node_id>", "kid": "q83vEjRWeJA", "box": "…" }
      ]
    }
  ]
}
```

Rules:

1. A node pins `NK` public at enrolment and MUST reject any manifest not signed
   by it. There is no in-band way to change `NK` in v1 (field `next_nk` is
   reserved).
2. `seq` MUST be greater than the manifest currently held. **Never accept a
   lower `seq`**, from anyone.
3. `expires` is at most 90 days after `issued`. Past it, a node MUST stop
   publishing and MUST stop applying incoming envelopes — it no longer knows
   who the members are. It keeps displaying what it has, tells the sysop, and
   does not advance its cursors, so nothing is lost: once a fresh manifest
   arrives it resumes from where it stopped. (This bounds how long a malicious
   relay can hide a revocation. The operator re-signs on a calendar; nodes warn
   their sysop from 14 days out.)
4. Revoked nodes stay listed, as `revoked`, forever. A name MUST NOT be given
   to a different key unless the new entry carries `"replaces": "<old
   node_id>"`; nodes surface such a change to the sysop.
5. `members` lists only `active` nodes. A board's `epoch` MUST increase
   whenever a node is removed from `members`, and MAY increase at any time.
6. `wraps` MUST contain the current epoch's key for every member. It SHOULD
   also retain earlier epochs' wraps for as long as the relay's retention
   window could still hold envelopes from those epochs. **A new member is
   given existing history by default:** the tool wraps to them every epoch key
   still within the retention window, so on first sync they read whatever the
   relay still holds. The operator MAY admit a node "from now on" instead, by
   wrapping only the current epoch. History older than the retention window is
   not available from the relay either way.
7. The AEAD associated data for `meta` is
   `"SFP1-boardmeta" ‖ 0x00 ‖ board_id_bytes ‖ u32be(epoch)`.
8. Size limit: 1 MiB.

The relay learns node names, board ids, and membership from the manifest. It
does not learn board names, and it cannot unwrap a key.

## 6. Envelopes

### 6.1 Wire form

```json
{ "h": "<base64url header bytes>", "c": "<base64url ciphertext>", "s": "<base64url signature>" }
```

```
signing_input = "SFP1-envelope" ‖ 0x00 ‖ u32be(len(h_bytes)) ‖ h_bytes ‖ c_bytes
s             = Ed25519(IK_sender, signing_input)
id            = SHA-256(signing_input)          (32 bytes; base64url when written)
```

The id excludes the signature, so it does not depend on signature encoding.

### 6.2 Header

`h_bytes` is JSON with **exactly** these fields:

| Field | Type | Meaning |
|---|---|---|
| `v` | int | `1` |
| `net` | string | `NK` public. Prevents replay into another network. |
| `from` | string | Sender's `node_id`. |
| `scope` | string | `b:<board_id>` or `n:<recipient node_id>`. |
| `seq` | int ≥ 1 | Position in the sender's chain for this scope (§7). |
| `prev` | string or null | `id` of the sender's previous envelope in this scope; `null` iff `seq` is 1. |
| `key` | object | Board scope: `{"epoch": n}`. Node scope: `{"to": "<recipient kid>", "from": "<sender kid>"}`. |
| `n` | string | 24-byte AEAD nonce, fresh random per envelope. |

A header with a missing, extra, or wrongly typed field MUST be rejected.
(Field `eph` is reserved for a future ephemeral-key upgrade; a v1 node rejects
it like any unknown field, so that upgrade will be a `v` bump.)

The relay can read the header. It contains nothing about the item's type,
author, content, or when it was written — the authoring time travels inside
the ciphertext (§8 `at`); the relay knows only when it was published.

### 6.3 Encryption

```
c_bytes = XChaCha20-Poly1305-IETF.encrypt(key, nonce = n, ad = h_bytes, plaintext = P)
```

Binding the whole header as associated data means a ciphertext cannot be moved
to another sender, scope, sequence number, or network and still decrypt.

**Board scope.** `key` = the board's epoch key for `header.key.epoch`.

**Node scope.**

```
shared = crypto_box_beforenm(EK_recipient_public, EK_sender_secret)
key    = BLAKE2b-256(key = shared, person = "SFP1-direct",
                     data = IK_sender_public ‖ IK_recipient_public)
```

Putting the identities in order makes the key directional, so a message from A
to B can never be reflected back to A as if from B.

### 6.4 Plaintext and padding

```
P = u32be(len(item_json)) ‖ item_json ‖ zero bytes
```

padded so that `len(P)` is the smallest of 512, 1024, 2048, 4096, or a
multiple of 4096 that fits. Senders MUST zero the padding; receivers MUST
ignore it. `len(item_json)` MUST be ≤ 98 304; `len(P)` ≤ 102 400. No
compression, anywhere.

### 6.5 Receiving: the validation order

A node processes an incoming envelope in exactly this order and stops at the
first failure. Steps 1–6 are also what the relay does on publish.

1. **Size**: `h` ≤ 1 KiB decoded, `c` ≤ 102 416 bytes decoded, `s` exactly 64.
2. **Parse** `h_bytes` strictly (§3, §6.2). `v` = 1, `net` = mine.
3. **Membership**: my manifest is unexpired and `from` is `active` in it. For
   a board scope, `from` ∈ `members` and so am I; for a node scope, the
   recipient is me (the relay instead checks that the recipient is `active`).
4. **Signature**: verify `s` over `signing_input` with `from`.
5. **Duplicate**: if `id` is already stored, acknowledge and stop — success.
6. **Chain**: check against §7. (The new head is committed in step 10, or
   with the envelope when step 7 sets it aside.)
7. **Key**: look up the epoch key, or derive the direct key.
   - Epoch newer than my manifest's, or a key id I do not recognise: fetch the
     manifest (or descriptor), retry once; if still unknown, store the raw
     envelope as *undecryptable*, advance the chain, alert the sysop, and
     retry whenever a new manifest arrives.
   - Epoch older than the first epoch the operator ever gave me a key for:
     this is history from before I joined. Advance the chain, store nothing,
     no alert.
   - An older epoch whose key I hold is fine: the sender published before the
     rotation reached it.
8. **Decrypt** with `ad = h_bytes`. Failure is a rejection and a sysop alert:
   a member signed something that does not decrypt.
9. **Unpad and parse the item** strictly; validate per §8.
10. **Apply** to the database in one transaction together with the chain
    update.

**Revocation is retroactive for anything not yet stored.** Once a node's
manifest marks `X` revoked (or removes `X` from a board), it rejects every
envelope from `X` (in that board) it has not already applied — including ones
`X` published while still a member. What is
already stored stays until the sysop purges it. This loses a late-syncing node
the last few legitimate posts of a removed member; that is the price of a rule
with no edge cases.

## 7. Chains

For each `(from, scope)` a sender's envelopes are numbered 1, 2, 3 … and each
names its predecessor's id.

**Sender.** `seq` = last + 1; `prev` = last id, allocated when the envelope is
sealed for sending (§10), strictly in order. A sender MUST NOT sign a second,
different envelope for a `(scope, seq)` unless the relay `nack`ed the first;
the one legitimate case is `stale-epoch` (§9.5), where the same item is
re-sealed under the new key.

**Receiver**, holding head `(k, id_k)` for that chain:

| Incoming | Action |
|---|---|
| `seq` = k+1 and `prev` = `id_k` | Accept; head becomes `(k+1, id)`. |
| `seq` ≤ k, same `id` as stored | Duplicate; ignore. |
| `seq` ≤ k, different `id` | **Fork.** Keep what is stored, discard this, record both ids, alert the sysop. A fork proves that *either* the sender signed twice *or* the relay is replaying an envelope it had refused; both are worth a human's attention and neither can alter what honest nodes display. |
| `seq` = k+1, `prev` ≠ `id_k` | **Fork** (as above). |
| `seq` > k+1 | **Gap.** Buffer (at most 256 per chain), request the missing range (§9.6). If unfilled after 10 minutes online, alert. Buffered envelopes are applied in order once the gap closes. |

A node that first sees a chain at `seq` > 1 — it joined late, or the relay's
retention has moved on — records the chain as *starting at* that `seq` and
validates onward from there.

**`seen` vector.** Every board item (§8) carries `seen`: for each *other*
member whose chain in this scope the sender holds contiguously, the highest
`seq` held, keyed by the first 16 characters of that member's `node_id`.
A receiver that finds `seen[Y]` greater than its own head for `Y` knows
envelopes exist that it has not been given; it requests them, and alerts if
the relay cannot produce them. This is what turns "the relay withheld the
latest messages" from invisible into evident. It also lets a client order
replies causally where timestamps disagree.

**After a reset or restore.** A node that has lost its local chain state asks
the relay for its own heads (§9.3 `welcome.heads`) and continues from them.
The relay is not trusted for this: a wrong answer produces a fork or a gap
that other nodes detect. It can only ever cause a visible failure.

## 8. Items

The decrypted `item_json`. Unknown *fields* MUST be ignored. An unknown `t`
MUST be skipped without error (the envelope still advances the chain).

An item's identity is the `id` of the envelope that carried it: globally
unique, unforgeable, and free.

Common fields:

| Field | Type | Notes |
|---|---|---|
| `t` | string | Item type. |
| `user` | string | Author's username on the sending node. MUST match `^[A-Za-z0-9][A-Za-z0-9_.-]{1,31}$`. Displayed as `user@nodename`, where the node name comes from the manifest entry for the envelope's **verified** `from`. Nothing inside the item can name a node. |
| `at` | int | When the user wrote it. Display uses `min(at, time_received)`. |
| `seen` | object | §7. Board scope only. |

All text fields: Unicode, NFC-normalised by the sender; receivers strip C0/C1
control characters other than `\n` and `\t`. **Plain text. No markup, ever.**

### 8.1 `thread`

```json
{ "t": "thread", "user": "alice", "at": 1790000000000,
  "subject": "…", "body": "…", "seen": { "k3J9…16chars": 41 } }
```

`subject` 1–128 characters, `body` 1–20 000 characters (the local limits).

### 8.2 `post`

```json
{ "t": "post", "user": "bob", "at": 1790000050000,
  "thread": "<id of the thread envelope>", "body": "…", "seen": { } }
```

`thread` MUST name a `thread` item in the same board. If the receiver does not
have it yet, the post is held (bounded, 30 days) and applied when it arrives.
A post to a deleted thread is dropped.

### 8.3 `delete`

```json
{ "t": "delete", "user": "alice", "at": 1790000090000,
  "target": "<id of the envelope to remove>", "seen": { } }
```

Honoured **only if the `delete` envelope's verified `from` equals the target
envelope's `from`.** The originating node is the authority over what it
published: its users delete their own posts through it, and its sysop
moderates through it. Deleting a thread removes its replies on the receiver.
The receiver keeps a tombstone (the id) so a late-arriving copy stays deleted.

There is no network-wide moderation message in v1. A sysop can locally hide
any item, user, or node; the operator can revoke a node.

When a local user is deleted, their node SHOULD publish `delete` for their
network items.

### 8.4 `dm` and `dm.bounce` (phase 6)

Node scope. Chains, signatures and validation are identical; there is no
`seen`.

```json
{ "t": "dm", "user": "alice", "to": "carol", "at": 1790000000000, "body": "…" }
```

`body` 1–2 000 characters. If `to` does not exist on the recipient node, it
replies `{"t":"dm.bounce","ref":"<id>"}` so the sender learns the message went
nowhere. Bounces are **on by default**; a sysop MAY turn them off, since they
confirm to other member nodes which usernames exist.

### 8.5 Not federated

Live chat, files, games and scores, likes, profiles, the user directory, and
everything the file-access gate counts. Remote activity MUST NOT count toward
any local privilege.

## 9. Relay protocol

### 9.1 Connection

`wss://<manifest.relay>/sfp/1`, TLS 1.3, WebPKI validation; a node MAY also
pin the key. JSON text frames. Each message is an object with an `op` field.

Before authentication the relay accepts one frame of at most 1 KiB and closes
after 10 seconds. After it, it accepts frames up to 192 KiB (one envelope, with
room to spare). Nodes accept frames up to 2 MiB from the relay, which is what a
full-size manifest needs. Keepalive: WebSocket ping
every 30 s; either side closes after 90 s of silence. One connection per node:
a new authenticated connection replaces the old.

### 9.2 Authentication

```
relay → {"op":"challenge","nonce":"<32 random bytes>","time":<relay ms>}
node  → {"op":"auth","node":"<node_id>","sig":"<signature>"}

sig = Ed25519(IK, "SFP1-auth" ‖ 0x00 ‖ nonce ‖ u16be(len(host)) ‖ host ‖ IK_public)
```

`host` is `manifest.relay`, the name the node dialled, as ASCII. The relay
verifies with the claimed key and requires the node to be `active` in its
manifest. On any failure it closes without explanation.

The relay does not authenticate itself beyond TLS. It does not need to:
nothing it says is believed without a signature from somebody else.

### 9.3 Session start

```
relay → {"op":"welcome",
         "manifest_seq": 12,
         "limits": {…§13 values in force…},
         "retention_days": 90,
         "heads": { "<scope>": {"seq": 41, "id": "…"} }}      ← the node's OWN chains
```

The node then, in order: fetches the manifest if `manifest_seq` is newer than
its own; uploads its descriptor if changed; fetches descriptors it lacks;
subscribes; drains its outbox.

### 9.4 Operations

Node → relay:

| `op` | Fields | Reply |
|---|---|---|
| `get_manifest` | — | `manifest` `{doc}` |
| `put_descriptor` | `doc` | `ok` / `error` |
| `get_descriptors` | `nodes: [node_id]`, at most 32 | `descriptors` `{docs: […]}` |
| `sub` | `scope`, `after` (relay offset, 0 for all) | optional `notice`, then `event`…, then `eose`, then live `event`s |
| `unsub` | `scope` | `ok` |
| `pub` | `env` | `ack` `{id, offset}` or `nack` `{id, code, expect?}` |
| `get` | `scope`, `from`, `lo`, `hi` (seq range, ≤ 256) | `event`… then `eose` |
| `ack` | `scope`, `offset` — node scopes only | — |

Relay → node, unsolicited: `event` `{scope, offset, env}`,
`manifest_changed` `{seq}`, `notice` `{scope, code, …}`.

### 9.5 Publishing

On `pub` the relay performs §6.5 steps 1–6 with itself as verifier, plus:

- the authenticated node MUST equal `header.from`;
- board scope: `header.key.epoch` MUST equal the manifest's current epoch for
  that board, else `nack stale-epoch` (the node refetches the manifest and
  re-seals; the rejected envelope was never accepted, so its `seq` is reused);
- chain: `seq` MUST be exactly head + 1 with matching `prev`, else
  `nack bad-seq` with `expect: {seq, id}`. A re-`pub` of an already stored `id`
  is `ack`ed again — publishing is idempotent, so a node that lost the `ack`
  simply retries;
- rate and quota limits (§13), else `nack rate`.

Accepted envelopes get the next **offset** in their scope — a relay-local
cursor with no security meaning — are written to disk, acknowledged, and fanned
out to current subscribers.

The relay enforces the chain so that honest nodes rarely see a gap; nodes
verify the chain themselves because the relay may not be honest.

### 9.6 Subscribing and catching up

A node stores `cursor[scope]` = the highest offset it has fully applied, and
subscribes with `after = cursor`. If `after` is older than the relay's oldest
retained offset, the relay first sends `notice {code:"truncated", oldest}`;
the node records a history gap for the sysop and carries on. There is no
backfill beyond retention in v1.

Access: a board scope may be subscribed to and published in only by its
members; `n:<X>` may be subscribed to only by `X` and published in by any
active node.

Offsets are hints for efficient resumption. Correctness rests on ids (for
duplicates) and chains (for completeness), never on offsets.

### 9.7 Retention

Board scopes: 90 days or the store quota, oldest first. Node scopes: until the
recipient `ack`s, at most 30 days. Envelopes of a revoked node are no longer
served. The relay MAY discard anything at any time; the protocol stays correct
(nodes detect the gap), only less useful.

### 9.8 Error codes

`bad-frame`, `too-large`, `bad-header`, `wrong-net`, `not-member`, `bad-sig`,
`bad-seq`, `stale-epoch`, `unknown-scope`, `forbidden`, `rate`, `quota`,
`manifest-expired`, `internal`. After `bad-frame`, `too-large`, or three
`bad-sig` in a session, the relay closes the connection.

## 10. Node behaviour

**Outbox.** Publishing a network item is two local steps in one transaction:
write the post as usual, and queue the *item* (plaintext; it is already in the
local database as a post) for its scope. A background task, when connected and
holding a current manifest, takes queued items oldest first, and for each:
allocates `(seq, prev)`, builds `seen`, seals under the current epoch, signs,
records the sealed envelope, sends it, and on `ack` removes it from the queue.
Offline is the normal case, not an error: the queue just waits, and sealing
late means a post written during a week offline goes out under the key that is
current when it is finally sent. If the connection drops before the `ack`, the
*recorded* envelope is sent again unchanged (publishing is idempotent). Only on
`nack stale-epoch` is the item re-sealed, at the same `seq`.

**Own posts** are applied locally at once and are not re-applied when they echo
back from the relay (duplicate by id).

**New manifest.** Verify (§5.2); unwrap any new board keys addressed to me and
store them; for each newly revoked node, stop accepting its envelopes; for each
board I was removed from, stop publishing and mark it read-only. Never delete
old epoch keys while envelopes from those epochs may still arrive.

**Local policy** runs after validation and never changes what is *stored*:
an item is kept exactly as it was signed, and policy acts on what is shown.
Per-user and per-node mutes and per-node daily quotas (default 500 items)
hide items. The sysop's no-links rule does not hide a remote post: the post
is shown with each link replaced by a fixed placeholder (`[link removed]`),
using the same pattern that rejects links in local posts. Admins, who may post
links locally, see remote links as plain, unlinked text. Hidden and
neutralised items still advance chains.

**Alerts** the sysop MUST be shown: fork, unfillable gap, `seen` ahead of what
the relay will supply, decryption failure from a member, manifest expiring
within 14 days or expired, a node name re-keyed via `replaces`, history
truncated on catch-up.

## 11. Operator procedures

All performed with the offline tool on the operator's own machine. The relay
is only ever handed finished, signed files.

**Founding.** Generate `NK` (stored passphrase-encrypted). Create the first
manifest with the operator's own node. Install `NK` *public* on the relay.

**Admitting a node.**
1. The prospective sysop runs `init` locally. This generates `IK` and the first
   `EK` and prints a **join request**: their signed descriptor plus a proposed
   name.
2. They send it to the operator and, **over a separate channel the two already
   trust — in person, a phone call, Signal —** read out the fingerprint (§4).
3. The operator verifies descriptor signature and fingerprint, adds the node,
   chooses its boards, and signs a new manifest. The tool wraps each chosen
   board's current key to the new node.
4. The operator gives the sysop the relay host name and `NK` public (again with
   its fingerprint confirmed out of band), and copies the manifest to the relay.

No secret ever travels. Everything exchanged is public; the out-of-band step
exists only to make sure it is the *right* public key.

**Removing or revoking a node.** Mark it `revoked`; remove it from every
board's `members`; the tool generates a fresh epoch key for each of those
boards and wraps it to the remaining members; sign; copy up. Do this promptly:
confidentiality against the removed node begins when honest senders receive
this manifest.

**Routine.** Re-sign before `expires` (the tool fetches current descriptors
from the relay, verifies each against the manifest, and re-wraps current epoch
keys to any rotated `EK`). Rotate a board's epoch whenever a member reports a
compromise.

## 12. Versioning

The WebSocket path and the header's `v` carry the major version. Within v1:
new item types and new item fields are ignored by older nodes; new *header*
fields are not allowed. A change to the header, the signing input, or the
cryptography is v2, negotiated by path.

## 13. Limits

Defaults; the relay advertises the values in force in `welcome`.

| Limit | Value |
|---|---|
| Header, decoded | 1 024 bytes |
| Item JSON | 98 304 bytes |
| Padded plaintext / ciphertext | 102 400 / 102 416 bytes |
| Frame accepted by relay, before / after auth | 1 KiB / 192 KiB |
| Frame accepted by node | 2 MiB |
| Time to authenticate | 10 s |
| Unauthenticated connections per address | 4 |
| Publishes per node | 30 per minute (burst 60), 2 000 per day |
| `get` range | 256 envelopes |
| Buffered out-of-order envelopes per chain | 256 |
| Posts held waiting for their thread | 1 000 per board, 30 days |
| Manifest / descriptor size | 1 MiB / 4 KiB |
| Retention, board / node scope | 90 days / until `ack`, max 30 days |
| Nodes per network (design target) | ≤ 50 |

## 14. Review record

### Decided by the operator, 2026-09-20

| # | Question | Decision | Where |
|---|---|---|---|
| 1 | What history does a new member get? | **Existing history** — everything the relay still holds — by default; "from now on" remains an option at admission. | §5.2 rule 6 |
| 2 | Manifest lifetime? | **90 days.** A quarterly re-sign is acceptable. | §5.2 rule 3 |
| 3 | Bounce undeliverable DMs? | **Yes**, on by default; a sysop may disable. | §8.4 |
| 4 | Is it acceptable that the operator can read every network board? | **Yes, for now.** Revisit if the network grows beyond people who already trust the operator; the alternative is a member node acting as key steward per board. | threat-model §2 |
| 5 | How does a no-links rule treat remote posts? | **Show the post with links neutralised**, not hidden. Stored unchanged. | §10 |

### Still open

Nothing is blocking. The operator wants more time with the design before any
of it is built; further questions get added here as they come up. Known to be
waiting for phase 4:

- How remote authors are represented in the database, to be decided together
  with the existing question of what deleting a local user does to other
  people's replies.

## 15. Reserved for later versions

Per-message forward secrecy via an ephemeral sender key (`eph`); network-key
rollover (`next_nk`); attachments as separately encrypted, content-addressed
blobs with their own quotas; a second relay with nodes publishing to both;
per-user signing keys, should a native client ever exist.

## Appendix A. Test vectors

To be generated by the phase 1 reference implementation and committed here:
fixed keys and nonce → header bytes, signing input, id, signature, ciphertext,
for one board envelope and one direct envelope; a signed descriptor and
manifest; and for each, a set of single-bit and single-field mutations that
MUST be rejected, each labelled with the step of §6.5 that rejects it.
