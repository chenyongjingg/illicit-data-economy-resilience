# Data: provenance by hash, not by byte

This repository deliberately does **not** redistribute the corpora it analyses.
What it publishes is the set of hashes that pin them, so a replication can prove
it holds the same inputs without the inputs travelling through git.

## `data/raw/` -- the reproducibility anchor

```
818e54e9198f0fadba82304079e2d5c33d6a99d598fd1f6d0bdf933703bd326f  agora_2014_2015.csv.xz
b074ad5d0b998c57184f4b0e9188ffbe5bc5be9990670a288b6cbf36a37f7c52  alphabay_2017-01-28.tar.xz
303a9ddf27d49add80cbaf76d4f744512efabcbd874b46434a474579a5323c9f  druglistingdataset.csv.xz
82c340231a26c1701cf30be49d74b9d670162bb94bbffc0b9e45fd2403e045c4  hansa_valhalla.zip
5659209b5a69992d5b0708a3e84a6c24e40ba04340f5e8c0b88f2442e664ca4d  kilos_6dnms_reviews.csv.xz
```

These five archives were verified, 5/5 by sha256, against the copies held on the
execution host on 2026-09-24. **That claim is dated, not standing**: it reports a
measurement made on that date, and decommissioning the host was still pending as of
it. A reader who needs it to hold now must re-run the comparison -- the sentence
cannot be true "in general", only at a time.

## Derived trees that are NOT published

| tree | files | bytes | sha256 of the sorted file list |
|---|---|---|---|
| `data/extracted` | 169541 | 21257014304 | `0e583ff41e0556539e4dc3979f475af6` |
| `data/EllipticPlusPlus-main` | 32 | 2221824034 | `93470ed6d36a5ec8aebd71fe81857ee7` |

Both are derived from `data/raw/` plus `EllipticPlusPlus.tar.gz` by the scripts in
`_server/` and `scripts/`. What is checkable without transferring them is the **file
list**: rebuild, then compare `find <tree> -type f -printf '%P\n' | LC_ALL=C sort | sha256sum`.
★ That value hashes the sorted **names only** -- two trees with the same names and
different bodies give the same number, so it cannot detect a changed byte. Content is
pinned separately and by a different instrument: the byte-identical `data/raw/`
archives above, together with the extraction the scripts perform. One step of that
extraction is worth stating because it is not in any script: the pinned
`data/extracted` member list is what `data/raw/` yields **after dropping
`alphabay_2017-01-28/20170128-alphabay/crawl-active/`** (169,541 names, list-hash
above); keeping it gives 283,772 names and a different hash. That was measured on
2026-09-24, not read off the code, and it is recorded as a measurement.

## Derived features that are NOT published

`results/elliptic_address_level.parquet` and `pipeline_reports/_ref/elliptic_address_level.parquet`
are feature tables over the Elliptic++ dataset. They are omitted rather than
redistributed; the scripts that build them are included.
