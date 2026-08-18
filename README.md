# venv setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

# linkedin posts
The number specifies number of posts to fetch.
```
python src/linkedin_posts.py "unsloth local finetune" 50 --list "unsloth-local"
```

# excluding search radius
Can be used to exclude commerical competitor mentions or team members' posts
```
python src/linkedin_posts.py "unsloth local finetune" 50 --list "unsloth-local" --exclude "['xxx xx xxx', 'yyyyyyyy yy']"
```

# limitting search to region
For targetting specific regions
```
python src/linkedin_posts.py "unsloth local finetune" 50 --list "unsloth-local" --region us-en
```

[DDG-script-regions](metadata.md#ddg-script-regions)

# limitting search to timespan

```
python src/linkedin_posts.py "unsloth local finetune" 50 --list "unsloth-local" --timeline d
```

| code | window |
| --- | --- |
| d | last day |
| w | last week |
| m | last month |
| y | last year |

# apollo list

```
python src/linkedin_posts.py "unsloth local finetune" 50 --list "unsloth-local"
```

# create apollo list

```
python src/create_apollo_list.py --list "unsloth-local"
```

# sync apollo list members to dataset
Writes `{list}/apollo-state.csv` from the live Apollo contacts list.
```
python src/sync_apollo_state.py --list "unsloth-local"
```

# push keeps to apollo list
Adds `vote=keep` people who are not already in `apollo-state.csv`.
```
python src/push_apollo_keeps.py --list "unsloth-local"
```

# merge dataset list

```
python src/merge_dataset.py --list "unsloth-local"
```

# codebase structure

```
Apollo-GTM-Agent/                 # repo root
├── data/                         # local CLI fetch output
│   ├── exports/                  # merged vote CSV dumps
│   └── linkedin_posts.csv        # CLI fetch table
├── src/                          # local CLI scripts
│   ├── env.py                    # load .env keys
│   ├── hf.py                     # HF token + dataset id
│   ├── apollo.py                 # Apollo API calls
│   ├── dataset_io.py             # HF shards, skip, apollo-state
│   ├── linkedin_posts.py         # DDG fetch LinkedIn posts
│   ├── sync_apollo_state.py      # Apollo members → apollo-state.csv
│   ├── push_apollo_keeps.py      # Keep votes → Apollo list
│   ├── merge_dataset.py          # concat list shards to one CSV
│   ├── create_apollo_list.py     # create empty Apollo list
│   └── store.py                  # CSV widths, local row writes
├── space/                        # HF Space dashboard
│   ├── app.py                    # FastAPI Keep/Ignore/Later UI
│   ├── apollo.py                 # Space copy of Apollo API
│   ├── dataset_io.py             # Space copy of dataset I/O
│   ├── env.py                    # Space copy of .env loader
│   ├── hf.py                     # Space copy of HF helpers
│   ├── linkedin_posts.py         # Space copy of post fetch
│   ├── store.py                  # Space copy of CSV helpers
│   ├── Dockerfile                # Space container
│   ├── README.md                 # Space card / app blurb
│   ├── DATASET_README.md         # HF dataset repo README
│   └── requirements.txt          # Space Python deps
├── flowchart.md                  # full pipeline diagram
├── flowchart_limited.md          # Space + list skip flow
├── metadata.md                   # column + region tables
├── requirements.txt              # CLI Python deps
├── README.md                     # this file
├── .env                          # local secrets
├── .env.example                  # key names, no secrets
├── .gitignore                    # ignored paths
└── LICENSE                       # license
```
