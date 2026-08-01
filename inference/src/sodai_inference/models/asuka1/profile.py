from sodai_inference.artifacts import ArtifactProfile
from sodai_inference.tokenization import CHAT_SPECIAL_TOKENS

ASUKA1_PROFILE = ArtifactProfile(
    model="asuka-1",
    architecture="rope_gpt",
    runtime_abi="asuka1-rope-gpt-v1",
    context_length=512,
    dtype="float16",
    prompt_template="asuka1-dialogue-v1",
    vocab_size=32_000,
    special_tokens=CHAT_SPECIAL_TOKENS,
    source_model_version="v2",
    source_checkpoint_stage="sft",
)
