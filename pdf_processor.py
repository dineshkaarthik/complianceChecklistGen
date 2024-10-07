import openai
import requests
import PyPDF2
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from concurrent.futures import ThreadPoolExecutor
import time
import json
import os
from logger import main_logger as logger

# Set up OpenAI API key and endpoint for chat completions
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_CHAT_COMPLETION_ENDPOINT = 'https://api.openai.com/v1/chat/completions'

# Function to extract text from a PDF file
def get_pdf_metadata(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
    return text

# Function to make an actual API call to OpenAI chat completion (GPT-4)
def process_chunk_gpt4(chunk, index,retries=5, wait_time=2):
    logger.info(f"Processing chunk number: {index}")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4o-mini",  # Use GPT-4 model
        "messages": [
            {"role": "system", "content": "You are a compliance expert."},
            {"role": "user", "content": f"""
            Review the following section for critical compliance-related information, especially focusing on regulatory requirements, cybersecurity policies, audit guidelines, and reporting standards.

            Provide the output in a detailed, structured checklist format with headings and sub-headings, including but not limited to Governance & Risk Management, Data Security & Protection, Monitoring & Detection, Incident Response & Recovery, and Resilience & Evolution. Use bullet points for each specific compliance requirement.

            Here's the section to review:

            {chunk}

            Summarize the compliance requirements mentioned and provide a checklist that looks like this:

            Governance & Risk Management:
            - Establish clear cybersecurity roles and responsibilities for senior management and all employees.
            - Document and implement a cybersecurity and cyber resilience policy approved by the Board/Partners/Proprietor.
            - Develop a Cyber Risk Management Framework to continuously identify, analyze, and monitor cyber risks.

            Data Security & Protection:
            - Implement an Authentication and Access Control Policy and ensure effective logging of all access.
            - Design and implement network segmentation to restrict access to sensitive information.

            Continue in this format for all the relevant sections based on the content provided.
            """}
        ],
        "max_tokens": 1500  # Increase max tokens if needed for detailed output
    }

    for attempt in range(retries):
        try:
            response = requests.post(OPENAI_CHAT_COMPLETION_ENDPOINT, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            logger.info(f"Completed chunk number: {index}")  # Check for HTTP errors
            return response.json()['choices'][0]['message']['content']  # Return the chat completion result
        except requests.exceptions.HTTPError as e:
            logger.exception(f"Error processing chunk number: {index}, exception {e}")
            if response.status_code == 429:
                logger.info(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                wait_time *= 2  # Exponential backoff: double the wait time for each retry
            else:
                raise e  # Raise other errors
    raise Exception(f"Failed after {retries} retries.")

# Parallel processing of document chunks (actual API calls)
def process_document_parallel(chunks, delay=2):
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = []
        for index, chunk in enumerate(chunks):
            result = executor.submit(process_chunk_gpt4, chunk, index)
            results.append(result)
            time.sleep(delay)  # Simulating delay to avoid rate limits
        return [result.result() for result in results]

# Generate a Checklist based on the results
def generate_checklist(results):
    # Placeholder for generating a compliance checklist based on results (can customize based on actual needs)
    checklist = {
        "Checklist": [
            "Ensure data encryption is enabled",
            "Conduct quarterly audits",
            "Implement multi-factor authentication"
        ]
    }
    return checklist

# Main processing function
def process_pdf(text, chunk_size=50000):
    # Simulating the extraction of relevant sections
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)] # Simulated chunking

    # Process relevant sections (API call)
    logger.info(f"Processing total chunks: {len(chunks)}")
    results = process_document_parallel(chunks, delay=2)

    # Combine results into a single output
    final_output = "\n".join(results)

    # Generate a checklist
    checklist = generate_checklist(results)

    # Combine the final output and checklist
    result = {
        "compliance_info": final_output,
        "checklist": checklist
    }

    return result

# Example usage (commented out for production use)
# if __name__ == "__main__":
#     pdf_path = "example.pdf"
#     document_text = get_pdf_metadata(pdf_path)
#     result = process_pdf(document_text)
#     print(json.dumps(result, indent=4))
