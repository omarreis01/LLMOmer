import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from googlesearch import search
from rich.console import Console
from rich.panel import Panel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Optional, Tuple, Dict
import json


# Configure the API key
genai.configure(api_key="api")

# Initialize the generative model and rich console
model = genai.GenerativeModel('gemini-1.5-flash')
console = Console()

# Initialize FastAPI app
app = FastAPI()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

def find_answer_in_url(url: str, question: str, user_choice: str) -> Optional[str]:
    """
    This function extracts content from the URL and asks the LLM
    if it can find the answer to the provided question.
    """
    content: str = ""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text(separator=' ', strip=True)
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching URL {url}:[/bold red] {e}")
        return None
    
    # Ask LLM about the content
    prompt: str = f"Here is the content: {content}\n\nAnswer this question: {question}, don't use your information, stick to the content"
    response = model.generate_content(prompt)
    
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]
        return candidate.content.parts[0].text.strip() if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') else None
    return None

def analyze_answer_relevance(answer: str, question: str) -> bool:
    """
    This function sends the answer and the question to the LLM to check if the answer is relevant.
    The LLM will analyze whether the answer directly addresses the question's topic.
    """
    try:
        prompt: str = (
            f"Question: {question}\n\n"
            f"Answer: {answer}\n\n"
            "Does the answer directly address the question? "
        )
        response = model.generate_content(prompt)
        if response.candidates and len(response.candidates) > 0:
            relevance_check: str = response.candidates[0].content.parts[0].text.strip().lower()
            return 'yes' in relevance_check
        return False
    except Exception as e:
        console.print(f"[bold red]Error in LLM response during relevance check:[/bold red] {e}")
        return False

def llm_based_on_decision(question: str, answer: str) -> Optional[str]:
    """
    This function lets the LLM decide if it needs more information from the user or should search for other links.
    Returns 'more_info' if the LLM needs more details or 'search_links' if it decides to search for other links.
    """
    try:
        prompt: str = (
            f"Question: {question}\n\n"
            f"Answer: {answer}\n\n"
            "Evaluate how closely the question is related to the content in the answer:\n"
            "- If the question is loosely related to the content (e.g., both belong to similar categories or fields, like programming languages or technologies), respond with 'search_links'.\n"
            "- If the question is completely unrelated to the content (e.g., a question about a political figure and content about programming), respond with 'more_info'."
        )
        response = model.generate_content(prompt)
        if response.candidates and len(response.candidates) > 0:
            decision: str = response.candidates[0].content.parts[0].text.strip().lower()
            return decision
        return "search_links"
    except Exception as e:
        console.print(f"[bold red]Error in LLM decision:[/bold red] {e}")
        return "search_links"

# Updated search_for_answer function
async def search_for_answer(websocket: WebSocket, url: str, question: str, user_choice: str, max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """
    This function searches for the answer by first looking at the provided URL.
    If no relevant answer is found, it searches additional links obtained via a web search.
    If more information is required, it asks the WebSocket client to provide a new URL or question.
    """
    console.print(Panel(f"Searching the provided URL: {url}", style="bold cyan"))
    
    # Find answer based on the initial URL
    answer: Optional[str] = find_answer_in_url(url, question, user_choice)
    
    # Check if the answer is relevant
    if answer and analyze_answer_relevance(answer, question):
        console.print(Panel(f"✅ Relevant answer found in the provided URL:\n{answer}", style="bold green"))
        return answer, url
    else:
        console.print(Panel("❌ No relevant answer found in the provided URL.", style="bold red"))
    
    # Let the LLM decide whether more information is needed
    decision = llm_based_on_decision(question, answer)
    
    if "more_info" in decision:
        # Send a message to the WebSocket client asking for more information (new URL and question)
        await manager.send_personal_message(json.dumps({
            "message": "The LLM needs more information. Please provide a new URL and question."
        }), websocket)

        # Receive the new input (URL and question) from the WebSocket client
        data = await websocket.receive_text()
        new_data = json.loads(data)
        new_url = new_data.get("url")
        new_question = new_data.get("question")
        
        # Recursively call search_for_answer with the new input (including updated question)
        return await search_for_answer(websocket, new_url, new_question, user_choice, max_attempts)
    
    # Continue with additional link search if no relevant answer was found in the initial URL
    additional_links: List[str] = []
    num_results: int = 5
    console.print(f"🔍 Searching the web for more information about: [bold yellow]{question}[/bold yellow]")
    try:
        search_results: List[str] = [url for url in search(question, num_results=num_results)]
        additional_links = search_results
    except Exception as e:
        console.print(f"[bold red]Error during web search:[/bold red] {e}")
        additional_links = []
    
    attempts: int = 0
    for link in additional_links:
        console.print(f"🔍 Searching in URL: [bold blue]{link}[/bold blue]")
        answer = find_answer_in_url(link, question, user_choice)
        
        if answer and analyze_answer_relevance(answer, question):
            console.print(Panel(f"✅ Relevant answer found in additional link:\n{answer}", style="bold green"))
            return answer, link
        
        attempts += 1
        if attempts >= max_attempts:
            console.print(f"[bold red]Max attempts reached: {attempts}[/bold red]")
            break
    
    console.print("[bold red]No relevant answer found after checking additional links.[/bold red]")
    return None, None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Step 1: Receive the JSON message from the client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            url = message.get("url")
            question = message.get("question")

            console.print(f"Received URL: {url}, Question: {question}")  # Log URL and question

            # Step 2: Extract content from the URL
            answer, link = await search_for_answer(websocket, url, question, "detailed")  # Await the updated function
            
            if answer is None:
                answer = "No relevant information is found"
                link = "There is no link"
                
            console.print(f"Sending answer: {answer}")  # Log the answer before sending it back

            # Step 4: Send the answer, updated question, and link back to the client
            response_data = json.dumps({
                "question": question,  # Ensure the updated question is sent back
                "answer": answer,
                "link": link
            }, ensure_ascii=False, indent=4)  # Properly format JSON with readable indentations

            await manager.send_personal_message(response_data, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client disconnected")
