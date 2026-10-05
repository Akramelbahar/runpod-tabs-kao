# RunPod music and lyrics workers

This repository contains three queue-based RunPod Serverless workers. Create the
music and lyrics endpoints from the same GitHub repository and branch, using Dockerfile paths
`runpod/Dockerfile.music` and `runpod/Dockerfile.lyrics`, with the repository
root as build context. Both Dockerfiles have pinned build-argument defaults;
the full image and GPU inference still need to be tested on RunPod.

If a build fails at `RUN test -n "$RUNPOD_VERSION" ...`, inspect the Git commit
shown in its log. Commit `42fbbfd` had no build-argument defaults; later local
source fixes that. Push the updated source, then create a new GitHub release to
trigger a new RunPod GitHub build. A `git pull` on your PC does not update an
already-created RunPod endpoint. The log warning about Git not being available
in RunPod's build host is not the cause of this build failure.

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

## Local midi2frets checkpoint

The accepted midi2frets handoff ZIP is kept out of Git. The frets worker
requires a separate **private** container image built on the machine holding
the ZIP; selecting `runpod/Dockerfile.frets` in RunPod's GitHub builder will
fail because the ignored ZIP is absent from the GitHub checkout. The staging
script copies the ZIP to `runpod/vendor/` and verifies the checkpoint SHA256
before the local build. The Dockerfile runs the handoff's package verification
during the build.

From this repository's root in PowerShell, after installing Docker Desktop:

```powershell
.\runpod\stage-handoff.ps1
docker build --platform linux/amd64 -f runpod/Dockerfile.frets -t akram/idealchords-frets:accepted-core-52a178b6 .
docker login
docker push akram/idealchords-frets:accepted-core-52a178b6
```

The `akram` namespace must be a Docker Hub account you own; Docker Hub will
reject the push otherwise. Create the `idealchords-frets` repository as
**private** under that account before pushing. In RunPod,
add Docker Hub registry credentials, create a **Queue** Serverless endpoint by importing this
image from the Docker registry, select CPU compute if offered, set
`MIDI2FRETS_CPU_THREADS=4`, and use one maximum worker for the first test.
Keep the image tag immutable; record its digest. The ZIP is about 32 MB, but
the final image is much larger because it installs PyTorch.

The frets endpoint expects the same signed-URL envelope with `stage=frets` and
a strict guitar request JSON at `inputUrl`. It cannot be smoke-tested with a
plain prompt. The current app's MIDI import and frets dispatch are still an
integration step after music and lyrics inference, so a healthy endpoint alone
will not yet produce playable tabs in Studio.
