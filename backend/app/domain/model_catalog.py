from dataclasses import dataclass
from enum import Enum


class ModelId(str, Enum):
    HINA = "hina"
    ASUKA_1 = "asuka-1"


class ModelAudience(str, Enum):
    GUEST = "guest"
    AUTHENTICATED = "authenticated"


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    id: ModelId
    name: str
    description: str
    runtime_target: str
    audiences: frozenset[ModelAudience]
    default_for: frozenset[ModelAudience] = frozenset()


@dataclass(frozen=True, slots=True)
class AvailableModel:
    id: ModelId
    name: str
    description: str
    is_default: bool


MODEL_CATALOG = (
    ModelDefinition(
        id=ModelId.ASUKA_1,
        name="Asuka 1",
        description="会話に最適。",
        runtime_target="pseudo:asuka-1",
        audiences=frozenset({ModelAudience.AUTHENTICATED}),
        default_for=frozenset({ModelAudience.AUTHENTICATED}),
    ),
    ModelDefinition(
        id=ModelId.HINA,
        name="Hina",
        description="知能の萌芽を捉える。",
        runtime_target="local:hina",
        audiences=frozenset(ModelAudience),
        default_for=frozenset({ModelAudience.GUEST}),
    ),
)
_MODEL_CATALOG_BY_ID = {model.id: model for model in MODEL_CATALOG}

if len(_MODEL_CATALOG_BY_ID) != len(MODEL_CATALOG):
    raise RuntimeError("Model catalog contains duplicate identifiers")

_DEFAULT_MODEL_BY_AUDIENCE: dict[ModelAudience, ModelDefinition] = {}
for audience in ModelAudience:
    defaults = [model for model in MODEL_CATALOG if audience in model.default_for]
    if len(defaults) != 1:
        raise RuntimeError(f"Model catalog must define one default for {audience.value}")
    if audience not in defaults[0].audiences:
        raise RuntimeError(f"Default model is not available to {audience.value}")
    _DEFAULT_MODEL_BY_AUDIENCE[audience] = defaults[0]


def get_model_definition(model_id: ModelId) -> ModelDefinition | None:
    return _MODEL_CATALOG_BY_ID.get(model_id)


def get_default_model(audience: ModelAudience) -> ModelDefinition:
    return _DEFAULT_MODEL_BY_AUDIENCE[audience]


def list_available_models(audience: ModelAudience) -> list[AvailableModel]:
    default = get_default_model(audience)
    return [
        AvailableModel(
            id=model.id,
            name=model.name,
            description=model.description,
            is_default=model.id is default.id,
        )
        for model in MODEL_CATALOG
        if audience in model.audiences
    ]
