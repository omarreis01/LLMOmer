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
genai.configure(api_key="AIzaSyAW1gHGYSLAHkg1tkPNG5tfvnQ_MJw64wM")

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

def find_content_from_url(url: str) -> Optional[str]:
    """
    This function extracts content from the URL.
    """
    content: str = ""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text(separator=' ', strip=True)
        return content
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching URL {url}:[/bold red] {e}")
        return None
def call_llm_with_json(content: str, question: str) -> Dict:
    """
    Calls the LLM once and returns a JSON result with answer, relevance, and decision info.
    """
    prompt: str = (
        f"Here is the content: {content}\n\n"
        f"Question: {question}\n\n"
        f"Firstly Create the answer part in JSON with question from the content, DONT USE YOUR BACK-UP INFORMATION, strictly stick to the content if relevant information cannot be found you can say I dont find the information from the content"
        f"For the is_relevant part in JSON If the answer doesn't contain relevant information, do the is_relevant part 'no'.Only do the is_relevant part 'yes' if the answer specifically answers the question's topic."
        f"For the decision part in JSON :Evaluate how closely the question is related to the content in the answer:\n If the question is loosely related to the content (e.g., both belong to similar categories or fields, like programming languages or technologies), respond with 'search_links'.\n If the question is completely unrelated to the content (e.g., a question about a political figure and content about programming), respond with 'more_info'."
        "Respond in the following JSON format:\n"
        "{\n"
        "  \"answer\": \"<Your answer here>\",\n"
        "  \"is_relevant\": \"yes\" or \"no\",\n"
        "  \"decision\": \"search_links\" or \"more_info\"\n"
        "}\n"
    )
    
    response = model.generate_content(prompt)
    
    if response.candidates and len(response.candidates) > 0:
        candidate = response.candidates[0]
        result = candidate.content.parts[0].text.strip() if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') else None
        

        
        # Clean up the result to remove backticks or any unwanted prefix like 'json'
        if result.startswith("```") and result.endswith("```"):
            result = result[3:-3].strip()  # Remove the backticks
        if result.startswith("json"):
            result = result[4:].strip()  # Remove the 'json' prefix

        
        # Try to parse the result as JSON
        try:
            return json.loads(result)  # Parse the cleaned result
        except json.JSONDecodeError:
            console.print(f"[bold red]Error: LLM did not return valid JSON. Output was: {result}[/bold red]")
            # Return a default fallback structure if JSON parsing fails
            return {
                "answer": result,  # Return the raw result as the answer if it's not in JSON format
                "is_relevant": "no",
                "decision": "search_links"
            }
    else:
        # Handle case when no candidate or empty response
        console.print(f"[bold red]Error: No candidates returned from the LLM.[/bold red]")
        return {
            "answer": None,
            "is_relevant": "no",
            "decision": "search_links"
        }

# Updated search_for_answer function
async def search_for_answer(websocket: WebSocket, url: str, question: str, user_choice: str, max_attempts: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """
    This function searches for the answer by first looking at the provided URL.
    If no relevant answer is found, it searches additional links obtained via a web search.
    If more information is required, it asks the WebSocket client to provide a new URL or question.
    """
    console.print(Panel(f"Searching the provided URL: {url}", style="bold cyan"))
    
    # Extract content from the URL
    content: Optional[str] = find_content_from_url(url)
    if not content:
        console.print(f"[bold red]No content found in the provided URL: {url}[/bold red]")
        return None, None
    # Call LLM once and get all required information
    llm_result = call_llm_with_json(content, question)
    console.print(f"[bold red]LLM_RESULT ======={llm_result}[/bold red] ")

    answer = llm_result.get("answer", None)
    is_relevant = llm_result.get("is_relevant","yes")
    decision = llm_result.get("decision", "search_links")

    if answer and is_relevant == "yes":
        console.print(Panel(f"✅ Relevant answer found:\n{answer}", style="bold green"))
        return answer, url
    else:
        console.print(Panel(f"❌ No relevant answer found.", style="bold red"))

    # If more information is needed
    if "more_info" in decision:
        console.print("HERE")
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
        answer = find_content_from_url(link)
        if answer:
            # Reuse the LLM with the extracted content from the new link
            llm_result = call_llm_with_json(answer, question)
            if llm_result.get("is_relevant", "no") == "yes":
                return llm_result.get("answer"), link
        
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

            # Step 2: Extract content from the URL and use the updated function
            answer, link = await search_for_answer(websocket, url, question, "detailed")
            
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
