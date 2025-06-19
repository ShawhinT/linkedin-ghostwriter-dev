import os
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Pydantic model for LLM judge response
class JudgeResponse(BaseModel):
    """
    This is a Pydantic model for the LLM judge response.
    It is used to parse the response from the LLM.
    
    The response is a JSON object with the following fields:
        - reasoning_steps: all the reasoning steps taken to reach the final label (i.e. all text before the final label)
        - label: a boolean of the final label
    """
    reasoning_steps: str
    label: bool

# LLM Judge: evaluate voice of post
def eval_voice(post, prompt_path="prompts/judge-voice/prompt-v7.md", model_name="gpt-4.1-2025-04-14"):
    """
    Evaluates the voice of a LinkedIn post using an LLM Judge.
    """
    # load prompt
    with open(prompt_path, "r") as file:
        judge_instructions = file.read()
    
    try:
        # generate response
        response = client.responses.parse(
            model=model_name,
            instructions=judge_instructions,
            input=post,
            text_format=JudgeResponse,
            temperature=0
        )

        # flip the label to be a pass/fail
        post_passed = not response.output_parsed.label
        
        return {
            "passed": post_passed,
            "reasoning": response.output_parsed.reasoning_steps,
        }
    except Exception as e:
        return {
            "passed": None,
            "reasoning": f"Error: {e}"
        }

# Rule-based: evaluate number of em-dashes
def eval_em_dashes(post):
    """
    Evaluates the number of em-dashes in a post.
    """
    count = post.count("—")
    return {
        "passed": count <= 1,
        "count": count
    }