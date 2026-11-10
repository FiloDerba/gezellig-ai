# AI Engineer Learning Checklist (2026)

Source: "AI Engineer in 2026" post by Nazih Khelifa (Oct 14).

**Core message:** Stop building another generic chatbot. Build something someone would use
even if it doesn't have AI in the name.

Notes on each topic live in the [wiki](ai-engineering-wiki.md). Points marked *(added)* were
not in the original list. A ticked box means it was covered hands-on in this repo; untick
anything you want to revisit.

---

## Stage 1: Foundations

- [ ] Learn Python for real
- [ ] Understand an API before an agent
- [ ] Learn how an LLM works, not just the chat
- [ ] Tokens, context windows and sampling (temperature) *(added)*
- [ ] Prompting basics: system prompts, few-shot examples *(added)*
- [x] Run a model locally and compare models on speed against quality *(added)*
      → [wiki](ai-engineering-wiki.md#choosing-a-model-speed-against-quality)

## Stage 2: Core building blocks

- [x] Build with tool calling → [wiki](ai-engineering-wiki.md#tool-calling)
- [ ] Learn RAG → [wiki](ai-engineering-wiki.md#rag)
  - [x] Standard RAG: retrieve relevant info and pass it to the prompt
  - [x] Agentic RAG: retrieve through a tool
  - [ ] Knowledge graph
- [x] Learn embeddings and vector search
      → [wiki](ai-engineering-wiki.md#embeddings-and-vector-search)
- [x] Compare embedding models: dimensions, max input length, languages *(added)*
      → [wiki](ai-engineering-wiki.md#embedding-models)
- [x] Put the vectors in a vector database (LanceDB) *(added)*
      → [wiki](ai-engineering-wiki.md#vector-databases)
- [x] Chunking: size, overlap, splitting on document structure *(added)*
      → [wiki](ai-engineering-wiki.md#chunking)
- [x] RAG vs fine-tuning → [wiki](ai-engineering-wiki.md#rag-vs-fine-tuning)
- [ ] Hybrid search and reranking
      → [wiki](ai-engineering-wiki.md#hybrid-search-and-reranking)
- [ ] Context engineering: deciding what goes into the prompt and what stays out *(added)*
- [ ] MCP (Model Context Protocol): the standard way to expose tools to agents *(added)*

## Stage 3: Build one real agent

- [ ] Build a real agent, just one
- [ ] Give it memory
- [ ] Give it real tools, not a mock
- [ ] Know when not to use an agent: a fixed pipeline is cheaper and more predictable *(added)*
- [ ] Human approval before risky or irreversible actions *(added)*

## Stage 4: Make it reliable

- [ ] Add retries and fallbacks
- [ ] What if the retrieval pipeline fails
- [ ] Force structured output
- [ ] Handle hallucination
- [ ] Add auth
- [ ] Add observability
- [ ] Add evals
- [ ] Break it with real failures
- [ ] Defend against prompt injection (text the agent reads is not instructions) *(added)*
- [x] Test without the network (fake models) and run the tests in CI *(added)*
      → [wiki](ai-engineering-wiki.md#testing-and-shipping-habits)

## Stage 5: Ship it

- [ ] Deploy it publicly
- [ ] See what it costs in prod
- [ ] Lower the latency
- [ ] Read the logs
- [ ] Fix what the user actually breaks
- [ ] Cut cost with prompt caching and by routing easy questions to a small model *(added)*
- [ ] Pin and version models and prompts, so a silent upgrade can't change behaviour *(added)*
- [ ] Know what data leaves your machine (privacy, API terms) *(added)*

## Stage 6: Present it

- [ ] Open the app (use it yourself)
- [ ] Write a followable README
- [ ] Put the demo on the CV

---

## My project

- Project idea: ______________________
- Start date: ______________________
- Repo / live link: ______________________

## Progress notes

| Date | What I did | What I learned |
|---|---|---|
| 2026-11-10 | Built `src/rag_playground/`: two-step and agentic RAG over my 161k-word D&D campaign summary, on local Ollama models. Timed gemma against qwen. Moved the vectors into LanceDB with numpy as fallback. Added a PR rule, CI and pre-commit to the repo. | Retrieval is cheap, the chat model is the slow part. A small fast model answers simple lookups fine but searches once and stops on questions that span chapters. 657 vectors need no vector database. RAG is for facts, fine-tuning is for behaviour. |
