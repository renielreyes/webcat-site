#!/usr/bin/env python3
"""
zone-diff.py — compare two DNS zone snapshot files and report what changed.

PURPOSE
    After a human edits DNS, take a "before" and an "after" text snapshot of the
    zone and run this tool to confirm that ONLY the intended records changed.
    It touches nothing live — it just reads two text files and prints a report.

USAGE
    python3 scripts/zone-diff.py BEFORE.txt AFTER.txt
        Compare the two snapshots. Prints three labelled sections — ADDED,
        REMOVED, CHANGED — then a one-line verdict.

    python3 scripts/zone-diff.py --selftest
        Run built-in example cases (identical / added / removed / changed) and
        print PASS/FAIL per case.

    python3 scripts/zone-diff.py --help
        Show this usage.

EXIT CODES
    0   The two files match (no differences), or --selftest passed, or --help.
    1   Differences were found (ADDED / REMOVED / CHANGED), or --selftest failed.
    2   Usage error (wrong arguments, or a file could not be read).

HOW LINES ARE READ (tolerant parsing)
    - Blank lines are ignored.
    - Comment lines whose first non-space character is '#' or ';' are ignored.
    - Repeated whitespace is collapsed to a single space.
    - Record names and record types are compared case-insensitively.
    - A line is treated as a DNS RECORD when it looks like "name [ttl] [class]
      TYPE value..." — i.e. it has a recognised record TYPE token (A, AAAA,
      CNAME, MX, TXT, NS, SOA, ...) with a name before it and a value after it.
      Records are compared by (name, type); a change in value OR ttl is a CHANGE.
    - Any other non-blank, non-comment line is compared as plain TEXT (present
      in one file but not the other shows up under ADDED / REMOVED).
"""

import sys
from collections import Counter, namedtuple

# Recognised DNS record types. If the second-or-later token on a line matches
# one of these (case-insensitively), the line is treated as a record.
KNOWN_TYPES = {
    "A", "AAAA", "AFSDB", "ALIAS", "CAA", "CDNSKEY", "CDS", "CERT", "CNAME",
    "DNSKEY", "DS", "HINFO", "HTTPS", "LOC", "MX", "NAPTR", "NS", "NSEC",
    "NSEC3", "PTR", "RP", "RRSIG", "SOA", "SPF", "SRV", "SSHFP", "SVCB",
    "TLSA", "TXT", "URI",
}

DNS_CLASSES = {"IN", "CH", "HS", "CS"}

# A normalised record. name is lower-cased, rtype is upper-cased, ttl is a
# string of digits (or "" when absent), value is whitespace-collapsed as-is.
Record = namedtuple("Record", ["name", "rtype", "ttl", "value"])


def parse_record(line):
    """Return a Record if the line looks like a DNS record, else None."""
    tokens = line.split()
    if len(tokens) < 3:
        return None
    # Find the first recognised TYPE token, but not at position 0 (a record
    # needs a name before its type).
    type_idx = None
    for i in range(1, len(tokens)):
        if tokens[i].upper() in KNOWN_TYPES:
            type_idx = i
            break
    if type_idx is None:
        return None
    value_tokens = tokens[type_idx + 1:]
    if not value_tokens:
        return None  # a record must have a value
    name = tokens[0].lower()
    rtype = tokens[type_idx].upper()
    # TTL, if present, is the first all-digits token between name and type.
    ttl = ""
    for t in tokens[1:type_idx]:
        if t.isdigit():
            ttl = t
            break
    value = " ".join(value_tokens)
    return Record(name, rtype, ttl, value)


def parse_snapshot(text):
    """Parse snapshot text into (records, texts).

    records: list[Record]
    texts:   list[str]  (whitespace-collapsed plain-text lines)
    """
    records = []
    texts = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped[0] in "#;":
            continue
        record = parse_record(stripped)
        if record is not None:
            records.append(record)
        else:
            texts.append(" ".join(stripped.split()))
    return records, texts


def _record_units(records):
    """Map (name, rtype) -> Counter of (ttl, value) units (a multiset)."""
    grouped = {}
    for r in records:
        key = (r.name, r.rtype)
        grouped.setdefault(key, Counter())[(r.ttl, r.value)] += 1
    return grouped


def _fmt_unit(name, rtype, ttl, value):
    return "{} {} (ttl {}) {}".format(name, rtype, ttl or "-", value)


def _fmt_units(name, rtype, counter):
    """Sorted, human-readable list of units under one (name, rtype) key."""
    out = []
    for (ttl, value), n in sorted(counter.items()):
        for _ in range(n):
            out.append(_fmt_unit(name, rtype, ttl, value))
    return out


def _fmt_values(counter):
    """Sorted list of just the 'ttl value' part of each unit (for CHANGED)."""
    out = []
    for (ttl, value), n in sorted(counter.items()):
        for _ in range(n):
            out.append("(ttl {}) {}".format(ttl or "-", value))
    return out


def diff_snapshots(before_text, after_text):
    """Compare two snapshot texts.

    Returns a dict with keys 'added', 'removed', 'changed' (lists of strings
    ready to print) so both the CLI and the self-test can use it.
    """
    b_records, b_texts = parse_snapshot(before_text)
    a_records, a_texts = parse_snapshot(after_text)

    b_units = _record_units(b_records)
    a_units = _record_units(a_records)

    added = []
    removed = []
    changed = []

    all_keys = sorted(set(b_units) | set(a_units))
    for key in all_keys:
        name, rtype = key
        b = b_units.get(key, Counter())
        a = a_units.get(key, Counter())
        if b == a:
            continue
        if not b:
            # Key only in "after" -> every unit is added.
            added.extend(_fmt_units(name, rtype, a))
        elif not a:
            # Key only in "before" -> every unit is removed.
            removed.extend(_fmt_units(name, rtype, b))
        else:
            # Same name+type, different value/ttl set -> a change.
            entry = ["{} {}".format(name, rtype)]
            for line in _fmt_values(b):
                entry.append("    before: " + line)
            for line in _fmt_values(a):
                entry.append("    after:  " + line)
            changed.append("\n".join(entry))

    # Plain-text lines: multiset difference, in each direction.
    b_text_counts = Counter(b_texts)
    a_text_counts = Counter(a_texts)
    for line in sorted((a_text_counts - b_text_counts).elements()):
        added.append("text: " + line)
    for line in sorted((b_text_counts - a_text_counts).elements()):
        removed.append("text: " + line)

    return {"added": added, "removed": removed, "changed": changed}


def print_report(before_name, after_name, result):
    """Print the ADDED / REMOVED / CHANGED report and a one-line verdict."""
    added = result["added"]
    removed = result["removed"]
    changed = result["changed"]

    print("zone-diff: comparing '{}' -> '{}'".format(before_name, after_name))
    print()

    print("ADDED ({})".format(len(added)))
    for line in added:
        print("  + " + line)
    print()

    print("REMOVED ({})".format(len(removed)))
    for line in removed:
        print("  - " + line)
    print()

    print("CHANGED ({})".format(len(changed)))
    for entry in changed:
        lines = entry.split("\n")
        print("  ~ " + lines[0])
        for extra in lines[1:]:
            print("  " + extra)
    print()

    if not added and not removed and not changed:
        print("Verdict: MATCH - before and after are equivalent.")
    else:
        print("Verdict: DIFFERENCES - {} added, {} removed, {} changed.".format(
            len(added), len(removed), len(changed)))


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #

def run_selftest():
    """Run built-in example cases; return True only if all pass."""
    # The "identical" case deliberately differs in casing, whitespace, comments
    # and blank lines, to prove tolerant parsing still sees them as equivalent.
    base = (
        "; zone snapshot\n"
        "@        IN  SOA  ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600\n"
        "www      3600 IN A     93.184.216.34\n"
        "mail     3600 IN MX    10 mail1.example.com.\n"
    )
    identical_reformatted = (
        "# same zone, reformatted\n"
        "\n"
        "@ in soa   ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600\n"
        "WWW  3600  IN  a    93.184.216.34\n"
        "MAIL 3600 in mx 10 mail1.example.com.\n"
    )
    added_after = base + "ftp      3600 IN A     93.184.216.35\n"
    removed_after = (
        "@        IN  SOA  ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600\n"
        "www      3600 IN A     93.184.216.34\n"
    )  # mail MX removed
    changed_after = (
        "@        IN  SOA  ns1.example.com. admin.example.com. 1 7200 3600 1209600 3600\n"
        "www      3600 IN A     93.184.216.99\n"   # value changed
        "mail     3600 IN MX    10 mail1.example.com.\n"
    )

    cases = [
        # (label, before, after, exp_added, exp_removed, exp_changed)
        ("identical", base, identical_reformatted, 0, 0, 0),
        ("added", base, added_after, 1, 0, 0),
        ("removed", base, removed_after, 0, 1, 0),
        ("changed", base, changed_after, 0, 0, 1),
    ]

    all_pass = True
    for label, before, after, exp_a, exp_r, exp_c in cases:
        result = diff_snapshots(before, after)
        got_a = len(result["added"])
        got_r = len(result["removed"])
        got_c = len(result["changed"])
        ok = (got_a, got_r, got_c) == (exp_a, exp_r, exp_c)
        all_pass = all_pass and ok
        print("{:5} {:9}  expected +{} -{} ~{}  got +{} -{} ~{}".format(
            "PASS" if ok else "FAIL", label,
            exp_a, exp_r, exp_c, got_a, got_r, got_c))
    print()
    print("Self-test: {}".format("ALL PASSED" if all_pass else "FAILURES"))
    return all_pass


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

USAGE = (
    "usage: zone-diff.py BEFORE.txt AFTER.txt\n"
    "       zone-diff.py --selftest\n"
    "       zone-diff.py --help\n"
)


def read_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main(argv):
    args = argv[1:]

    if not args:
        sys.stderr.write(USAGE)
        return 2

    if args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0

    if args[0] == "--selftest":
        if len(args) != 1:
            sys.stderr.write(USAGE)
            return 2
        return 0 if run_selftest() else 1

    if len(args) != 2 or any(a.startswith("-") for a in args):
        sys.stderr.write(USAGE)
        return 2

    before_path, after_path = args
    try:
        before_text = read_file(before_path)
        after_text = read_file(after_path)
    except OSError as exc:
        sys.stderr.write("zone-diff: cannot read file: {}\n".format(exc))
        sys.stderr.write(USAGE)
        return 2

    result = diff_snapshots(before_text, after_text)
    print_report(before_path, after_path, result)

    has_diff = result["added"] or result["removed"] or result["changed"]
    return 1 if has_diff else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
