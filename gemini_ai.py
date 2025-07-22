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
def generate_interview_questions(role: str, difficulty: str = "medium", num_questions: int = 5, intro=None):
    prompt = (
        f"Generate {num_questions} realistic interview questions for a {role} position. "
        f"Difficulty: {difficulty}. Return as a JSON list of objects with 'title', 'description', 'type', and 'difficulty'."
        f"Do NOT explain the purpose of the question. Only provide the question itself."
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
def ai_employer_feedback(question: str, answer: str, follow_up_count: int = 0):
    # Only ask a follow-up if less than 2 have been asked
    ask_follow_up = follow_up_count < 2

    prompt = (
        f"You are an AI interviewer conducting a professional interview. "
        f"Question asked: '{question}'\n"
        f"Candidate's answer: '{answer}'\n\n"
        f"Provide a conversational response that:\n"
        f"1. Acknowledges their answer naturally\n"
        f"2. Gives constructive feedback\n"
        + (f"3. Asks a thoughtful follow-up question (start the follow-up with 'Follow-up:')\n" if ask_follow_up else "")
        + f"4. Speaks in a friendly, professional tone like Siri or Alexa\n"
        f"Keep it concise and conversational for text-to-speech. "
        f"Limit your feedback to 2-3 sentences."
    )
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    text = response.text or ""

    feedback = text
    follow_up = None
    if "Follow-up:" in text:
        parts = text.split("Follow-up:", 1)
        feedback = parts[0].strip()
        follow_up = parts[1].strip()
    return feedback, follow_up, (follow_up_count + 1 if follow_up else follow_up_count)

def generate_conversational_question(role: str, intro: str = None):
    """Generate a more conversational first question"""
    prompt = (
        f"You are conducting an interview for a {role} position. "
        f"The candidate introduced themselves as: '{intro}'\n"
        f"Start the interview with a warm, conversational opening and then ask "
        f"an appropriate first question. Keep it natural for text-to-speech delivery. "
        f"Speak like a professional interviewer would."
        f"Do NOT explain the purpose of the question. Only provide the question itself."
    )
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text