# linkedin posts

| column | search hit only | after fetching public post URL | length | fit |
| --- | --- | --- | --- | --- |
| query | set by script | set by script | 50 | padded/truncated |
| activity_id | from post url | from post url | 150 | padded/truncated |
| post_url | Yes | Yes | 250 | padded/truncated |
| author_name | Usually in the title (`Name posted on the topic`) | Usually | 50 | padded/truncated |
| author_type | `article` if `/pulse/`, `newsletter` if `/newsletters/`, else `unknown` | `person` / `company` / `article` / `newsletter` / `unknown` | 11 | natural |
| author_vanity | from post url slug | from post url slug | 100 | padded/truncated |
| profile_url_guess | Infer from slug: `/posts/mandeepshishodia_…` → `/in/mandeepshishodia` | Same inference | 120 | padded/truncated |
| headline | Sometimes in richer Google results | Often on public posts (`Software Engineer @Datopic \| …`) | 50 | padded/truncated |
| post_snippet | ~150–300 chars | unused | 50 | padded/truncated |
| post_text | no | flattened 200-char preview in csv; full text in `data/bodies/linkedin_posts/` | 200 | padded/truncated |
| date_raw | Sometimes a SERP date | Relative only (`3w`, `5mo`). No ISO timestamp | 10 | padded/truncated |
| fetched_at | set by script | set by script | 20 | natural |

# redit posts

| column | RSS / public search | length | fit |
| --- | --- | --- | --- |
| query | set by script | 50 | padded/truncated |
| post_id | In the URL | 20 | padded/truncated |
| post_url | Yes (`/r/sub/comments/id/slug/`) | 250 | padded/truncated |
| title | Yes | 80 | padded/truncated |
| post_text | flattened 200-char preview in csv; full text in `data/bodies/reddit_posts/` | 200 | padded/truncated |
| author | Yes | 50 | padded/truncated |
| author_url | `https://www.reddit.com/user/{name}` | 120 | padded/truncated |
| subreddit | Yes, from the URL | 50 | padded/truncated |
| subreddit_url | `https://www.reddit.com/r/{sub}` | 80 | padded/truncated |
| created_at | Yes, real published timestamp in RSS | 40 | padded/truncated |
| outbound_url | Yes if it is a link post | 250 | padded/truncated |
| fetched_at | set by script | 20 | natural |
