# RunPod music and lyrics workers

This repository contains two queue-based RunPod Serverless workers. Create two
endpoints from the same GitHub repository and branch, using Dockerfile paths
`runpod/Dockerfile.music` and `runpod/Dockerfile.lyrics`, with the repository
root as build context. Both Dockerfiles have pinned build-argument defaults;
the full image and GPU inference still need to be tested on RunPod.

The music endpoint requires `MUSCRIPTOR_MODEL=medium` and an `HF_TOKEN` that
can read the licensed MuScriptor checkpoint. MuScriptor weights require
Hugging Face access and are licensed CC BY-NC 4.0. Do not put tokens or model
weights in Git. The lyrics endpoint requires `WHISPERX_MODEL=small` for the
first smoke test, or another evaluated WhisperX checkpoint.

The lyrics worker runs Demucs `htdemucs` vocal separation on CUDA before
WhisperX transcription and word alignment. If Demucs fails, or the separated
stem yields no timed words, it retries the original mix. Its JSON result
records `audioSource`, `separationModel`, and `fallbackReason`. Setting
`LYRICS_USE_DEMUCS=0` bypasses separation for comparisons. The original
audio SHA remains the result's `sourceSha256`; word times remain on the
song's timeline. Demucs runs in a child process and the worker releases
cached ASR GPU memory before separating another song.

These workers require the versioned signed-URL job envelope sent by the
IdealChords app. RunPod's generic `{"input":{"prompt":"..."}}` test request
is not valid for them. The app-side coordinator and private artifact routes
must be deployed separately before an end-to-end audio test.

For offline checks, run `python -m unittest discover -s runpod -p 'test_*.py'`.
Then check each endpoint's Builds and Logs tabs and submit an owned test song
through the app. Start with zero active and one maximum worker per endpoint.
