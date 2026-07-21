# Slice 3 engine fixture

`slice3_episode.json` is a deterministic, wholly synthetic configuration used
to generate the April 2020 sign and byte-golden inputs. Its values are invented;
it contains no licensed UMich observations or other provider data.

Regenerate deliberately with:

```bash
.venv/bin/python tests/fixtures/engine/gen_slice3_fixture.py
```

The fixture-matches-generator test and the assembly SHA must both be reviewed
and re-pinned after an intentional engine-output change.
