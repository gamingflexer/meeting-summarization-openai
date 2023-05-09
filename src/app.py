import logging
import gradio as gr
import os
import zipfile
import pydub
import datetime

import openai
import jwt

from summarizer import count_tokens,main_summarizer_action_items,main_summarizer_meet
from decouple import config

DEBUG = True
API_KEY = config('API_KEY')
model_id = 'whisper-1'
SECRET_KEY = "$§%§$secret"

# Set the summarization parameters
# Set the maximum chunk size and tokens per chunk
max_chunk_size = 2000
max_tokens_per_chunk = 500
temperature = 0.7
top_p = 0.5
frequency_penalty = 0.5
temp_dir = os.path.join(os.path.dirname(__file__), 'temp')

title = description = article = "Meeting Summariser ⚡️ "

logger = logging.getLogger("Summariser")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s;%(levelname)s;%(message)s", "%Y-%m-%d %H:%M:%S")
ch.setFormatter(formatter)
logger.addHandler(ch)

def authentication(username, password):
    if username == "admin" and password == "admin":
        return True


def transcribe_audio(audio_file_path, temp_folder_path):
    if DEBUG:
        return "This is a test transcription"
    
    max_size_bytes = 20 * 1024 * 1024  # 24 MB

    if os.path.getsize(audio_file_path) <= max_size_bytes:
        media_file = open(audio_file_path, 'rb')
        response = openai.Audio.transcribe(
            api_key=API_KEY,
            model=model_id,
            file=media_file
        )
        return response['text']
    else:
        sound = pydub.AudioSegment.from_file(audio_file_path, format="mp3")
        chunks = pydub.utils.make_chunks(sound, max_size_bytes)
        transcriptions = []
        for i, chunk in enumerate(chunks):
            print("chunk ", i)
            chunk_path = os.path.join(temp_folder_path, f"audio_chunk_{i}.mp3")
            chunk.export(chunk_path, format="mp3")
            response = openai.Audio.transcribe(api_key=API_KEY,model=model_id,file=open(chunk_path, 'rb'))
            transcriptions.append(response['text'])

        return ' '.join(transcriptions)

def download_files(transcription: str, summary: str):
    time_now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Create transcription file
    transcript_file_path = os.path.join(temp_dir, f'transcription_{time_now}.txt')
    with open(transcript_file_path, 'w') as f:
        f.write(transcription)
    # Create summary file
    summary_file_path = os.path.join(temp_dir, f'summary_{time_now}.txt')
    with open(summary_file_path, 'w') as f:
        f.write(summary)
    # Create zip file
    zip_file_path = os.path.join(temp_dir, 'download.zip')
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add transcription file to zip
        zip_file.write(transcript_file_path, 'transcription.txt')
        # Add summary file to zip
        zip_file.write(summary_file_path, 'summary.txt')
    return zip_file_path
    
def clean_trancript(text):
    return text

def main_meet_summarizer(audio_file):
    
    summary = ""
    transcript = ""
    action_items = ""
    
    print("Starting Transcription")
    transcript = transcribe_audio(audio_file,temp_dir)
    print(f"Starting Summarization | {count_tokens(transcript)}")
    cleaned_transcript = clean_trancript(transcript)
    summary = main_summarizer_meet(cleaned_transcript, debug=DEBUG)
    action_items = main_summarizer_action_items(cleaned_transcript, debug=DEBUG)
    print("Finished Summarization")
    return summary,transcript,download_files(transcription = transcript, summary = (summary + action_items))


summarizer_interface = gr.Interface(
    fn=main_meet_summarizer,
    inputs=[gr.inputs.Audio(source='upload', type='filepath', label='Audio File')],
    outputs=[gr.outputs.Textbox(label='Summary'), gr.outputs.Textbox(label='Transcription'),gr.outputs.File(label="Download files here"),],
    title='Summarizer',
    description='Transcribe speech in an audio file & summarize it.',
)

summarizer_interface.launch(debug=True)