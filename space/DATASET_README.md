---
pretty_name: Apollo-Leads-Lists
---

# Apollo-Leads-Lists

Private store for Apollo GTM votes. One directory per Apollo contacts list. Skip logic only reads files in that list's directory.

Hourly vote shards: `{list}/{DDMMYYYY-HH}.csv` (includes post text and title for a later classifier). Current Apollo members: `{list}/apollo-state.csv`.

Primary key for a person on a list: LinkedIn URL (`linkedin_url`). `apollo_contact_id` is secondary.

`in_apollo` on a vote row: `y` if that person is in `apollo-state.csv` or was just pushed. `n` otherwise.
