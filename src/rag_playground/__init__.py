import argparse

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    from rag_playground import rag
    from rag_playground.graph import load_graph
    from rag_playground.index import load_index

    parser = argparse.ArgumentParser(description="Ask questions about the D&D campaign.")
    parser.add_argument("--agentic", action="store_true", help="let the model decide to search")
    parser.add_argument("--hybrid", action="store_true", help="search by keyword as well as vector")
    parser.add_argument(
        "--graph", action="store_true", help="with --agentic: add a knowledge graph lookup tool"
    )
    parser.add_argument(
        "--grep", action="store_true", help="with --agentic: add a regular-expression search tool"
    )
    args = parser.parse_args()
    for flag in ("graph", "grep"):
        if getattr(args, flag) and not args.agentic:
            parser.error(f"--{flag} needs --agentic: it is a tool the model chooses to call")

    index = load_index(hybrid=args.hybrid)
    graph = load_graph(index.chunks) if args.graph else None
    agent = rag.agentic(index, graph=graph, grep=args.grep) if args.agentic else None

    mode = "Agentic" if args.agentic else "Two-step"
    search = "hybrid" if args.hybrid else "vector"
    print(f"{mode} RAG over {len(index.chunks)} chunks ({index.store}, {search} search).")
    while True:
        query = input("You: ")
        if query.lower() in ("exit", "quit"):
            break
        print(f"Assistant: {agent.chat(query) if agent else rag.two_step(index, query)}")


if __name__ == "__main__":
    main()
