# venv setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

# linkedin posts

```
python src/linkedin_posts.py "unsloth local finetune" 50
```

# reddit posts

```
python src/reddit_posts.py "unsloth local finetune" 50
```

# codebase structure

```
Apollo-GTM-Agent/
├── data/
│   ├── bodies/
│   ├── linkedin_posts.csv
│   └── reddit_posts.csv
├── src/
│   ├── linkedin_posts.py
│   ├── reddit_posts.py
│   └── store.py
├── metadata.md
├── requirements.txt
├── README.md
└── LICENSE
```
