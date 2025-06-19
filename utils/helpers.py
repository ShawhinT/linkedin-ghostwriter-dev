from openai import OpenAI
from dotenv import load_dotenv
import os
from pydantic import BaseModel

# connect to openai API
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# funtion to generate posts
def generate_post(instructions, user_input, model_name, temp=1):

    class Post(BaseModel):
        writing_steps: str
        final_post: str
    
    response = client.responses.parse(
        model=model_name,
        instructions=instructions,
        input=user_input,
        temperature=temp,
        text_format=Post
    )

    return response