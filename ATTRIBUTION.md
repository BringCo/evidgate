# Attribution

evidgate stands on two ideas that already existed elsewhere. This file says
exactly which parts came from where, so nobody has to guess.

## 1. Evidence triples, three-state verdicts, fake-PASS / fake-FAIL discipline

The rules "fresh / verifiable / traceable", "PASS · DIFF(yellow) · FAIL(red)",
"a check must be re-run against a known-bad sample before you trust it", and
"two states is not enough" were adapted from:

- **obra/superpowers** — skill `verification-before-completion`
  (MIT). Content pulled 2026-09-19; locally reorganised, translated and
  extended for document deliverables.

evidgate keeps those ideas and makes them executable. It does not claim to
have invented them.

## 2. "Evidence gate" as a pattern

The framing "an agent's summary is a claim; accept it only against supplied
evidence" is used, at the git-push boundary, by:

- **TestifySec Pushgate** — https://www.testifysec.com/pushgate
  (positioning checked on the vendor page, 2026-11-16)
- **JFrog AppTrust** — policy-as-code for software supply chains

Both gate *code and build artifacts*. evidgate applies the same pattern to
document deliverables — a draft, a report, a set of application materials —
and leaves code to them.

## 3. What this project adds

- **Ledger == check == evidence == resume point.** One table line carries the
  check, the command that produced the evidence, the counter-test, the exit
  code, the artifact hash, the timestamp and the verdict. Reports and ledgers
  are the same read instead of two files that drift.
- **A counter-test is mandatory.** A check without a declared way to go red is
  refused at load time.
- **Prose rules for Chinese technical writing** — absolutes without a search
  date, claim sentences without a citation, statistics without a stated scope
  (`n`, protocol, script path), and body-vs-bibliography citation parity.
- **Mutation check for document gates** — run the same checks against a
  baseline and a planted-defect copy; a check that stays green is reported as
  having no detection power. Mutation testing itself is a well-known technique
  (PIT, mutmut, compose-lint); the application target here — prose gates — is
  what is new.

## Not attributed, because it is not borrowed

The prose rule set, the ledger schema, and the example project are original to
this repository. If you find an overlap we missed, open an issue.
