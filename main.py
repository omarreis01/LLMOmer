import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from googlesearch import search

# Configure the API key
genai.configure(api_key="AIzaSyAW1gHGYSLAHkg1tkPNG5tfvnQ_MJw64wM")

# Initialize the generative model
model = genai.GenerativeModel('gemini-1.5-flash')

# Initialize conversation history
conversation_history = []

def add_to_history(question, answer, link):
    """
    Adds the question and answer to the conversation history.
    """
    conversation_history.append({"question": question, "answer": answer, "link": link})

def display_history():
    """
    Displays the conversation history.
    """
    print("\n================= Conversation History =================")
    for i, entry in enumerate(conversation_history, 1):
        print(f"{i}.")
        print(f"  Q: {entry['question']}")
        print(f"  A: {entry['answer']}")
        print(f"  Link: {entry['link']}\n")
    print("========================================================\n")

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
        print(f"Error in LLM response during summarization: {e}")
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
        print(f"Error fetching URL {url}: {e}")
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
        print(f"Error in LLM response: {e}")
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
    print(f"Searching the web for more information about: {question}")
    try:
        search_results = []
        for url in search(question, num_results=num_results):
            search_results.append(url)
        return search_results
    except Exception as e:
        print(f"Error during web search: {e}")
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
        print(f"Error in LLM response during relevance check: {e}")
        return False


def search_for_answer(url, question, user_choice, max_attempts=2):
    """
    This function searches for the answer by first looking at the provided URL.
    If no relevant answer is found, it searches additional links obtained via a web search.
    """
    print(f"\nSearching the provided URL: {url}\n")
    
    # Try the user's provided URL first
    answer = find_answer_in_url(url, question, user_choice)
    
    # Check if the LLM finds the answer relevant to the question
    if answer and analyze_answer_relevance(answer, question):
        return answer, url
    else:
        print("No relevant answer found in the provided URL, searching additional links.")
    
    # If no relevant answer is found, search for additional links
    additional_links = search_additional_links(question)
    
    attempts = 0
    for link in additional_links:
        print(f"Searching in URL: {link}\n")
        answer = find_answer_in_url(link, question, user_choice)
        
        # Check if the LLM finds the answer relevant
        if answer and analyze_answer_relevance(answer, question):
            print(f"Relevant answer found in additional link: {answer}\n")
            return answer, link
        
        attempts += 1
        if attempts >= max_attempts:
            print(f"Max attempts reached: {attempts}")
            break
    
    print("No relevant answer found after checking additional links.")
    return None, None

def get_user_input(prompt, valid_choices=None):
    """
    Prompts the user for input and validates the response if valid_choices are provided.
    """
    while True:
        user_input = input(prompt).lower()
        if valid_choices:
            if user_input in valid_choices:
                return user_input
            else:
                print(f"Invalid choice. Please choose from: {', '.join(valid_choices)}.")
        else:
            return user_input

def main():
    """
    Main function to take user input from the console and find answers
    from the provided URL and the question.
    """
    while True:
        user_url = get_user_input("Please provide the URL: ")
        question = get_user_input("Please provide the question: ")
        
        # Ask the user for their preferred type of answer: summary or detailed
        user_choice = get_user_input("Would you like a summary or a detailed answer? (summary/detailed): ", ["summary", "detailed"])
        
        # Try to find the answer by searching through the user's URL and related links
        answer, link = search_for_answer(user_url, question, user_choice)
    
        if answer:
            print(f"\nAnswer: {answer}\nRelated Information Found in the link: {link}\n")
            add_to_history(question, answer, link)
        else:
            print("Sorry, the information couldn't be found.")
        
        # Ask if the user wants to see the conversation history
        show_history = get_user_input("\nWould you like to see the conversation history? (yes/no): ", ["yes", "no"])
        if show_history == 'yes':
            display_history()
        
        # Ask if the user wants to continue
        continue_search = get_user_input("\nWould you like to search for another question? (yes/no): ", ["yes", "no"])
        if continue_search != 'yes':
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    main()
