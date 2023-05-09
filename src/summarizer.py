import openai_async
import asyncio
import nest_asyncio

import torch
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("gpt2")

def count_tokens(text):
    input_ids = torch.tensor(tokenizer.encode(text)).unsqueeze(0)
    return input_ids.shape[1]

def break_up_file_to_chunks(text, chunk_size=2000, overlap=100):
    tokens = tokenizer.encode(text)
    num_tokens = len(tokens)
    chunks = []
    for i in range(0, num_tokens, chunk_size - overlap):
        chunk = tokens[i:i + chunk_size]
        chunks.append(chunk)
    
    return chunks

async def summarize_meeting(prompt, timeout, max_tokens):
    
    #timeout = 30
    temperature = 0.5
    #max_tokens = 1000
    top_p = 1
    frequency_penalty = 0
    presence_penalty = 0
    
    # Call the OpenAI GPT-3 API
    response = await openai_async.complete(
        api_key = API_KEY,
        timeout=timeout,
        payload={
            "model": "gpt-3.5-turbo",
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty
        },
    )

    # Return the generated text
    return response

def main_summarizer_meet(text, debug=False):
    if debug:
        return "This is a test summary function"
    prompt_response = []
    prompt_tokens = []

    chunks = break_up_file_to_chunks(text)

    for i, chunk in enumerate(chunks):
        prompt_request = (
            f"Summarize this meeting transcript: {tokenizer.decode(chunks[i])}"
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        response = loop.run_until_complete(summarize_meeting(prompt = prompt_request, timeout=30, max_tokens = 1000))

        prompt_response.append(response.json()["choices"][0]["text"].strip())
        prompt_tokens.append(response.json()["usage"]["total_tokens"])

    prompt_request = f"Consoloidate these meeting summaries: {prompt_response}"

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response = loop.run_until_complete(summarize_meeting(prompt = prompt_request, timeout=45, max_tokens = 1000))
    return response.json()["choices"][0]["text"].strip()

# -----------------------------

def main_summarizer_action_items(text, debug=False):
    
    if debug:
        return "This is a test action items function"

    action_response = []
    action_tokens = []

    chunks = break_up_file_to_chunks(text)

    for i, chunk in enumerate(chunks):
        prompt_request = f"Provide a list of action items with a due date from the provided meeting transcript text: {tokenizer.decode(chunks[i])}"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(summarize_meeting(prompt = prompt_request, timeout=30, max_tokens = 1000))

        action_response.append(response.json()["choices"][0]["text"].strip())
        action_tokens.append(response.json()["usage"]["total_tokens"])

    return '\n'.join(action_response)