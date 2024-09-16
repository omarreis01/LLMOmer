import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from googlesearch import search
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List, Optional, Tuple  
import json  
import os 
import xml.etree.ElementTree as ET  
import uvicorn

#from dotenv import load_dotenv
# Load environment variables from .env file
##load_dotenv()


# Configure the API key
genai.configure(api_key="AIzaSyAW1gHGYSLAHkg1tkPNG5tfvnQ_MJw64wM")

# Initialize the generative model and rich console
model = genai.GenerativeModel('gemini-1.5-flash')
console = Console()

# Initialize FastAPI app
app = FastAPI()

# Initialize conversation history
conversation_history = []

def clean_content(content_output: str) -> str:
    """
    Clean the content by removing triple backticks and other extraneous characters
    that may cause JSON or XML deserialization to fail.
    Ensure all content is preserved.
    """
    # Remove backticks that wrap the JSON content
    cleaned_content = content_output.strip("```json").strip("```").strip()
    
    # Ensure multiline content is preserved correctly
    return cleaned_content

def deserialize_json(content_output: str) -> Optional[str]:
    """
    Deserialize the LLM's JSON response and return a formatted output.
    """
    try:
        # Clean the content before deserialization
        cleaned_content = clean_content(content_output)
        
        # Log cleaned content for debugging
        print(f"Cleaned JSON content for deserialization: {cleaned_content}")
        
        # Attempt to load the cleaned JSON, ensuring multiline content is captured
        deserialized_data = json.loads(cleaned_content)
        return json.dumps(deserialized_data, indent=4)  # Pretty print JSON response
    except json.JSONDecodeError as e:
        print(f"Error deserializing JSON: {e}")
        print(f"Original content received: {content_output}")  # Print original content for debugging
        return "Error deserializing JSON."


def deserialize_xml(content_output: str) -> Optional[str]:
    """
    Deserialize the LLM's XML response and return a formatted output.
    """
    try:
        # Clean the content before deserialization
        cleaned_content = clean_content(content_output)
        
        # Log cleaned content for debugging
        console.print(f"[bold green]Cleaned XML content for deserialization:[/bold green] {cleaned_content}")
        
        # Attempt to load the cleaned XML
        root = ET.fromstring(cleaned_content)
        return ET.tostring(root, encoding='unicode', method='xml')  # Pretty print XML response
    except ET.ParseError as e:
        console.print(f"[bold red]Error deserializing XML:[/bold red] {e}")
        console.print(f"[bold red]Original content received: {content_output}[/bold red]")  # Print original content for debugging
        return "Error deserializing XML."
def llm_decision_based_on_answer(answer: str, question: str) -> str:
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
        print(response)
        if response.candidates and len(response.candidates) > 0:
            decision: str = response.candidates[0].content.parts[0].text.strip().lower()
            return decision
        return "search_links"  # Default to searching more links if no decision is made
    except Exception as e:
        console.print(f"[bold red]Error in LLM decision:[/bold red] {e}")
        return "search_links"

def ask_llm_about_content(content: str, question: str, user_choice: str, output_format: str = "json") -> Optional[str]:
    """
    This function sends the content and the question to the LLM.
    The LLM will try to answer based on the content provided and handle safety concerns.
    The output can be in JSON or XML format.
    """
    try:
        prompt: str = (
            f"Here is the content: {content}\n\n"
            f"Answer this question: {question}, don't use your information, stick to the content.\n"
            f"Return the result in {output_format} format."
        )
        response = model.generate_content(prompt)

        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            
            if candidate.finish_reason == "SAFETY":
                return "Content generation blocked due to safety concerns."
            
            content_output = candidate.content.parts[0].text.strip()

            # Check if the content is empty
            if not content_output:
                console.print(f"[bold red]Error: LLM returned an empty response.[/bold red]")
                return "LLM returned an empty response."

            # Now attempt to deserialize the response based on the format
            if output_format == "json":
                return deserialize_json(content_output)
            elif output_format == "xml":
                return deserialize_xml(content_output)
            else:
                return "Unsupported output format."
        else:
            return "No candidates returned in the response."
    
    except Exception as e:
        console.print(f"[bold red]Error in LLM response:[/bold red] {e}")
        return None


def find_answer_in_url(url: str, question: str, user_choice: str) -> Optional[str]:
    """
    This function extracts content from the URL and asks the LLM
    if it can find the answer to the provided question.
    """
    content: str = ""
    try:
        response = requests.get(url)
        response.raise_for_status()  # This will raise an exception for invalid responses
        soup = BeautifulSoup(response.text, 'html.parser')
        content = soup.get_text(separator=' ', strip=True)
        
        # Check if the content is empty or contains insufficient information
        if not content:
            console.print(f"[bold red]Error: No content found in URL {url}[/bold red]")
            return None
    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching URL {url}:[/bold red] {e}")
        return None

    return ask_llm_about_content(content, question, user_choice)


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
            "If the answer is about something else or doesn't contain relevant information, respond with 'no'. "
            "Only respond 'yes' if the answer specifically answers the question's topic."
        )
        response = model.generate_content(prompt)
        
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            relevance_check: str = candidate.content.parts[0].text.strip().lower()
            return 'yes' in relevance_check
        
        return False
    except Exception as e:
        console.print(f"[bold red]Error in LLM response during relevance check:[/bold red] {e}")
        return False
async def search_for_answer(url: str, question: str, user_choice: str, output_format: str = "json", websocket: WebSocket = None, additional_info: str = None) -> Tuple[Optional[str], Optional[str]]:
    """
    This function searches for the answer by first looking at the provided URL.
    If no relevant answer is found, it either asks the user for more information or searches additional links obtained via a web search.
    """
    console.print(Panel(f"Searching the provided URL: {url}", style="bold cyan"))

    # Use additional information if provided
    if additional_info:
        console.print(f"Using additional info provided by user: {additional_info}")
        question += f" {additional_info}"

    answer: Optional[str] = find_answer_in_url(url, question, user_choice)

    # If answer is found and it's relevant, return it immediately
    if answer and analyze_answer_relevance(answer, question):
        console.print(Panel(f"✅ Relevant answer found in the provided URL:\n{answer}", style="bold green"))
        response_data = json.dumps({
            "question": question,
            "answer": answer,
            "link": url,
            "format": output_format
        })
        await manager.send_personal_message(response_data, websocket)
        return ask_llm_about_content(answer, question, user_choice, output_format), url
    else:
        console.print(Panel("❌ No relevant answer found in the provided URL. Asking LLM for the next step...", style="bold red"))

    # Ask LLM for next steps: more info or search additional links
    decision = llm_decision_based_on_answer(answer or "", question)
    console.print(f"LLM decision: {decision}")

    # If LLM requests more info, ask user via WebSocket
    if "more_info" in decision and websocket:
        await manager.send_personal_message(json.dumps({
            "type": "info_request",
            "message": "The LLM needs more information. Please provide additional details about the question or URL."
        }), websocket)
        # Stop here and wait for user response
        return None, None

    # If LLM decides to search for additional links, proceed with that
    elif "search_links" in decision:
        console.print(Panel("🔍 Searching additional links based on the question...", style="bold cyan"))
        additional_links: List[str] = []
        num_results: int = 5
        try:
            search_results: List[str] = [url for url in search(question, num_results=num_results)]
            additional_links = search_results
        except Exception as e:
            console.print(f"[bold red]Error during web search:[/bold red] {e}")
            additional_links = []

        # Try searching through the additional links
        for link in additional_links:
            console.print(f"🔍 Searching in URL: [bold blue]{link}[/bold blue]")
            answer = find_answer_in_url(link, question, user_choice)

            if answer and analyze_answer_relevance(answer, question):
                console.print(Panel(f"✅ Relevant answer found in additional link:\n{answer}", style="bold green"))
                response_data = json.dumps({
                    "question": question,
                    "answer": answer,
                    "link": link,
                    "format": output_format
                })
                await manager.send_personal_message(response_data, websocket)
                return ask_llm_about_content(answer, question, user_choice, output_format), link

        # If all additional links have been searched and no relevant answer is found, send the final message
        console.print("[bold red]No relevant answer found after checking additional links.[/bold red]")
        response_data = json.dumps({
            "question": question,
            "answer": "No relevant information found after searching additional links",
            "link": "No relevant link",
            "format": output_format
        })
        await manager.send_personal_message(response_data, websocket)
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
        additional_info = None  # Variable to hold additional information
        while True:
            # Step 1: Receive the JSON message from the client
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "info_response":
                # Continue searching with the additional information provided by the client
                url = message.get("url")
                question = message.get("question")
                additional_info = message.get("additional_info")
                user_choice = message.get("user_choice", "detailed")
                output_format = message.get("format", "json")

                console.print(f"Continuing with additional information: {additional_info}")
                answer, link = await search_for_answer(url, question, user_choice, output_format, websocket, additional_info)

                # Now send the updated answer back to the client after the additional info
                response_data = json.dumps({
                    "question": question,
                    "answer": answer or "No relevant information found",
                    "link": link or "No relevant link",
                    "format": output_format
                })

                await manager.send_personal_message(response_data, websocket)

            else:
                # Initial search
                url = message.get("url")
                question = message.get("question")
                output_format = message.get("format", "json")  # Get output format from client (default to JSON)
                user_choice = message.get("user_choice", "detailed")

                console.print(f"Received URL: {url}, Question: {question}, Format: {output_format}")

                # Step 2: Extract content from the URL
                answer, link = await search_for_answer(url, question, user_choice, output_format, websocket)
                
                if answer is None:
                    # Don't send "No relevant info" immediately; wait for additional info
                    await manager.send_personal_message(json.dumps({
                        "type": "info_request",
                        "message": "The LLM needs more information. Please provide additional details about the question or URL."
                    }), websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client disconnected")

@app.get("/")
async def root():
    return {"message": "Welcome to the WebSocket-based LLM Query Service with JSON/XML output"}

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
            entry = {
                "question": question,
                "answer": answer,
                "link": link
            }
            conversation_history.append(entry)

            # Save history to a JSON file
            with open("conversation_history.json", "w") as history_file:
                json.dump(conversation_history, history_file, indent=4)
        else:
            console.print("[bold red]Sorry, the information couldn't be found.[/bold red]")
        
        # Ask if the user wants to see the conversation history
        show_history = Prompt.ask("\nWould you like to see the conversation history?", choices=["yes", "no"], default="yes")
        if show_history == 'yes':
            table = Table(title="Conversation History")
            table.add_column("No.", justify="right", style="cyan", no_wrap=True)
            table.add_column("Question", style="magenta")
            table.add_column("Answer", style="green")
            table.add_column("Link", style="blue")

            for i, entry in enumerate(conversation_history, 1):
                table.add_row(str(i), entry['question'], entry['answer'], entry['link'])
            
            console.print(table)

        
        # Ask if the user wants to continue
        continue_search = Prompt.ask("\nWould you like to search for another question?", choices=["yes", "no"], default="yes")
        if continue_search != 'yes':
            console.print("[bold blue]\nGoodbye![/bold blue]")
            break

if __name__ == "__main__":
    uvicorn.run("MyLLM:app", host="0.0.0.0", port=8004, reload=True)
