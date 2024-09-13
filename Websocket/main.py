
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from googlesearch import search
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
import json  # Structured output using JSON

# Configure the API key
genai.configure(api_key="api")

# Initialize the generative model and rich console
model = genai.GenerativeModel('gemini-1.5-flash')
console = Console()

# Initialize FastAPI app
app = FastAPI()

# Initialize conversation history
conversation_history = []

def add_to_history(question, answer, link):
    """
    Adds the question and answer to the conversation history in JSON format.
    """
    entry = {
        "question": question,
        "answer": answer,
        "link": link
    }
    conversation_history.append(entry)

    # Save history to a JSON file
    with open("conversation_history.json", "w") as history_file:
        json.dump(conversation_history, history_file, indent=4)

def display_history():
    """
    Displays the conversation history in a table format using rich.
    """
    table = Table(title="Conversation History")
    table.add_column("No.", justify="right", style="cyan", no_wrap=True)
    table.add_column("Question", style="magenta")
    table.add_column("Answer", style="green")
    table.add_column("Link", style="blue")

    for i, entry in enumerate(conversation_history, 1):
        table.add_row(str(i), entry['question'], entry['answer'], entry['link'])
    
    console.print(table)

def summarize_content(content):
    """
    Ask the LLM to summarize large content blocks.
    """
    try:
        prompt = f"Summarize the following content: {content}"
        response = model.generate_content(prompt)
        
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            return candidate.content.parts[0].text.strip() if candidate.content.parts else "No summary available."
        else:
            return "No summary generated."
    except Exception as e:
        console.print(f"[bold red]Error in LLM response during summarization:[/bold red] {e}")
        return "Error generating summary."

def extract_content_from_url(url):
    """
    This function fetches the content from the provided URL.
    It uses requests and BeautifulSoup to extract the text.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP errors
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text(separator=' ', strip=True)
        return content
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching URL {url}:[/bold red] {e}")
        return None

def ask_llm_about_content(content, question, user_choice):
    """
    This function sends the content and the question to the LLM.
    The LLM will try to answer based on the content provided, and handle safety concerns.
    """
    try:
        prompt = f"Here is the content: {content}\n\nAnswer this question: {question}, don't use your information, stick to the content"
        response = model.generate_content(prompt)
        
        # Check if the response contains candidates
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            
            # Check if the content was not generated due to safety concerns
            if candidate.finish_reason == "SAFETY":
                return "Content generation blocked due to safety concerns."
            
            if hasattr(candidate, 'content'):
                if hasattr(candidate.content, 'parts'):
                    # Summarize or provide a detailed response based on user choice
                    if user_choice == "summary":
                        return summarize_content(candidate.content.parts[0].text.strip())
                    else:
                        return candidate.content.parts[0].text.strip()
                else:
                    return "No parts found in content."
            else:
                return "No content found in the candidate."
        else:
            return "No candidates returned in the response."
    
    except Exception as e:
        console.print(f"[bold red]Error in LLM response:[/bold red] {e}")
        return None

def find_answer_in_url(url, question, user_choice):
    """
    This function extracts content from the URL and asks the LLM
    if it can find the answer to the provided question.
    """
    content = extract_content_from_url(url)
    if not content:
        return None
    answer = ask_llm_about_content(content, question, user_choice)
    if answer:
        return answer
    return None

def search_additional_links(question, num_results=5):
    """
    This function searches Google for additional links based on the question.
    It returns a list of URLs from the search results.
    """
    console.print(f"🔍 Searching the web for more information about: [bold yellow]{question}[/bold yellow]")
    try:
        search_results = []
        for url in search(question, num_results=num_results):
            search_results.append(url)
        return search_results
    except Exception as e:
        console.print(f"[bold red]Error during web search:[/bold red] {e}")
        return []

def analyze_answer_relevance(answer, question):
    """
    This function sends the answer and the question to the LLM to check if the answer is relevant.
    The LLM will analyze whether the answer directly addresses the question's topic.
    """
    try:
        prompt = (
            f"Question: {question}\n\n"
            f"Answer: {answer}\n\n"
            "Does the answer directly address the question? "
            "If the answer is about something else or doesn't contain relevant information, respond with 'no'. "
            "Only respond 'yes' if the answer specifically answers the question's topic."
        )
        response = model.generate_content(prompt)
        
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            relevance_check = candidate.content.parts[0].text.strip().lower()
            
            if 'yes' in relevance_check:
                return True
            elif 'no' in relevance_check:
                return False
            else:
                return False  # If the LLM response is ambiguous, assume irrelevant
        else:
            return False
    except Exception as e:
        console.print(f"[bold red]Error in LLM response during relevance check:[/bold red] {e}")
        return False


def search_for_answer(url, question, user_choice, max_attempts=2):
    """
    This function searches for the answer by first looking at the provided URL.
    If no relevant answer is found, it searches additional links obtained via a web search.
    """
    console.print(Panel(f"Searching the provided URL: {url}", style="bold cyan"))
    
    # Try the user's provided URL first
    answer = find_answer_in_url(url, question, user_choice)
    
    # Check if the LLM finds the answer relevant to the question
    if answer and analyze_answer_relevance(answer, question):
        console.print(Panel(f"✅ Relevant answer found in the provided URL:\n{answer}", style="bold green"))
        return answer, url
    else:
        console.print(Panel("❌ No relevant answer found in the provided URL. Searching additional links...", style="bold red"))
    
    # If no relevant answer is found, search for additional links
    additional_links = search_additional_links(question)
    
    attempts = 0
    for link in additional_links:
        console.print(f"🔍 Searching in URL: [bold blue]{link}[/bold blue]")
        answer = find_answer_in_url(link, question, user_choice)
        
        # Check if the LLM finds the answer relevant
        if answer and analyze_answer_relevance(answer, question):
            console.print(Panel(f"✅ Relevant answer found in additional link:\n{answer}", style="bold green"))
            return answer, link
        
        attempts += 1
        if attempts >= max_attempts:
            console.print(f"[bold red]Max attempts reached: {attempts}[/bold red]")
            break
    
    console.print("[bold red]No relevant answer found after checking additional links.[/bold red]")
    return None, None

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
            answer, link = search_for_answer(url, question, "detailed")

            console.print(f"Sending answer: {answer}")  # Log the answer before sending it back

            # Step 4: Send the answer, question, and link back to the client
            response_data = json.dumps({
                "question": question,
                "answer": answer,
                "link": link
            })

            await manager.send_personal_message(response_data, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client disconnected")



@app.get("/")
async def root():
    return {"message": "Welcome to the WebSocket-based LLM Query Service"}

def main():
    """
    Main function to take user input from the console and find answers
    from the provided URL and the question.
    """
    while True:
        user_url = Prompt.ask("Please provide the URL")
        question = Prompt.ask("Please provide the question")
        
        # Ask the user for their preferred type of answer: summary or detailed
        user_choice = Prompt.ask("Would you like a summary or a detailed answer?", choices=["summary", "detailed"], default="detailed")
        
        # Try to find the answer by searching through the user's URL and related links
        answer, link = search_for_answer(user_url, question, user_choice)
    
        if answer:
            console.print(Panel(f"\nAnswer: {answer}\n\nRelated Information Found in the link: {link}", style="bold green"))
            add_to_history(question, answer, link)
        else:
            console.print("[bold red]Sorry, the information couldn't be found.[/bold red]")
        
        # Ask if the user wants to see the conversation history
        show_history = Prompt.ask("\nWould you like to see the conversation history?", choices=["yes", "no"], default="yes")
        if show_history == 'yes':
            display_history()
        
        # Ask if the user wants to continue
        continue_search = Prompt.ask("\nWould you like to search for another question?", choices=["yes", "no"], default="yes")
        if continue_search != 'yes':
            console.print("[bold blue]\nGoodbye![/bold blue]")
            break

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("MyLLM:app", host="0.0.0.0", port=8004, reload=True)
