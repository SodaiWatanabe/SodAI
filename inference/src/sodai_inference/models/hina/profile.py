from sodai_inference.artifacts import ArtifactProfile
from sodai_inference.tokenization import CHAT_SPECIAL_TOKENS

HINA_PROFILE = ArtifactProfile(
    model="hina",
    architecture="absolute_position_gpt",
    runtime_abi="hina-absolute-gpt-v1",
    context_length=512,
    dtype="float32",
    prompt_template="partner-self-v1",
    vocab_size=32_000,
    special_tokens=CHAT_SPECIAL_TOKENS,
    source_model_version="v1",
    source_checkpoint_stage="sft",
)
