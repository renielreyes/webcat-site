# scripts/

Small, dependency-free helper scripts for this repo. Plain Python 3, standard
library only — no `pip install` needed.

## zone-diff.py — verify a DNS edit changed only what you intended

After a **human** edits DNS, take a text snapshot of the zone before the edit
and another after, then compare them. The tool reads two text files and prints
what changed. It never touches anything live.

```
python3 scripts/zone-diff.py BEFORE.txt AFTER.txt   # compare two snapshots
python3 scripts/zone-diff.py --selftest             # run built-in test cases
python3 scripts/zone-diff.py --help                 # full usage
```

**Exit codes:** `0` files match · `1` differences found · `2` usage error
(bad arguments, or a file could not be read). The non-zero "differences" code
makes it easy to use in a check: `python3 scripts/zone-diff.py a b && echo OK`.

### What counts as a record

A line is read as a DNS record when it looks like `name [ttl] [class] TYPE
value...` with a recognised type (`A`, `AAAA`, `CNAME`, `MX`, `TXT`, `NS`,
`SOA`, ...). Records are matched by **name + type**; a different value *or* TTL
is reported as a CHANGE. Parsing is tolerant: blank lines and comment lines
(starting with `#` or `;`) are ignored, repeated whitespace is collapsed, and
record names and types are compared case-insensitively. Any other line is
compared as plain text.

### Worked example

`before.txt`

```
; zone snapshot before edit
@     3600 IN NS   ns1.example.com.
www   3600 IN A    93.184.216.34
mail  3600 IN MX   10 mail1.example.com.
```

`after.txt` — the TTL on `www` was raised and an `ftp` record was added:

```
; zone snapshot after edit
@     3600 IN NS   ns1.example.com.
www   7200 IN A    93.184.216.34
mail  3600 IN MX   10 mail1.example.com.
ftp   3600 IN A    93.184.216.35
```

Running the tool:

```
$ python3 scripts/zone-diff.py before.txt after.txt
zone-diff: comparing 'before.txt' -> 'after.txt'

ADDED (1)
  + ftp A (ttl 3600) 93.184.216.35

REMOVED (0)

CHANGED (1)
  ~ www A
      before: (ttl 3600) 93.184.216.34
      after:  (ttl 7200) 93.184.216.34

Verdict: DIFFERENCES - 1 added, 0 removed, 1 changed.
$ echo $?
1
```

A human can now confirm at a glance that only the intended records changed.
