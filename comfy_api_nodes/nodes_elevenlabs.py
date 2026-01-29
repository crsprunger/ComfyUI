import json
import uuid

from typing_extensions import override

from comfy_api.latest import IO, ComfyExtension, Input
from comfy_api_nodes.apis.elevenlabs import (
    AddVoiceRequest,
    AddVoiceResponse,
    ComposeMusicRequest,
    CreateCompositionPlanRequest,
    DialogueInput,
    DialogueSettings,
    MusicPrompt,
    MusicSection,
    SpeechToSpeechRequest,
    SpeechToTextRequest,
    SpeechToTextResponse,
    TextToDialogueRequest,
    TextToSoundEffectsRequest,
    TextToSpeechRequest,
    TextToSpeechVoiceSettings,
)
from comfy_api_nodes.util import (
    ApiEndpoint,
    audio_bytes_to_audio_input,
    audio_ndarray_to_bytesio,
    audio_tensor_to_contiguous_ndarray,
    sync_op,
    sync_op_raw,
    upload_audio_to_comfyapi,
    validate_string,
)

ELEVENLABS_MUSIC_SECTIONS = "ELEVENLABS_MUSIC_SECTIONS"  # Custom type for music sections
ELEVENLABS_COMPOSITION_PLAN = "ELEVENLABS_COMPOSITION_PLAN"  # Custom type for composition plan
ELEVENLABS_VOICE = "ELEVENLABS_VOICE"  # Custom type for voice selection

# Predefined ElevenLabs voices: (voice_id, display_name, gender, accent)
ELEVENLABS_VOICES = [
    ("CwhRBWXzGAHq8TQ4Fs17", "Roger", "male", "american"),
    ("EXAVITQu4vr4xnSDxMaL", "Sarah", "female", "american"),
    ("FGY2WhTYpPnrIDTdsKH5", "Laura", "female", "american"),
    ("IKne3meq5aSn9XLyUdCD", "Charlie", "male", "australian"),
    ("JBFqnCBsd6RMkjVDRZzb", "George", "male", "british"),
    ("N2lVS1w4EtoT3dr4eOWO", "Callum", "male", "american"),
    ("SAz9YHcvj6GT2YYXdXww", "River", "neutral", "american"),
    ("SOYHLrjzK2X1ezoPC6cr", "Harry", "male", "american"),
    ("TX3LPaxmHKxFdv7VOQHJ", "Liam", "male", "american"),
    ("Xb7hH8MSUJpSbSDYk0k2", "Alice", "female", "british"),
    ("XrExE9yKIg1WjnnlVkGX", "Matilda", "female", "american"),
    ("bIHbv24MWmeRgasZH58o", "Will", "male", "american"),
    ("cgSgspJ2msm6clMCkdW9", "Jessica", "female", "american"),
    ("cjVigY5qzO86Huf0OWal", "Eric", "male", "american"),
    ("hpp4J3VqNfWAUOO0d1Us", "Bella", "female", "american"),
    ("iP95p4xoKVk53GoZ742B", "Chris", "male", "american"),
    ("nPczCjzI2devNBz1zQrb", "Brian", "male", "american"),
    ("onwK4e9ZLuTAKqWW03F9", "Daniel", "male", "british"),
    ("pFZP5JQG7iQjIQuC4Bku", "Lily", "female", "british"),
    ("pNInz6obpgDQGcFmaJgB", "Adam", "male", "american"),
    ("pqHfZKP75CvOlQylNhV4", "Bill", "male", "american"),
]

ELEVENLABS_VOICE_OPTIONS = [f"{name} ({gender}, {accent})" for _, name, gender, accent in ELEVENLABS_VOICES]
ELEVENLABS_VOICE_MAP = {
    f"{name} ({gender}, {accent})": voice_id for voice_id, name, gender, accent in ELEVENLABS_VOICES
}


def parse_multiline_to_list(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


class ElevenLabsComposeMusicSection(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsComposeMusicSection",
            display_name="ElevenLabs Compose Music Section",
            category="api node/audio/ElevenLabs",
            description="Define a section for structured music composition.",
            inputs=[
                IO.String.Input(
                    "section_name",
                    default="Verse",
                    tooltip="Name of this section (1-100 characters). "
                    "E.g., 'Intro', 'Verse', 'Chorus', 'Bridge', 'Outro'.",
                ),
                IO.String.Input(
                    "positive_local_styles",
                    default="",
                    multiline=True,
                    tooltip="Styles for this section (one per line). E.g., 'energetic', 'upbeat', 'guitar-driven'.",
                ),
                IO.String.Input(
                    "negative_local_styles",
                    default="",
                    multiline=True,
                    tooltip="Styles to avoid in this section (one per line). E.g., 'slow', 'acoustic'.",
                ),
                IO.Float.Input(
                    "duration",
                    default=30,
                    min=3,
                    max=120,
                    step=0.01,
                    display_mode=IO.NumberDisplay.number,
                    tooltip="Duration of this section in seconds.",
                ),
                IO.String.Input(
                    "content",
                    default="",
                    multiline=True,
                    tooltip="Lyrics for this section (one line per lyric line, max 200 characters per line).",
                ),
            ],
            outputs=[
                IO.Custom(ELEVENLABS_MUSIC_SECTIONS).Output(display_name="section"),
            ],
            is_api_node=False,
        )

    @classmethod
    def execute(
        cls,
        section_name: str,
        positive_local_styles: str,
        negative_local_styles: str,
        duration: float,
        content: str,
    ) -> IO.NodeOutput:
        validate_string(section_name, min_length=1, max_length=100)
        lines = parse_multiline_to_list(content)
        for i, line in enumerate(lines, 1):
            if len(line) > 200:
                raise ValueError(f"Line {i} exceeds 200 characters (has {len(line)}).")
        section = {
            "section_name": section_name,
            "positive_local_styles": parse_multiline_to_list(positive_local_styles),
            "negative_local_styles": parse_multiline_to_list(negative_local_styles),
            "duration_ms": int(duration * 1000),
            "lines": lines,
        }
        return IO.NodeOutput(json.dumps(section))


class ElevenLabsCreateCompositionPlan(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsCreateCompositionPlan",
            display_name="ElevenLabs Create Composition Plan",
            category="api node/audio/ElevenLabs",
            description="Generate a composition plan from lyrics. "
            "Connect output to a 'Preview as Text' node to view the plan, then copy values to Section nodes.",
            inputs=[
                IO.String.Input(
                    "prompt",
                    default="",
                    multiline=True,
                    tooltip="Lyrics or description to generate a composition plan from.",
                ),
                IO.Float.Input(
                    "duration",
                    default=60,
                    min=3,
                    max=600,
                    step=0.1,
                    display_mode=IO.NumberDisplay.number,
                ),
                IO.DynamicCombo.Input(
                    "model",
                    options=[
                        IO.DynamicCombo.Option("music_v1", []),
                    ],
                    tooltip="Model to use for plan generation.",
                ),
            ],
            outputs=[
                IO.String.Output(display_name="composition_plan"),
                IO.Custom(ELEVENLABS_COMPOSITION_PLAN).Output(display_name="plan_data"),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
        )

    @classmethod
    async def execute(
        cls,
        prompt: str,
        duration: float,
        model: dict,
    ) -> IO.NodeOutput:
        validate_string(prompt, min_length=1)
        request = CreateCompositionPlanRequest(
            prompt=prompt,
            music_length_ms=int(duration * 1000) if duration else None,
            model_id=model["model"],
        )
        response = await sync_op(
            cls,
            ApiEndpoint(path="/proxy/elevenlabs/v1/music/plan", method="POST"),
            response_model=MusicPrompt,
            data=request,
        )
        output_lines = [
            "=== COMPOSITION PLAN ===",
            "",
            "--- GLOBAL STYLES ---",
            "Positive (copy to positive_global_styles):",
            "\n".join(response.positive_global_styles) if response.positive_global_styles else "(none)",
            "",
            "Negative (copy to negative_global_styles):",
            "\n".join(response.negative_global_styles) if response.negative_global_styles else "(none)",
            "",
            "--- SECTIONS ---",
        ]
        for i, section in enumerate(response.sections, 1):
            output_lines.extend(
                [
                    "",
                    f"=== Section {i}: {section.section_name} ===",
                    f"section_name: {section.section_name}",
                    f"duration: {section.duration_ms / 1000:.2f} seconds",
                    "",
                    "positive_local_styles:",
                    "\n".join(section.positive_local_styles) if section.positive_local_styles else "(none)",
                    "",
                    "negative_local_styles:",
                    "\n".join(section.negative_local_styles) if section.negative_local_styles else "(none)",
                    "",
                    "content (lyrics):",
                    "\n".join(section.lines) if section.lines else "(instrumental)",
                ]
            )
        return IO.NodeOutput("\n".join(output_lines), response.model_dump_json())


class ElevenLabsComposeMusic(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsComposeMusic",
            display_name="ElevenLabs Compose Music",
            category="api node/audio/ElevenLabs",
            description="Generate music. Use a simple text prompt or a detailed composition plan with sections.",
            inputs=[
                IO.DynamicCombo.Input(
                    "model",
                    options=[
                        IO.DynamicCombo.Option(
                            "music_v1",
                            [],
                        ),
                    ],
                    tooltip="Model to use for music generation.",
                ),
                IO.DynamicCombo.Input(
                    "content",
                    options=[
                        IO.DynamicCombo.Option(
                            "prompt",
                            [
                                IO.String.Input(
                                    "prompt",
                                    default="",
                                    multiline=True,
                                    tooltip="A simple text prompt to generate a song from (max 4100 characters).",
                                ),
                                IO.Float.Input(
                                    "duration",
                                    default=60,
                                    min=3,
                                    max=600,
                                    step=0.1,
                                    display_mode=IO.NumberDisplay.number,
                                ),
                                IO.Boolean.Input(
                                    "force_instrumental",
                                    default=False,
                                    tooltip="If true, guarantees the generated song will be instrumental.",
                                ),
                            ],
                        ),
                        IO.DynamicCombo.Option(
                            "composition_plan",
                            [
                                IO.String.Input(
                                    "positive_global_styles",
                                    default="",
                                    multiline=True,
                                    tooltip="Global styles for the entire song (one per line). "
                                    "E.g., 'pop', 'electronic', 'uplifting'.",
                                ),
                                IO.String.Input(
                                    "negative_global_styles",
                                    default="",
                                    multiline=True,
                                    tooltip="Styles to avoid in the entire song (one per line). "
                                    "E.g., 'metal', 'aggressive'.",
                                ),
                                IO.Boolean.Input(
                                    "respect_sections_durations",
                                    default=True,
                                    tooltip="When true, strictly enforces each section's duration. "
                                    "When false, may adjust for better quality.",
                                ),
                                IO.Autogrow.Input(
                                    "sections",
                                    template=IO.Autogrow.TemplatePrefix(
                                        IO.Custom(ELEVENLABS_MUSIC_SECTIONS).Input("sections"),
                                        prefix="section",
                                        min=1,
                                        max=30,
                                    ),
                                ),
                            ],
                        ),
                        IO.DynamicCombo.Option(
                            "from_plan",
                            [
                                IO.Custom(ELEVENLABS_COMPOSITION_PLAN).Input(
                                    "plan_data",
                                    tooltip="Connect the plan_data output from ElevenLabsCreateCompositionPlan node.",
                                ),
                                IO.Boolean.Input(
                                    "respect_sections_durations",
                                    default=True,
                                    tooltip="When true, strictly enforces each section's duration. "
                                    "When false, may adjust for better quality.",
                                ),
                            ],
                        ),
                    ],
                    tooltip="Choose between a simple text prompt, a structured composition plan, "
                    "or connect directly from ElevenLabsCreateCompositionPlan.",
                ),
                IO.Combo.Input(
                    "output_format",
                    options=["mp3_44100_192", "opus_48000_192"],
                ),
            ],
            outputs=[
                IO.Audio.Output(),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        model: dict,
        content: dict,
        output_format: str,
    ) -> IO.NodeOutput:
        if content["content"] == "prompt":
            validate_string(content["prompt"], min_length=1, max_length=4100)
            request = ComposeMusicRequest(
                model_id=model["model"],
                prompt=content["prompt"],
                music_length_ms=content["duration"] * 1000,
                force_instrumental=content["force_instrumental"],
                output_format=output_format,
                respect_sections_durations=None,
                composition_plan=None,
            )
        elif content["content"] == "from_plan":
            composition_plan = MusicPrompt.model_validate_json(content["plan_data"])
            request = ComposeMusicRequest(
                model_id=model["model"],
                composition_plan=composition_plan,
                respect_sections_durations=content["respect_sections_durations"],
                output_format=output_format,
                prompt=None,
                music_length_ms=None,
                force_instrumental=None,
            )
        else:  # composition_plan
            sections_autogrow = content["sections"]
            sections: list[MusicSection] = []
            for key in sections_autogrow:
                section_json = sections_autogrow[key]
                s = json.loads(section_json)
                sections.append(
                    MusicSection(
                        section_name=s["section_name"],
                        positive_local_styles=s["positive_local_styles"],
                        negative_local_styles=s["negative_local_styles"],
                        duration_ms=s["duration_ms"],
                        lines=s["lines"],
                    )
                )
            if not sections:
                raise ValueError("At least one section is required for composition_plan.")
            request = ComposeMusicRequest(
                model_id=model["model"],
                composition_plan=MusicPrompt(
                    positive_global_styles=parse_multiline_to_list(content["positive_global_styles"]),
                    negative_global_styles=parse_multiline_to_list(content["negative_global_styles"]),
                    sections=sections,
                ),
                respect_sections_durations=content["respect_sections_durations"],
                output_format=output_format,
                prompt=None,
                music_length_ms=None,
                force_instrumental=None,
            )
        response = await sync_op_raw(
            cls,
            ApiEndpoint(path="/proxy/elevenlabs/v1/music", method="POST"),
            data=request,
            as_binary=True,
        )
        return IO.NodeOutput(audio_bytes_to_audio_input(response))


class ElevenLabsSpeechToText(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsSpeechToText",
            display_name="ElevenLabs Speech to Text",
            category="api node/audio/ElevenLabs",
            description="Transcribe audio to text. "
            "Supports automatic language detection, speaker diarization, and audio event tagging.",
            inputs=[
                IO.Audio.Input(
                    "audio",
                    tooltip="Audio to transcribe.",
                ),
                IO.DynamicCombo.Input(
                    "model",
                    options=[
                        IO.DynamicCombo.Option(
                            "scribe_v2",
                            [
                                IO.Boolean.Input(
                                    "tag_audio_events",
                                    default=False,
                                    tooltip="Annotate sounds like (laughter), (music), etc. in transcript.",
                                ),
                                IO.Boolean.Input(
                                    "diarize",
                                    default=False,
                                    tooltip="Annotate which speaker is talking.",
                                ),
                                IO.Float.Input(
                                    "diarization_threshold",
                                    default=0.22,
                                    min=0.1,
                                    max=0.4,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Speaker separation sensitivity. "
                                    "Lower values are more sensitive to speaker changes.",
                                ),
                                IO.Float.Input(
                                    "temperature",
                                    default=0.0,
                                    min=0.0,
                                    max=2.0,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Randomness control. "
                                    "0.0 uses model default. Higher values increase randomness.",
                                ),
                                IO.Combo.Input(
                                    "timestamps_granularity",
                                    options=["word", "character", "none"],
                                    default="word",
                                    tooltip="Timing precision for transcript words.",
                                ),
                            ],
                        ),
                    ],
                    tooltip="Model to use for transcription.",
                ),
                IO.String.Input(
                    "language_code",
                    default="",
                    tooltip="ISO-639-1 or ISO-639-3 language code (e.g., 'en', 'es', 'fra'). "
                    "Leave empty for automatic detection.",
                ),
                IO.Int.Input(
                    "num_speakers",
                    default=0,
                    min=0,
                    max=32,
                    display_mode=IO.NumberDisplay.slider,
                    tooltip="Maximum number of speakers to predict. Set to 0 for automatic detection.",
                ),
                IO.Int.Input(
                    "seed",
                    default=1,
                    min=0,
                    max=2147483647,
                    tooltip="Seed for reproducibility (determinism not guaranteed).",
                ),
            ],
            outputs=[
                IO.String.Output(display_name="text"),
                IO.String.Output(display_name="language_code"),
                IO.String.Output(display_name="words_json"),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        audio: Input.Audio,
        model: dict,
        language_code: str,
        num_speakers: int,
        seed: int,
    ) -> IO.NodeOutput:
        if model["diarize"] and num_speakers:
            raise ValueError(
                "Number of speakers cannot be specified when diarization is enabled. "
                "Either disable diarization or set num_speakers to 0."
            )
        request = SpeechToTextRequest(
            model_id=model["model"],
            cloud_storage_url=await upload_audio_to_comfyapi(
                cls, audio, container_format="mp4", codec_name="aac", mime_type="audio/mp4"
            ),
            language_code=language_code if language_code.strip() else None,
            tag_audio_events=model["tag_audio_events"],
            num_speakers=num_speakers if num_speakers > 0 else None,
            timestamps_granularity=model["timestamps_granularity"],
            diarize=model["diarize"],
            diarization_threshold=model["diarization_threshold"] if model["diarize"] else None,
            seed=seed,
            temperature=model["temperature"],
        )
        response = await sync_op(
            cls,
            ApiEndpoint(path="/proxy/elevenlabs/v1/speech-to-text", method="POST"),
            response_model=SpeechToTextResponse,
            data=request,
            content_type="multipart/form-data",
        )
        words_json = json.dumps(
            [w.model_dump(exclude_none=True) for w in response.words] if response.words else [],
            indent=2,
        )
        return IO.NodeOutput(response.text, response.language_code, words_json)


class ElevenLabsVoiceSelector(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsVoiceSelector",
            display_name="ElevenLabs Voice Selector",
            category="api node/audio/ElevenLabs",
            description="Select a predefined ElevenLabs voice for text-to-speech generation.",
            inputs=[
                IO.Combo.Input(
                    "voice",
                    options=ELEVENLABS_VOICE_OPTIONS,
                    tooltip="Choose a voice from the predefined ElevenLabs voices.",
                ),
            ],
            outputs=[
                IO.Custom(ELEVENLABS_VOICE).Output(display_name="voice"),
            ],
            is_api_node=False,
        )

    @classmethod
    def execute(cls, voice: str) -> IO.NodeOutput:
        voice_id = ELEVENLABS_VOICE_MAP.get(voice)
        if not voice_id:
            raise ValueError(f"Unknown voice: {voice}")
        return IO.NodeOutput(voice_id)


class ElevenLabsTextToSpeech(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsTextToSpeech",
            display_name="ElevenLabs Text to Speech",
            category="api node/audio/ElevenLabs",
            description="Convert text to speech.",
            inputs=[
                IO.Custom(ELEVENLABS_VOICE).Input(
                    "voice",
                    tooltip="Voice to use for speech synthesis. Connect from Voice Selector or Instant Voice Clone.",
                ),
                IO.String.Input(
                    "text",
                    multiline=True,
                    default="",
                    tooltip="The text to convert to speech.",
                ),
                IO.Float.Input(
                    "stability",
                    default=0.5,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    display_mode=IO.NumberDisplay.slider,
                    tooltip="Voice stability. Lower values give broader emotional range, "
                    "higher values produce more consistent but potentially monotonous speech.",
                ),
                IO.Combo.Input(
                    "apply_text_normalization",
                    options=["auto", "on", "off"],
                    tooltip="Text normalization mode. 'auto' lets the system decide, "
                    "'on' always applies normalization, 'off' skips it.",
                ),
                IO.DynamicCombo.Input(
                    "model",
                    options=[
                        IO.DynamicCombo.Option(
                            "eleven_multilingual_v2",
                            [
                                IO.Float.Input(
                                    "speed",
                                    default=1.0,
                                    min=0.7,
                                    max=1.3,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Speech speed. 1.0 is normal, <1.0 slower, >1.0 faster.",
                                ),
                                IO.Float.Input(
                                    "similarity_boost",
                                    default=0.75,
                                    min=0.0,
                                    max=1.0,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Similarity boost. Higher values make the voice more similar to the original.",
                                ),
                                IO.Boolean.Input(
                                    "use_speaker_boost",
                                    default=False,
                                    tooltip="Boost similarity to the original speaker voice.",
                                ),
                                IO.Float.Input(
                                    "style",
                                    default=0.0,
                                    min=0.0,
                                    max=0.2,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Style exaggeration. Higher values increase stylistic expression "
                                    "but may reduce stability.",
                                ),
                            ],
                        ),
                        IO.DynamicCombo.Option(
                            "eleven_v3",
                            [
                                IO.Float.Input(
                                    "speed",
                                    default=1.0,
                                    min=0.7,
                                    max=1.3,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Speech speed. 1.0 is normal, <1.0 slower, >1.0 faster.",
                                ),
                                IO.Float.Input(
                                    "similarity_boost",
                                    default=0.75,
                                    min=0.0,
                                    max=1.0,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Similarity boost. Higher values make the voice more similar to the original.",
                                ),
                            ],
                        ),
                    ],
                    tooltip="Model to use for text-to-speech.",
                ),
                IO.String.Input(
                    "language_code",
                    default="",
                    tooltip="ISO-639-1 or ISO-639-3 language code (e.g., 'en', 'es', 'fra'). "
                    "Leave empty for automatic detection.",
                ),
                IO.Int.Input(
                    "seed",
                    default=1,
                    min=0,
                    max=2147483647,
                    tooltip="Seed for reproducibility (determinism not guaranteed).",
                ),
                IO.Combo.Input(
                    "output_format",
                    options=["mp3_44100_192", "opus_48000_192"],
                    tooltip="Audio output format.",
                ),
            ],
            outputs=[
                IO.Audio.Output(),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        voice: str,
        text: str,
        stability: float,
        apply_text_normalization: str,
        model: dict,
        language_code: str,
        seed: int,
        output_format: str,
    ) -> IO.NodeOutput:
        validate_string(text, min_length=1)
        request = TextToSpeechRequest(
            text=text,
            model_id=model["model"],
            language_code=language_code if language_code.strip() else None,
            voice_settings=TextToSpeechVoiceSettings(
                stability=stability,
                similarity_boost=model["similarity_boost"],
                speed=model["speed"],
                use_speaker_boost=model.get("use_speaker_boost", None),
                style=model.get("style", None),
            ),
            seed=seed,
            apply_text_normalization=apply_text_normalization,
        )
        response = await sync_op_raw(
            cls,
            ApiEndpoint(
                path=f"/proxy/elevenlabs/v1/text-to-speech/{voice}",
                method="POST",
                query_params={"output_format": output_format},
            ),
            data=request,
            as_binary=True,
        )
        return IO.NodeOutput(audio_bytes_to_audio_input(response))


class ElevenLabsAudioIsolation(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsAudioIsolation",
            display_name="ElevenLabs Voice Isolation",
            category="api node/audio/ElevenLabs",
            description="Remove background noise from audio, isolating vocals or speech.",
            inputs=[
                IO.Audio.Input(
                    "audio",
                    tooltip="Audio to process for background noise removal.",
                ),
            ],
            outputs=[
                IO.Audio.Output(),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        audio: Input.Audio,
    ) -> IO.NodeOutput:
        audio_data_np = audio_tensor_to_contiguous_ndarray(audio["waveform"])
        audio_bytes_io = audio_ndarray_to_bytesio(audio_data_np, audio["sample_rate"], "mp4", "aac")
        response = await sync_op_raw(
            cls,
            ApiEndpoint(path="/proxy/elevenlabs/v1/audio-isolation", method="POST"),
            files={"audio": ("audio.mp4", audio_bytes_io, "audio/mp4")},
            content_type="multipart/form-data",
            as_binary=True,
        )
        return IO.NodeOutput(audio_bytes_to_audio_input(response))


class ElevenLabsTextToSoundEffects(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsTextToSoundEffects",
            display_name="ElevenLabs Text to Sound Effects",
            category="api node/audio/ElevenLabs",
            description="Generate sound effects from text descriptions.",
            inputs=[
                IO.String.Input(
                    "text",
                    multiline=True,
                    default="",
                    tooltip="Text description of the sound effect to generate.",
                ),
                IO.DynamicCombo.Input(
                    "model",
                    options=[
                        IO.DynamicCombo.Option(
                            "eleven_sfx_v2",
                            [
                                IO.Float.Input(
                                    "duration",
                                    default=5.0,
                                    min=0.5,
                                    max=30.0,
                                    step=0.1,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="Duration of generated sound in seconds.",
                                ),
                                IO.Boolean.Input(
                                    "loop",
                                    default=False,
                                    tooltip="Create a smoothly looping sound effect.",
                                ),
                                IO.Float.Input(
                                    "prompt_influence",
                                    default=0.3,
                                    min=0.0,
                                    max=1.0,
                                    step=0.01,
                                    display_mode=IO.NumberDisplay.slider,
                                    tooltip="How closely generation follows the prompt. "
                                    "Higher values make the sound follow the text more closely.",
                                ),
                            ],
                        ),
                    ],
                    tooltip="Model to use for sound effect generation.",
                ),
                IO.Combo.Input(
                    "output_format",
                    options=["mp3_44100_192", "opus_48000_192"],
                    tooltip="Audio output format.",
                ),
            ],
            outputs=[
                IO.Audio.Output(),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        text: str,
        model: dict,
        output_format: str,
    ) -> IO.NodeOutput:
        validate_string(text, min_length=1)
        response = await sync_op_raw(
            cls,
            ApiEndpoint(
                path="/proxy/elevenlabs/v1/sound-generation",
                method="POST",
                query_params={"output_format": output_format},
            ),
            data=TextToSoundEffectsRequest(
                text=text,
                duration_seconds=model["duration"],
                prompt_influence=model["prompt_influence"],
                loop=model.get("loop", None),
            ),
            as_binary=True,
        )
        return IO.NodeOutput(audio_bytes_to_audio_input(response))


class ElevenLabsInstantVoiceClone(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsInstantVoiceClone",
            display_name="ElevenLabs Instant Voice Clone",
            category="api node/audio/ElevenLabs",
            description="Create a cloned voice from audio samples. "
            "Provide 1-8 audio recordings of the voice to clone.",
            inputs=[
                IO.Autogrow.Input(
                    "files",
                    template=IO.Autogrow.TemplatePrefix(
                        IO.Audio.Input("audio"),
                        prefix="audio",
                        min=1,
                        max=8,
                    ),
                    tooltip="Audio recordings for voice cloning.",
                ),
                IO.Boolean.Input(
                    "remove_background_noise",
                    default=False,
                    tooltip="Remove background noise from voice samples using audio isolation.",
                ),
            ],
            outputs=[
                IO.Custom(ELEVENLABS_VOICE).Output(display_name="voice"),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        files: IO.Autogrow.Type,
        remove_background_noise: bool,
    ) -> IO.NodeOutput:
        file_tuples: list[tuple[str, tuple[str, bytes, str]]] = []
        for key in files:
            audio = files[key]
            sample_rate: int = audio["sample_rate"]
            waveform = audio["waveform"]
            audio_data_np = audio_tensor_to_contiguous_ndarray(waveform)
            audio_bytes_io = audio_ndarray_to_bytesio(audio_data_np, sample_rate, "mp4", "aac")
            file_tuples.append(("files", (f"{key}.mp4", audio_bytes_io.getvalue(), "audio/mp4")))

        response = await sync_op(
            cls,
            ApiEndpoint(path="/proxy/elevenlabs/v1/voices/add", method="POST"),
            response_model=AddVoiceResponse,
            data=AddVoiceRequest(
                name=str(uuid.uuid4()),
                remove_background_noise=remove_background_noise,
            ),
            files=file_tuples,
            content_type="multipart/form-data",
        )
        return IO.NodeOutput(response.voice_id)


ELEVENLABS_STS_VOICE_SETTINGS = [
    IO.Float.Input(
        "speed",
        default=1.0,
        min=0.7,
        max=1.3,
        step=0.01,
        display_mode=IO.NumberDisplay.slider,
        tooltip="Speech speed. 1.0 is normal, <1.0 slower, >1.0 faster.",
    ),
    IO.Float.Input(
        "similarity_boost",
        default=0.75,
        min=0.0,
        max=1.0,
        step=0.01,
        display_mode=IO.NumberDisplay.slider,
        tooltip="Similarity boost. Higher values make the voice more similar to the original.",
    ),
    IO.Boolean.Input(
        "use_speaker_boost",
        default=False,
        tooltip="Boost similarity to the original speaker voice.",
    ),
    IO.Float.Input(
        "style",
        default=0.0,
        min=0.0,
        max=0.2,
        step=0.01,
        display_mode=IO.NumberDisplay.slider,
        tooltip="Style exaggeration. Higher values increase stylistic expression but may reduce stability.",
    ),
]


class ElevenLabsSpeechToSpeech(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsSpeechToSpeech",
            display_name="ElevenLabs Speech to Speech",
            category="api node/audio/ElevenLabs",
            description="Transform speech from one voice to another while preserving the original content and emotion.",
            inputs=[
                IO.Custom(ELEVENLABS_VOICE).Input(
                    "voice",
                    tooltip="Target voice for the transformation. "
                    "Connect from Voice Selector or Instant Voice Clone.",
                ),
                IO.Audio.Input(
                    "audio",
                    tooltip="Source audio to transform.",
                ),
                IO.Float.Input(
                    "stability",
                    default=0.5,
                    min=0.0,
                    max=1.0,
                    step=0.01,
                    display_mode=IO.NumberDisplay.slider,
                    tooltip="Voice stability. Lower values give broader emotional range, "
                    "higher values produce more consistent but potentially monotonous speech.",
                ),
                IO.DynamicCombo.Input(
                    "model",
                    options=[
                        IO.DynamicCombo.Option(
                            "eleven_multilingual_sts_v2",
                            ELEVENLABS_STS_VOICE_SETTINGS,
                        ),
                        IO.DynamicCombo.Option(
                            "eleven_english_sts_v2",
                            ELEVENLABS_STS_VOICE_SETTINGS,
                        ),
                    ],
                    tooltip="Model to use for speech-to-speech transformation.",
                ),
                IO.Combo.Input(
                    "output_format",
                    options=["mp3_44100_192", "opus_48000_192"],
                    tooltip="Audio output format.",
                ),
                IO.Int.Input(
                    "seed",
                    default=0,
                    min=0,
                    max=4294967295,
                    tooltip="Seed for reproducibility.",
                ),
                IO.Boolean.Input(
                    "remove_background_noise",
                    default=False,
                    tooltip="Remove background noise from input audio using audio isolation.",
                ),
            ],
            outputs=[
                IO.Audio.Output(),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        voice: str,
        audio: Input.Audio,
        stability: float,
        model: dict,
        output_format: str,
        seed: int,
        remove_background_noise: bool,
    ) -> IO.NodeOutput:
        audio_data_np = audio_tensor_to_contiguous_ndarray(audio["waveform"])
        audio_bytes_io = audio_ndarray_to_bytesio(audio_data_np, audio["sample_rate"], "mp4", "aac")
        voice_settings = TextToSpeechVoiceSettings(
            stability=stability,
            similarity_boost=model["similarity_boost"],
            style=model["style"],
            use_speaker_boost=model["use_speaker_boost"],
            speed=model["speed"],
        )
        response = await sync_op_raw(
            cls,
            ApiEndpoint(
                path=f"/proxy/elevenlabs/v1/speech-to-speech/{voice}",
                method="POST",
                query_params={"output_format": output_format},
            ),
            data=SpeechToSpeechRequest(
                model_id=model["model"],
                voice_settings=voice_settings.model_dump_json(exclude_none=True),
                seed=seed,
                remove_background_noise=remove_background_noise,
            ),
            files={"audio": ("audio.mp4", audio_bytes_io.getvalue(), "audio/mp4")},
            content_type="multipart/form-data",
            as_binary=True,
        )
        return IO.NodeOutput(audio_bytes_to_audio_input(response))


def _generate_dialogue_inputs(count: int) -> list:
    """Generate input widgets for a given number of dialogue entries."""
    inputs = []
    for i in range(1, count + 1):
        inputs.extend(
            [
                IO.String.Input(
                    f"text{i}",
                    multiline=True,
                    default="",
                    tooltip=f"Text content for dialogue entry {i}.",
                ),
                IO.Custom(ELEVENLABS_VOICE).Input(
                    f"voice{i}",
                    tooltip=f"Voice for dialogue entry {i}. Connect from Voice Selector or Instant Voice Clone.",
                ),
            ]
        )
    return inputs


class ElevenLabsTextToDialogue(IO.ComfyNode):
    @classmethod
    def define_schema(cls) -> IO.Schema:
        return IO.Schema(
            node_id="ElevenLabsTextToDialogue",
            display_name="ElevenLabs Text to Dialogue",
            category="api node/audio/ElevenLabs",
            description="Generate multi-speaker dialogue from text. Each dialogue entry has its own text and voice.",
            inputs=[
                IO.Float.Input(
                    "stability",
                    default=0.5,
                    min=0.0,
                    max=1.0,
                    step=0.5,
                    display_mode=IO.NumberDisplay.slider,
                    tooltip="Voice stability. Lower values give broader emotional range, "
                    "higher values produce more consistent but potentially monotonous speech.",
                ),
                IO.Combo.Input(
                    "apply_text_normalization",
                    options=["auto", "on", "off"],
                    tooltip="Text normalization mode. 'auto' lets the system decide, "
                    "'on' always applies normalization, 'off' skips it.",
                ),
                IO.Combo.Input(
                    "model",
                    options=["eleven_v3"],
                    tooltip="Model to use for dialogue generation.",
                ),
                IO.DynamicCombo.Input(
                    "inputs",
                    options=[
                        IO.DynamicCombo.Option("1", _generate_dialogue_inputs(1)),
                        IO.DynamicCombo.Option("2", _generate_dialogue_inputs(2)),
                        IO.DynamicCombo.Option("3", _generate_dialogue_inputs(3)),
                        IO.DynamicCombo.Option("4", _generate_dialogue_inputs(4)),
                        IO.DynamicCombo.Option("5", _generate_dialogue_inputs(5)),
                        IO.DynamicCombo.Option("6", _generate_dialogue_inputs(6)),
                        IO.DynamicCombo.Option("7", _generate_dialogue_inputs(7)),
                        IO.DynamicCombo.Option("8", _generate_dialogue_inputs(8)),
                        IO.DynamicCombo.Option("9", _generate_dialogue_inputs(9)),
                        IO.DynamicCombo.Option("10", _generate_dialogue_inputs(10)),
                    ],
                    tooltip="Number of dialogue entries.",
                ),
                IO.String.Input(
                    "language_code",
                    default="",
                    tooltip="ISO-639-1 or ISO-639-3 language code (e.g., 'en', 'es', 'fra'). "
                    "Leave empty for automatic detection.",
                ),
                IO.Int.Input(
                    "seed",
                    default=1,
                    min=0,
                    max=4294967295,
                    tooltip="Seed for reproducibility.",
                ),
                IO.Combo.Input(
                    "output_format",
                    options=["mp3_44100_192", "opus_48000_192"],
                    tooltip="Audio output format.",
                ),
            ],
            outputs=[
                IO.Audio.Output(),
            ],
            hidden=[
                IO.Hidden.auth_token_comfy_org,
                IO.Hidden.api_key_comfy_org,
                IO.Hidden.unique_id,
            ],
            is_api_node=True,
        )

    @classmethod
    async def execute(
        cls,
        stability: float,
        apply_text_normalization: str,
        model: str,
        inputs: dict,
        language_code: str,
        seed: int,
        output_format: str,
    ) -> IO.NodeOutput:
        num_entries = int(inputs["inputs"])
        dialogue_inputs: list[DialogueInput] = []
        for i in range(1, num_entries + 1):
            text = inputs[f"text{i}"]
            voice_id = inputs[f"voice{i}"]
            validate_string(text, min_length=1)
            dialogue_inputs.append(DialogueInput(text=text, voice_id=voice_id))
        request = TextToDialogueRequest(
            inputs=dialogue_inputs,
            model_id=model,
            language_code=language_code if language_code.strip() else None,
            settings=DialogueSettings(stability=stability),
            seed=seed,
            apply_text_normalization=apply_text_normalization,
        )
        response = await sync_op_raw(
            cls,
            ApiEndpoint(
                path="/proxy/elevenlabs/v1/text-to-dialogue",
                method="POST",
                query_params={"output_format": output_format},
            ),
            data=request,
            as_binary=True,
        )
        return IO.NodeOutput(audio_bytes_to_audio_input(response))


class ElevenLabsExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[IO.ComfyNode]]:
        return [
            # ElevenLabsComposeMusicSection,
            # ElevenLabsCreateCompositionPlan,
            # ElevenLabsComposeMusic,
            ElevenLabsSpeechToText,
            ElevenLabsVoiceSelector,
            ElevenLabsTextToSpeech,
            ElevenLabsAudioIsolation,
            ElevenLabsTextToSoundEffects,
            ElevenLabsInstantVoiceClone,
            ElevenLabsSpeechToSpeech,
            ElevenLabsTextToDialogue,
        ]


async def comfy_entrypoint() -> ElevenLabsExtension:
    return ElevenLabsExtension()
