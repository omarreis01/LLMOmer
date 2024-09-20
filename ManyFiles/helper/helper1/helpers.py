import requests
from bs4 import BeautifulSoup
import json
from rich.console import Console
from OmerModels import OutputType


console = Console()

def find_content_from_url(url: str) -> str:
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

def call_llm_with_json(model, content: str, question: str) -> dict:
    prompt: str = (
        f"Here is the content: {content}\n\n"
        f"Question: {question}\n\n"
        f"Firstly Create the answer part in JSON with question from the content, DONT USE YOUR BACK-UP INFORMATION, strictly stick to the content if relevant information cannot be found you can say I dont find the information from the content."
        f"For the is_relevant part in JSON If the answer doesn't contain relevant information, do the is_relevant part 'no'.Only do the is_relevant part 'yes' if the answer specifically answers the question's topic."
        f"For the decision part in JSON: Evaluate how closely the question is related to the content in the answer:\n If the question is loosely related to the content (e.g., both belong to similar categories or fields, like programming languages or technologies), respond with 'search_links'.\n If the question is completely unrelated to the content (e.g., a question about a political figure and content about programming), respond with 'more_info'."
        "Respond in the following JSON format, dont write any additional thing other than json format:\n"
        "{\n"
        "  \"answer\": \"<Your answer here>\",\n"
        "  \"is_relevant\": \"yes\" or \"no\",\n"
        "  \"decision\": \"search_links\" or \"more_info\"\n"
        "}\n"
    )

    response = model.generate_content(prompt)
    result = response.strip()

    try:
        if result.startswith("```") and result.endswith("```"):
            result = result[3:-3].strip()

        if result.startswith("json"):
            result = result[4:].strip()
        result_json = json.loads(result)
        return OutputType(**result_json)
    
    except json.JSONDecodeError:
        console.print(f"[bold red]Error: LLM did not return valid JSON. Output was: {result}[/bold red]")
        return {
            "answer": result,
            "is_relevant": "no",
            "decision": "search_links"
        }
