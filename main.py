import google.generativeai as genai
import requests
from bs4 import BeautifulSoup

# Configure the API key
genai.configure(api_key="api")

# Initialize the generative model
model = genai.GenerativeModel('gemini-1.5-flash')

def extract_content_from_url(url):
    """
    This function fetches the content from the provided URL.
    It uses requests and BeautifulSoup to extract the text.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check for HTTP errors
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None

def ask_llm_about_content(content, question):
    """
    This function sends the content and the question to the LLM.
    The LLM will try to answer based on the content provided.
    """
    try:
        prompt = f"Here is the content: {content}\n\nAnswer this question: {question}"
        response = model.generate_content(prompt)
        return response.text.strip()  # Extract the answer
    except Exception as e:
        print(f"Error in LLM response: {e}")
        return None

def find_answer_in_url(url, question):
    """
    This function extracts content from the URL and asks the LLM
    if it can find the answer to the provided question.
    """
    content = extract_content_from_url(url)
    if not content:
        return None
    
    answer = ask_llm_about_content(content, question)
    if answer:
        return answer
    return None

def search_multiple_urls(urls, question, max_attempts=3):
    """
    This function searches through multiple URLs to find the answer.
    It stops after finding an answer or after max_attempts.
    """
    attempts = 0
    for url in urls:
        print(f"Searching in URL: {url}")
        answer = find_answer_in_url(url, question)
        if answer:
            print(f"Answer found: {answer}")
            return answer
        attempts += 1
        if attempts >= max_attempts:
            break
    print("No answer found after checking 3 URLs.")
    return None

def main():
    """
    Main function to take user input from the console and find answers
    from URLs and the question provided.
    """
    user_url = input("Please provide the main URL: ")
    question = input("Please provide the question: ")
    
    additional_urls = []
    while True:
        additional_url = input("Enter additional URL (or press Enter to stop): ")
        if not additional_url:
            break
        additional_urls.append(additional_url)
    
    # Try to find the answer by searching through the URLs
    answer = search_multiple_urls([user_url] + additional_urls, question)

    if answer:
        print(f"Final answer: {answer}")
    else:
        print("Sorry, the information couldn't be found.")

if __name__ == "__main__":
    main()
