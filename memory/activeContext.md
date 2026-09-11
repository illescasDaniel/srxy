# Active Context

_Last updated: 2026-09-12_

## Branch

- `develop` — current (v1.7.0).
- `feature/1.8.0` — active 1.8.0 release train.

## Current focus

Signed + notarized macOS installers for **srxy 1.7.0 / installer 16**.

## Just changed

- Built unsigned offline + online `.app`/`.dmg` into `dist/`.
- Signed, notarized, stapled copies into `dist/signed/` (Developer ID + notary).

## Next steps

1. Distribute from `dist/signed/` (DMGs preferred for end users).
2. Commit when Daniel asks (quality-gate work may still be uncommitted on develop).
3. Continue 1.8.0 work off `feature/1.8.0`.
