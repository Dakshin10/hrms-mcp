import asyncio
from src.agent.hr_agent import HRAgent
from src.agent.conversation_memory import memory_store

async def main():
    agent = HRAgent()
    session_id = "cli_test"
    session = memory_store.get_or_create(session_id)
    
    print("Minori HR Agent — type 'quit' to exit, 'clear' to reset")
    print("=" * 50)

    loop = asyncio.get_event_loop()

    while True:
        try:
            question = await loop.run_in_executor(None, lambda: input("\nYou: "))
            question = question.strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if question.lower() == "quit":
            break
        if question.lower() == "clear":
            session.clear()
            print("Session cleared.")
            continue
        if not question:
            continue

        print("Agent: thinking...", end="\r")
        result = await agent.ask(
            question=question,
            history=session.get_history()
        )
        session.add_turn(question, result["answer"])
        
        print(f"Agent: {result['answer']}")
        if result["steps"] > 1:
            print(
                f"       [{result['steps']} steps, "
                f"tools: {', '.join(result['tools_used'])}]"
            )

if __name__ == "__main__":
    asyncio.run(main())
