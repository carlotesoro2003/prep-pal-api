import google.generativeai as genai
import os
import re

# Initialize Google Generative AI with the API key from environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

def extract_json_from_markdown(text):
    # Extract JSON from markdown code block
    match = re.search(r"```json\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text


# Generate interview questions for a specific role
def generate_interview_questions(role: str, difficulty: str = "medium", num_questions: int = 5):
    prompt = (
        f"Generate {num_questions} realistic interview questions for a {role} position. "
        f"Difficulty: {difficulty}. Return as a JSON list of objects with 'title', 'description', 'type', and 'difficulty'."
    )
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    import json

    print("Gemini raw response:", response.text)
    if not response.text:
        raise Exception("Gemini API returned empty response.")
    json_str = extract_json_from_markdown(response.text)
    try:
        return json.loads(json_str)
    except Exception as e:
        raise Exception(f"Gemini API did not return valid JSON. Extracted: {json_str}") from e


# Generate AI feedback for a candidate's answer to an interview question
def ai_employer_feedback(question: str, answer: str):
    prompt = (
        f"You are an employer. Here is the interview question: '{question}'. "
        f"Here is the candidate's answer: '{answer}'. Give detailed feedback and a follow-up question."
    )
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text    