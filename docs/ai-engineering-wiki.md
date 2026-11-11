# AI Engineering Wiki

General notes on building with LLMs, written as I work through the
[checklist](ai-learning-checklist.md). Each section ends with what was actually tried in this
repo, so the claims can be traced back to something that ran.

Last updated: 2026-11-10.

## Contents

- [Tool calling](#tool-calling)
- [Embeddings and vector search](#embeddings-and-vector-search)
- [Embedding models](#embedding-models)
- [Chunking](#chunking)
- [RAG](#rag)
- [Two-step against agentic RAG](#two-step-against-agentic-rag)
- [Vector databases](#vector-databases)
- [Hybrid search and reranking](#hybrid-search-and-reranking)
- [Knowledge graphs](#knowledge-graphs)
- [RAG vs fine-tuning](#rag-vs-fine-tuning)
- [Choosing a model: speed against quality](#choosing-a-model-speed-against-quality)
- [Testing and shipping habits](#testing-and-shipping-habits)
- [Glossary](#glossary)
- [Next experiments](#next-experiments)

---

## Tool calling

A tool is a normal function that the model is allowed to ask for. The model never runs
anything itself. The loop is:

1. The app sends the question plus a description of each tool (name, parameters, docstring).
2. The model replies either with an answer or with "call `search_campaign('Kallista')`".
3. The app runs the function and sends the result back.
4. Repeat until the model answers.

An **agent** is this loop: a model that decides which tools to call and when to stop.

Things worth remembering:

- **The docstring is the prompt.** It is the only thing the model sees when deciding whether
  to call a tool, so write it for the model: when to use it, what to pass, what comes back.
- **Not every model can do it.** Check for tool support (`ollama show <model>` lists
  "tools" under capabilities). Small models call tools less reliably.
- **Tools make runs slower and less predictable.** Each call is an extra model round trip.

*In this repo:* `ai_playground.Agent` takes `extra_tools`; `rag_playground/rag.py` passes it
a `search_campaign` function. Printing each tool call with its arguments turned out to be the
most useful debugging aid.

## Embeddings and vector search

An **embedding model** turns a piece of text into a list of numbers (a vector) so that texts
with similar meaning end up close together. It is a different model from the chat model and
is much smaller and faster.

- **Search** means: embed the question, then find the stored vectors closest to it.
  Closeness is usually **cosine similarity** (the angle between two vectors). If all vectors
  are scaled to length 1 first, that is a single matrix multiplication.
- **Use the same embedding model for documents and questions.** Vectors from different
  models are not comparable. Changing the model means re-embedding everything.
- **Some models need prefixes.** `nomic-embed-text` expects `search_query:` or
  `search_document:` in front of each text. `bge-m3` does not.
- **Embeddings match meaning, not spelling.** They are good at "what destroyed the
  continent?" finding a passage about an explosion. They are weak on rare or invented names,
  which is what keyword search is for (see hybrid search).

*In this repo:* `bge-m3` through Ollama, 1,024 numbers per chunk, called with pydantic-ai's
`Embedder`. Embedding 657 chunks took about a minute, once. See `rag_playground/index.py`.

## Embedding models

Embedding models differ on a handful of practical properties. The first two are explained in
detail below because they shape the whole index.

| Property | What it means | Why it matters |
|---|---|---|
| Dimensions | How many numbers per vector (384 to 3,072) | More can capture finer meaning, but takes more storage and slower search |
| Max input length | How much text fits in one call (256 to 32,000 tokens) | Anything longer is silently cut off, so it caps your chunk size |
| Languages | English-only or multilingual | An English-only model does poorly on Dutch |
| Model size | About 50 MB to several GB | Indexing speed, and whether it fits next to the chat model |
| Prefixes / instructions | Some need `search_query:` or a task instruction before the text | Forgetting them quietly hurts quality |
| Shortenable vectors ("Matryoshka") | You may keep only the first 256 or 512 numbers | A smaller index for little quality loss |
| Output type | Dense (one vector), sparse (keyword-like weights), multi-vector (one per token) | Sparse and multi-vector do better on exact names |
| Modality | Text only, or text plus images | Needed to search figures, screenshots, maps |

### Dimensions

The model turns every text into a list of numbers of a **fixed length**, and that length is
the dimension count. `bge-m3` always returns 1,024 numbers, whether the input is one word or
a full page.

Each number is a position along one direction the model learned during training. No single
direction has a readable meaning like "is about dragons"; the meaning is in the combination.
Think of describing a person: with 3 numbers (height, weight, age) many different people
look identical, with 100 numbers far fewer do. More dimensions give the model more room to
keep two different meanings apart.

What it costs is plain arithmetic, at 4 bytes per number:

| Chunks | 384 dims | 1,024 dims | 3,072 dims |
|---|---|---|---|
| 657 (the campaign) | 1.0 MB | 2.7 MB | 8.1 MB |
| 1 million | 1.5 GB | 4.1 GB | 12.3 GB |

Search time grows the same way, because comparing two vectors means multiplying every pair
of numbers.

- **At small scale it does not matter.** The campaign index is 2.7 MB at 1,024 dimensions.
  Dimensions become a real decision at hundreds of thousands of chunks.
- **More is not automatically better.** Dimensions are room, not quality. A well-trained
  768-dimension model can beat a weaker 3,072-dimension one. Compare models on a benchmark
  or your own questions, never on dimension count.
- **The count is fixed per model**, so every vector in an index has the same length, and
  vectors from two different models can never be mixed.
- **Shortenable models** are trained so the first numbers carry the most meaning. You can
  keep the first 256 of 1,024 and lose only a little quality. Cutting an ordinary model's
  vectors that way ruins them.

### Max input length

An embedding model reads its input in tokens and has a hard limit on how many it can take.
Text past the limit is **dropped without an error**: Ollama truncates by default. The
vector then describes only the start of the chunk.

Why that is a nasty failure: the full chunk text is still stored and still shown to the chat
model when it is retrieved. Nothing looks wrong. The chunk simply can no longer be *found*
by anything in its cut-off tail.

Measured on the campaign chunks with `bge-m3`:

| Chunk | Words | Tokens |
|---|---|---|
| Typical (median) | 249 | 397 |
| Large (90th percentile) | 358 | 513 |
| Longest | 700 | 995 |

That is about 1.4 to 1.6 tokens per word, more than the usual estimate of 1.3. Invented
names split into several tokens each.

What each limit would do to these 657 chunks:

| Model limit | Chunks cut off |
|---|---|
| 256 tokens (`all-minilm`) | about 564 (86%) |
| 512 tokens (`mxbai-embed-large`) | about 100 (15%) |
| 2,048 or 8,192 tokens | none |

- **Check the limit against your real chunks**, in tokens, not words, before picking a model.
- **Changing to a model with a shorter limit means re-chunking**, not only re-embedding.
- **The limit is a ceiling, not a target.** `bge-m3` accepts 8,192 tokens, but a whole
  chapter squeezed into 1,024 numbers gives a blurry vector that matches everything a
  little and nothing well. This is the link between the two properties: the vector is the
  same size however much text goes in, so small focused chunks get sharper vectors.

### Models to know

Figures are from memory and the field moves fast; check the model page before relying on
one.

Local, through Ollama:

| Model | Dimensions | Max input | Notes |
|---|---|---|---|
| `all-minilm` | 384 | 256 | Tiny and very fast. Fine for demos. |
| `nomic-embed-text` | 768 | 8,192 | Small, good for English. Needs the prefixes. |
| `mxbai-embed-large` | 1,024 | 512 | Strong on English, short input limit. |
| `bge-m3` | 1,024 | 8,192 | Multilingual, no prefixes. Used in this repo. |
| `embeddinggemma` | 768 | 2,048 | Google's small model for laptops and phones. Shortenable. |
| `qwen3-embedding` | 1,024 to 4,096 | 32,000 | Three sizes. Among the strongest open models. |

Hosted, through an API: OpenAI `text-embedding-3-small` / `-large`, Google
`gemini-embedding-001`, Voyage AI (also specialised models for code, law, finance; Anthropic
has no embedding model and points to Voyage), Cohere `embed-v4` (text and images), Jina,
Mistral. Often a little better and nothing to run locally, but the text leaves your machine
and you pay per token.

### Choosing one

1. Check the hard limits: your languages, and a max input above your largest chunk.
2. Use the MTEB leaderboard on Hugging Face for a shortlist. The top changes every few
   months.
3. Test the shortlist on your own questions. Benchmark rank often does not carry over to a
   specific corpus, especially one full of invented names.

*In this repo:* changing model is one setting, `RAG_EMBED_MODEL`, plus a one-minute re-index.

## Chunking

Documents are split into chunks because an embedding of a whole chapter is too vague to
match a specific question, and because only a few passages fit usefully in a prompt.

- **Size:** a few hundred words is the usual starting point. Smaller chunks match more
  precisely but lose context; larger ones do the opposite.
- **Split on structure first** (headings, sessions, paragraphs), not on a fixed character
  count, so a chunk is a coherent piece of text.
- **Overlap** repeats the end of one chunk at the start of the next, so a scene cut in half
  is still findable from both sides.
- **Carry metadata.** Put the section title on each chunk, so both the search and the model
  know where and when the passage belongs.

*In this repo:* the campaign .docx is split on its Word heading styles, then packed into
chunks of about 300 words that never cross a chapter. Each chunk starts with its chapter
title. 161k words became 657 chunks. There is no overlap yet, and one answer did complain
that an excerpt "ends mid-scene". See `rag_playground/loader.py`.

## RAG

**Retrieval-Augmented Generation** gives the model relevant passages from your own text at
question time, so it answers from your data and can say where the answer came from.

**Indexing (once):** load → chunk → embed → store.

**Answering (every question):** embed the question → retrieve the closest chunks → put them
in the prompt → the model answers.

| Type | Idea | Trade-off |
|---|---|---|
| Two-step (classic) | Always retrieve once, then answer. | Simple, cheap, predictable. Fails on vague questions and ones needing several lookups. |
| Advanced two-step | The same pipeline plus query rewriting, hybrid search, reranking. | Usually the best gain for the effort. |
| Agentic | Retrieval is a tool the model chooses to call, as often as it wants. | Handles multi-step questions. Slower and less predictable. |
| Corrective / self-RAG | The model grades what it retrieved and searches again if it is weak. | Between two-step and agentic. |
| GraphRAG (knowledge graph) | Extract entities and relations into a graph, retrieve through it. | Good for "how does X relate to Y across everything". Heavy to index. |

RAG is needed when the text does not fit in the context window, or when sending all of it
with every question is too slow or expensive. The campaign is about 210k tokens, more than
most local models can read at once.

## Two-step against agentic RAG

The whole difference is **who decides to retrieve**: the code (two-step) or the model
(agentic).

What running both on the campaign showed:

- On simple lookups ("Who is X?") both give the same result with one search. Agentic was
  not slower, because the answers were shorter.
- On a question spanning three chapters, two-step can only use its one batch of 5 chunks.
  Agentic with a strong model searched 4 to 8 times with different wording and pieced the
  answer together.
- Agentic quality depends on the model. A small model searched once and stopped, and
  described only the chapter it happened to land on.
- Agentic with a large model can run away: one question took 176 seconds and 8 searches.

Rule of thumb: start with two-step. Move to agentic when questions need more than one
lookup, and only with a model that handles tools well.

## Vector databases

A vector database stores vectors and finds the nearest ones. For small collections it is not
needed: a numpy array in memory does the same job in well under a millisecond for a few
thousand vectors.

Reach for one when you need:

- **Scale:** hundreds of thousands of vectors or more, where comparing against all of them
  gets slow. Databases use approximate indexes (HNSW) to avoid that.
- **Incremental updates:** adding or deleting single documents without re-embedding all.
- **Metadata filters:** "only chapters 10 to 20".
- **Built-in hybrid search**, or serving several apps at once.

Light options that run without a server: Chroma, LanceDB. If you already run Postgres:
pgvector.

**A model is not a database.** The embedding model and the chat model *compute*: text in,
vector or answer out, and they hold none of your data. The vector database *stores* your
vectors and looks them up, with no intelligence of its own. Swapping the database changes
speed and features, never the answers.

*In this repo:* the vectors are cached in one `.npz` file and loaded into a LanceDB table
(a folder on disk, no server) at startup. `RAG_STORE=numpy` skips the database and searches
the same vectors in numpy. Measured on the 657 campaign chunks: both return identical
results, the table builds in 15 ms and a search takes 8 ms. So at this size the database
adds no speed or quality; what it adds is a `section` column to filter on and built-in
keyword search for the hybrid experiment.

## Hybrid search and reranking

These are the standard fixes for weak retrieval. Hybrid search is built here; the other two
are not.

- **Hybrid search** runs a keyword search (BM25) next to the vector search and merges the
  two result lists. Keywords catch exact names and codes that embeddings blur. Expect this
  to matter for invented names. The usual merge is **reciprocal rank fusion**: each chunk
  scores `1 / (60 + rank)` in each list and the sums are sorted, so only positions count,
  not the two kinds of score.
- **Reranking** retrieves generously (say 50 chunks) and then has a second, slower model
  (a cross-encoder) score each chunk against the question, keeping the best 5. It reads the
  question and chunk together, so it judges relevance better than vector distance alone.
- **Query rewriting** has the model rephrase the question before searching. One variant,
  HyDE, writes a made-up answer and searches with that, because an answer looks more like
  the stored passages than a question does.

They sit at different stages of one pipeline, so they combine:

```
question → (rewrite) → vector + keyword search → merge → ~50 chunks → (rerank) → best 5 → model
```

### How hybrid search works

**Why vector search is not enough.** The embedding model has never seen an invented name,
so it turns it into a vague vector. A chunk that contains the name can rank below chunks
that are only about a similar topic.

**Keyword search (BM25)** scores a chunk by the question's exact words. Three things set the
score:

- **Rare words count most.** A word found in 2 chunks out of 657 says far more than "the" or
  "who", which are in almost all of them. This is why it is strong on invented names.
- **More mentions help, but less each time.** Ten mentions do not score ten times one.
- **Long chunks are scaled down**, so a chunk does not win only by containing more words.

It needs no model: it is an index from each word to the chunks containing it, so it is fast
to build and to search.

**Merging.** The two scores cannot be added: cosine similarity is between -1 and 1, a BM25
score has no upper limit. Reciprocal rank fusion ignores the scores and uses positions:

| Chunk | Vector rank | Keyword rank | Score |
|---|---|---|---|
| A | 1 | not found | 1/61 = 0.0164 |
| B | 2 | 3 | 1/62 + 1/63 = 0.0320 |
| C | not found | 1 | 1/61 = 0.0164 |

B wins because both searches agree on it. A and C still get through, each on the strength
of one search. The 60 is a convention; it keeps the top position from dominating.

**What each side is good at:**

| | Vector search | Keyword search |
|---|---|---|
| Finds | The same meaning in different words | The exact word |
| Good for | "What destroyed the continent?" | Names, codes, numbers, rare terms |
| Misses | Rare and invented names | Synonyms, paraphrases, other spellings |

**Limits.** Keyword search matches spelling, so a typo or a second spelling of a name
("Rhosghonel" and "Rhosgonel" both occur in the campaign) is a miss for it. Hybrid search
also cannot fix a question that has no useful words in it; that is what query rewriting is
for. And the merge can push out a good vector result in favour of a chunk that only repeats
a word from the question, so measure it on your own questions before making it the default.

*In this repo:* `uv run rag-playground --hybrid`. LanceDB builds the keyword index on the
`text` column and does the merge (`rag_playground/index.py`). Measured on 14 names that occur
in only one or two of the 657 chunks ("Who or what is Vaxumbria?"): vector search had the
name somewhere in its top 5 for 11 of 14 questions, hybrid for 14 of 14, at the same speed.
Names that occur often ("Ksenrae", in 44 chunks) were already found by vector search alone,
so the gain is on the rare ones.

### How reranking works

**The problem.** The first search is fast but rough. The right chunk is often somewhere in
the top 50, just not in the top 5 that the model gets to read.

**The fix.** Retrieve about 50 chunks, have a second model (a **cross-encoder**) score each
one against the question, and keep the best 5.

**Why the second model judges better.** The embedding model is a **bi-encoder**: it reads
the question and the chunk separately. The cross-encoder reads them together.

| | Bi-encoder (embedding model) | Cross-encoder (reranker) |
|---|---|---|
| Reads | Question and chunk separately | Question and chunk together |
| Output | One vector per text | One relevance score per pair |
| When the work is done | Chunks once, in advance | Every pair, at question time |
| Speed | Fast: compare vectors | Slow: one model run per chunk |
| Judgement | Rough: the chunk was summed up before any question existed | Sharper: can tell a chunk names the right person but answers another question |

**Limits.**

- It improves the order, not the reach: a chunk that is not in the 50 cannot be brought back.
- It runs once per chunk for every question and nothing can be prepared in advance, so it
  is only affordable on a shortlist, never on the whole collection.

**How to tell if you need it.** With an eval set, check where the right chunk lands. If it
is often in the top 50 but not in the top 5, rerank. If it is already in the top 5, skip it.

*In this repo:* not built. The reasons:

- **No evidence of a ranking problem yet.** Simple lookups already retrieve the right
  chapter, and hybrid search fixed the one failure that was measured. The eval set comes
  first.
- **It would not help the multi-chapter questions.** Those need several searches, which is
  what agentic mode does.
- **Ollama cannot serve a reranker.** Version 0.40.16 answers 404 on `/api/rerank` and
  `/v1/rerank` (checked 2026-11-11), and the upstream feature request has been open since
  March 2024.

The ways to run one locally anyway:

| Option | Needs | Trade-off |
|---|---|---|
| LanceDB's built-in `CrossEncoderReranker` | `sentence-transformers` and `torch` | Fewest lines: it plugs into the hybrid query in `rag_playground/index.py`. A large dependency. |
| A chat model as the judge | Nothing new | One model call per chunk, so 50 calls per question. Slow. |
| A separate rerank server | llama.cpp's `llama-server`, which has `/v1/rerank` | A real reranker model, but a second service to run. |

If it is built later, start with the LanceDB option. None of the three has been run here.

## Knowledge graphs

A knowledge graph stores **entities** (people, places, factions, events) and the
**relations** between them, as triples: `Kallista | is the capital of | Carverun`. Using one
for retrieval is called **GraphRAG**.

**Why chunks are not enough.** A search returns the 5 passages closest to the question. That
works when one passage holds the answer. It fails when the answer is spread thinly over the
whole text ("who is connected to Kallista?") or needs several steps ("who leads the faction
that the narrator's friend belongs to?").

**How it is built.** A chat model reads every chunk once and writes down the relations it
states. This happens at indexing time, so it is slow to build and needs no model to look up.

| | Vector or keyword search | Knowledge graph |
|---|---|---|
| Stores | Passages of text | Facts pulled out of the text |
| Built by | An embedding model, in about a minute here | A chat model, one call per chunk |
| Answers well | "What happened at X?" | "How are X and Y related?", "what is connected to X?" |
| Keeps | The author's exact words | Only what the model wrote down |
| Fails when | The answer is spread over many passages | The model missed or misread a relation |

**What makes it hard.**

- **Extraction is noisy.** The model decides what counts as a relation. Without firm rules
  it records every sword blow as one. A weak model produces nothing usable.
- **Names must be matched.** "Rhosghonel" and "Rhosgonel" become two entities unless
  someone merges them. So do "Nerwen" and "the goddess of love".
- **Stories change.** An ally in chapter 6 is an enemy in chapter 30. A triple has no time
  in it unless you store where it came from.
- **The narrator.** In a first-person text most relations start at "I", which has to be
  given a name.

**Full GraphRAG goes further:** it groups related entities into clusters and writes a
summary of each one, to answer questions about the whole text ("what are the main themes?").
That is much more model work at indexing time.

**Rule of thumb:** add a graph when you have questions about connections that the search
demonstrably fails on. Keep the search: the graph says *that* two things are related and
where, the passages say *what happened*.

## RAG vs fine-tuning

**RAG gives the model facts to read at question time. Fine-tuning changes how the model
behaves.**

| | RAG | Fine-tuning |
|---|---|---|
| What it does | Looks up text and puts it in the prompt | Retrains the model's weights on examples |
| Good at | Facts, details, anything you want cited | Style, tone, output format, one narrow task |
| Updating knowledge | Re-index (about a minute here) | Retrain |
| Can show its source | Yes | No |
| Made-up answers | Fewer, the text is in front of it | Still common: facts are recalled loosely |
| Effort | A loader, an index, a prompt | Hundreds to thousands of examples, GPU time, evaluation |
| Cost per answer | Longer prompts, slower | Short prompts, faster once trained |

- **Fine-tuning is poor at memorising facts.** A model trained on a 161k-word story learns
  to sound like it and will confidently invent plausible details. And every new chapter
  would mean retraining.
- **Fine-tune for behaviour:** a specific voice, a strict output format, or making a small
  fast model do one narrow task as well as a big one.
- **They combine.** RAG for the facts, a fine-tuned model for the style or for using the
  search tool well.
- **Order to try things:** better prompting, then RAG when knowledge is missing, then
  fine-tuning only if the behaviour is still wrong.

## Choosing a model: speed against quality

Measured on this laptop, three campaign questions, both RAG modes, model loading time
excluded. One or two runs per question, so treat single numbers as rough.

| Model | Average seconds per answer |
|---|---|
| gemma4:e2b | 6.3 |
| gemma4:e4b | 8.4 |
| qwen3.6:35b-a3b | 30.2 |
| qwen3.8:27b | 64.8 (42.5 without one 176-second run) |

What the timings do not show:

- **The fast models gave thinner answers.** Asked who "Salazar the Lavender" is, only 1 of 8
  gemma answers mentioned that it is an alias, which the source chapter states. The qwen
  answers did.
- **Speed partly came from doing less.** On the multi-chapter question the gemmas searched
  once; qwen3.6 searched 4 times, qwen3.8 searched 8 times.
- **Retrieval is not the bottleneck.** Search takes milliseconds. Almost all the waiting is
  the chat model writing, so longer answers cost more time.

Lessons: measure on your own questions, look at the answers and not only the clock, warm the
model up before timing, and run each question more than once.

Useful commands: `ollama list` (installed), `ollama ps` (loaded right now),
`ollama show <model>` (size, context length, tool support).

## Testing and shipping habits

- **Test without a model.** pydantic-ai's `TestModel` and `TestEmbeddingModel` stand in for
  the real ones, so tests need no network, no API key and no GPU, and run in seconds.
- **Test the plain code hardest.** The loader, chunker and ranking are ordinary functions
  with exact expected output. The model's wording cannot be asserted on; that is what evals
  are for.
- **One script for local and CI.** `./init.sh` runs lint, type check and tests; the GitHub
  Actions workflow runs the same script, so they cannot disagree.
- **Protect `main`.** A GitHub ruleset requires a pull request and a passing CI check. Solo,
  set required approvals to 0, since you cannot approve your own PR.
- **Pre-commit hooks** format and lint on every commit, but only after
  `uv run pre-commit install` in each clone.
- **Keep private data out of git.** The source document and its index sit in a git-ignored
  folder.

## Glossary

| Term | Meaning |
|---|---|
| Token | The unit a model reads and writes; roughly three quarters of an English word. |
| Context window | How many tokens a model can take in at once. |
| Embedding | A vector of numbers representing the meaning of a text. |
| Cosine similarity | How closely two vectors point the same way; the usual measure of "similar". |
| Chunk | A passage of a document, small enough to embed and retrieve on its own. |
| Top-k | The k closest chunks returned by a search. |
| BM25 | The standard keyword-search scoring method. |
| Reranker | A second model that re-scores retrieved chunks against the question. |
| Knowledge graph | Entities and the relations between them, stored as triples. |
| Indexing time | The preparation done once per document, before any question. |
| Agent | A model in a loop that decides which tools to call and when to stop. |
| Hallucination | A confident answer that is not supported by the source or by fact. |
| Eval | A fixed set of questions with expected answers, used to measure quality. |
| Fine-tuning | Further training of a model on your own examples. |
| Quantization | Storing model weights at lower precision to shrink it and speed it up. |

## Next experiments

1. Write about 10 campaign questions with known answers, as an eval set. Without it,
   "better" is a guess.
2. Add hybrid (keyword + vector) search with LanceDB's keyword index and check it on
   invented names.
3. Add chunk overlap and see whether "ends mid-scene" answers go away.
4. Try a reranker.
5. Prompt the small model to search more than once on multi-part questions.
6. Filter searches by chapter using the `section` column in the LanceDB table.
