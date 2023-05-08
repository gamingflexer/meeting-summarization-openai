import uuid
import logging
import math
import os
import tempfile
import zipfile
import time
import shutil
from multiprocessing import Pool

import gradio as gr
import jax.numpy as jnp
import numpy as np
from jax.experimental.compilation_cache import compilation_cache as cc
from transformers.models.whisper.tokenization_whisper import TO_LANGUAGE_CODE
from transformers.pipelines.audio_utils import ffmpeg_read

from whisper_jax import FlaxWhisperPipline


cc.initialize_cache("./jax_cache")
checkpoint = "openai/whisper-tiny"

DEBUG = False
BATCH_SIZE = 32
CHUNK_LENGTH_S = 30
NUM_PROC = 32
FILE_LIMIT_MB = 100000
YT_LENGTH_LIMIT_S = 72000  # limit to 2 hour YouTube files

title = description = article = " Whisper JAX ⚡️ "

language_names = sorted(TO_LANGUAGE_CODE.keys())

logger = logging.getLogger("whisper-jax-app")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s;%(levelname)s;%(message)s", "%Y-%m-%d %H:%M:%S")
ch.setFormatter(formatter)
logger.addHandler(ch)

temp_path_zip_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')


def identity(batch):
    return batch

def authentication(username, password):
    return username == password


def format_timestamp(seconds: float, always_include_hours: bool = False, decimal_marker: str = "."):
    if seconds is None:
        # we have a malformed timestamp so just return it as is
        return seconds
    milliseconds = round(seconds * 1000.0)

    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000

    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000

    seconds = milliseconds // 1_000
    milliseconds -= seconds * 1_000

    hours_marker = f"{hours:02d}:" if always_include_hours or hours > 0 else ""
    return f"{hours_marker}{minutes:02d}:{seconds:02d}{decimal_marker}{milliseconds:03d}"


if __name__ == "__main__":
    pipeline = FlaxWhisperPipline(checkpoint, dtype=jnp.bfloat16, batch_size=BATCH_SIZE)
    stride_length_s = CHUNK_LENGTH_S / 6
    chunk_len = round(CHUNK_LENGTH_S * pipeline.feature_extractor.sampling_rate)
    stride_left = stride_right = round(stride_length_s * pipeline.feature_extractor.sampling_rate)
    step = chunk_len - stride_left - stride_right
    pool = Pool(NUM_PROC)

    #do a pre-compile step so that the first user to use the demo isn't hit with a long transcription time
    logger.info("compiling forward call...")
    start = time.time()
    random_inputs = {"input_features": np.ones((BATCH_SIZE, 80, 3000))}
    random_timestamps = pipeline.forward(random_inputs, batch_size=BATCH_SIZE, return_timestamps=True)
    compile_time = time.time() - start
    logger.info(f"compiled in {compile_time}s")

    def tqdm_generate(inputs: dict, task: str, return_timestamps: bool, progress: gr.Progress):
        inputs_len = inputs["array"].shape[0]
        all_chunk_start_idx = np.arange(0, inputs_len, step)
        num_samples = len(all_chunk_start_idx)
        num_batches = math.ceil(num_samples / BATCH_SIZE)
        dummy_batches = list(
            range(num_batches)
        )  # Gradio progress bar not compatible with generator, see https://github.com/gradio-app/gradio/issues/3841

        dataloader = pipeline.preprocess_batch(inputs, chunk_length_s=CHUNK_LENGTH_S, batch_size=BATCH_SIZE)
        progress(0, desc="Pre-processing audio file...")
        logger.info("pre-processing audio file...")
        dataloader = pool.map(identity, dataloader)
        logger.info("done post-processing")

        start_time = time.time()
        logger.info("transcribing...")
        model_outputs = [
            pipeline.forward(
                batch, batch_size=BATCH_SIZE, task=task, return_timestamps=True
            )
            for batch, _ in zip(
                dataloader, progress.tqdm(dummy_batches, desc="Transcribing...")
            )
        ]
        runtime = time.time() - start_time
        logger.info("done transcription")

        logger.info("post-processing...")
        post_processed = pipeline.postprocess(model_outputs, return_timestamps=True)
        text = post_processed["text"]
        if return_timestamps:
            timestamps = post_processed.get("chunks")
            timestamps = [
                f"[{format_timestamp(chunk['timestamp'][0])} -> {format_timestamp(chunk['timestamp'][1])}] {chunk['text']}"
                for chunk in timestamps
            ]
            text = "\n".join(str(feature) for feature in timestamps)
        logger.info("done post-processing")
        return text, runtime

    def transcribe_chunked_audio(inputs, task, return_timestamps, progress=gr.Progress()):
        progress(0, desc="Loading audio file...")
        logger.info("loading audio file...")
        if inputs is None:
            logger.warning("No audio file")
            raise gr.Error("No audio file submitted! Please upload an audio file before submitting your request.")
        file_size_mb = os.stat(inputs).st_size / (1024 * 1024)
        if file_size_mb > FILE_LIMIT_MB:
            logger.warning("Max file size exceeded")
            raise gr.Error(
                f"File size exceeds file size limit. Got file of size {file_size_mb:.2f}MB for a limit of {FILE_LIMIT_MB}MB."
            )

        with open(inputs, "rb") as f:
            inputs = f.read()

        inputs = ffmpeg_read(inputs, pipeline.feature_extractor.sampling_rate)
        inputs = {"array": inputs, "sampling_rate": pipeline.feature_extractor.sampling_rate}
        logger.info("done loading")
        text, runtime = tqdm_generate(inputs, task=task, return_timestamps=return_timestamps, progress=progress)
        return text, runtime

    audio_chunked = gr.Interface(
        fn=transcribe_chunked_audio,
        inputs=[
            gr.inputs.Audio(source="upload", optional=True, label="Audio file", type="filepath"),
            gr.inputs.Radio(["transcribe", "translate"], label="Task", default="transcribe"),
            gr.inputs.Checkbox(default=False, label="Return timestamps"),
        ],
        outputs=[
            gr.outputs.Textbox(label="Transcription").style(show_copy_button=True),
            gr.outputs.Textbox(label="Transcription Time (s)"),
        ],
        allow_flagging="never",
        title=title,
        description=description,
        article=article,
    )

    demo = gr.Blocks()

    with demo:
        gr.TabbedInterface([audio_chunked], ["Audio File"])

    demo.queue(concurrency_count=1, max_size=5)
    if DEBUG:
        demo.launch(server_name="0.0.0.0", show_api=False, share=True,auth=authentication)
    else:
        demo.launch(server_name="0.0.0.0", show_api=False)
