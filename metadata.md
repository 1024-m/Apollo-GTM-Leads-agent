# linkedin posts

| column | search hit only | after fetching public post URL | length | fit |
| --- | --- | --- | --- | --- |
| query | set by script | set by script | 50 | truncated |
| activity_id | from post url | from post url | 150 | truncated |
| post_url | Yes | Yes | 250 | truncated |
| author_name | Usually in the title (`Name posted on the topic`) | Usually | 50 | truncated |
| author_type | `unknown` until the public post page is fetched | `person` / `company` / `unknown` (`/posts/` only; no Pulse/newsletters) | 11 | natural |
| author_vanity | from `/posts/{vanity}_…` | from `/posts/{vanity}_…` | 100 | truncated |
| linkedin_url | Built from `/posts/{vanity}_…` → `/in/{vanity}` or `/company/{vanity}`. Same key as Apollo `linkedin_url`. | Same | 150 | truncated |
| headline | Sometimes in richer search results | Job line from the public post page. Full value on HF shards | 50 | local truncated; HF full |
| post_snippet | DDG snippet | unused after page fetch | 50 | local truncated; HF full |
| post_text | no | Public post body. Stored on HF for later classifier training | — | HF full |
| date_raw | Sometimes a SERP date | Relative only (`3w`, `5mo`). No ISO timestamp | 10 | truncated |
| fetched_at | set by script | set by script | 20 | natural |
| apollo_list | `--list` on this run | same | 80 | truncated |
| vote | Space Keep/Ignore/Later | `keep` / `ignore` / `later` | 10 | natural |
| voted_at | Space vote time | ISO | 20 | natural |
| in_apollo | `n` until that person is in `{list}/apollo-state.csv` | `y` after sync or push for that LinkedIn URL | 10 | natural |

# DDG-script-regions

| region | place |
| --- | --- |
| xa-ar | Arabia |
| xa-en | Arabia (en) |
| ar-es | Argentina |
| au-en | Australia |
| at-de | Austria |
| be-fr | Belgium (fr) |
| be-nl | Belgium (nl) |
| br-pt | Brazil |
| bg-bg | Bulgaria |
| ca-en | Canada |
| ca-fr | Canada (fr) |
| ct-ca | Catalan |
| cl-es | Chile |
| cn-zh | China |
| co-es | Colombia |
| hr-hr | Croatia |
| cz-cs | Czech Republic |
| dk-da | Denmark |
| ee-et | Estonia |
| fi-fi | Finland |
| fr-fr | France |
| de-de | Germany |
| gr-el | Greece |
| hk-tzh | Hong Kong |
| hu-hu | Hungary |
| in-en | India |
| id-id | Indonesia |
| id-en | Indonesia (en) |
| ie-en | Ireland |
| il-he | Israel |
| it-it | Italy |
| jp-jp | Japan |
| kr-kr | Korea |
| lv-lv | Latvia |
| lt-lt | Lithuania |
| xl-es | Latin America |
| my-ms | Malaysia |
| my-en | Malaysia (en) |
| mx-es | Mexico |
| nl-nl | Netherlands |
| nz-en | New Zealand |
| no-no | Norway |
| pe-es | Peru |
| ph-en | Philippines |
| ph-tl | Philippines (tl) |
| pl-pl | Poland |
| pt-pt | Portugal |
| ro-ro | Romania |
| ru-ru | Russia |
| sg-en | Singapore |
| sk-sk | Slovak Republic |
| sl-sl | Slovenia |
| za-en | South Africa |
| es-es | Spain |
| se-sv | Sweden |
| ch-de | Switzerland (de) |
| ch-fr | Switzerland (fr) |
| ch-it | Switzerland (it) |
| tw-tzh | Taiwan |
| th-th | Thailand |
| tr-tr | Turkey |
| ua-uk | Ukraine |
| uk-en | United Kingdom |
| us-en | United States |
| ue-es | United States (es) |
| ve-es | Venezuela |
| vn-vi | Vietnam |
| wt-wt | No region |
