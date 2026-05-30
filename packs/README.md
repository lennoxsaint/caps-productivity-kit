# CAPS Packs

Packs are optional installable operating-system modules for a specific cohort,
product, launch, or team.

Use packs when the same CAPS lane structure should be reused across multiple
projects without hardcoding that structure into the core kit.

Install a pack:

```bash
./install.sh /path/to/project --pack full-circle-5
```

Packs are public-safe by default. Do not add secrets, private thread IDs,
member/customer data, paid course material, or local launch proof unless it has
been explicitly approved for public release.
