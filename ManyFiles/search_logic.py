from typing import List, Optional, Tuple
from rich.console import Console
from helper.helper1.helpers import find_content_from_url, call_llm_with_json
from connection_manager import ConnectionManager
from googlesearch import search
import json

console = Console()

# WebSocket connection manager
manager = ConnectionManager()

async def search_for_answer(websocket, model, url: str, question: str, user_choice: str, max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """
    Searches for the answer by looking at the provided URL.
    If no relevant answer is found, it searches additional links obtained via a web search.
    """
    console.print(f"Searching the provided URL: {url}", style="bold cyan")

    # Step 1: Extract content from the URL
    content = find_content_from_url(url)
    if not content:
        console.print(f"[bold red]No content found at the provided URL: {url}[/bold red]")
        return None, None

    # Step 2: Call LLM with content and question
    llm_result = call_llm_with_json(model, content, question)

    answer = llm_result.answer
    is_relevant = llm_result.is_relevant
    decision = llm_result.decision

    console.print("llm_result ==",llm_result)
    # Step 3: Return relevant answer if found
    if answer and is_relevant == "yes":
        console.print(f"✅ Relevant answer found: {answer}", style="bold green")
        return answer, url

    # Step 4: Handle more info or web search
    if decision == "more_info":
        await manager.send_personal_message(json.dumps({
            "message": "The LLM needs more information. Please provide a new URL and question."
        }), websocket)

        # Receive new URL/question from the WebSocket client
        data = await websocket.receive_text()
        new_data = json.loads(data)
        new_url = new_data.get("url")
        new_question = new_data.get("question")

        return await search_for_answer(websocket, model, new_url, new_question, user_choice, max_attempts)

    # Step 5: Web search for additional links if no relevant answer is found
    additional_links = []
    try:
        additional_links = [url for url in search(question, num_results=5)]
    except Exception as e:
        console.print(f"[bold red]Error during web search: {e}[/bold red]")

    # Step 6: Iterate through additional links
    attempts = 0
    for link in additional_links:
        console.print(f"🔍 Searching in URL: {link}", style="bold blue")
        content = find_content_from_url(link)
        if content:
            llm_result = call_llm_with_json(model, content, question)
            if "yes" in llm_result.is_relevant:
                return llm_result.answer, link
        attempts += 1
        if attempts >= max_attempts:
            console.print(f"[bold red]Max attempts reached: {attempts}[/bold red]")
            break

    console.print("[bold red]No relevant answer found after additional searches.[/bold red]")
    return None, None
