"""Typed configuration entities for the generator."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_SYSTEM_TEMPLATE = """You generate dataset text candidates.
Follow the user request exactly. Return only the requested output format."""


DEFAULT_USER_TEMPLATE = """Generate {batch_size} unique text candidates for rule "{rule_id}".

Goal:
{goal}

Positive examples:
{positive_examples}

Negative examples:
{negative_examples}

Checks that every accepted candidate must pass:
{checks}

Diversity context for this request:
{diversity}

{output_contract}"""


DEFAULT_OUTPUT_CONTRACT_TEMPLATE = """Return only a valid JSON array of strings.
Do not wrap it in markdown. Do not add comments or explanations."""


@dataclass
class RunConfig:
    """Execution-level settings that are independent from individual rules."""

    name: str
    random_seed: int = 42
    resume: bool = True
    prompts_per_cycle: int = 4
    max_requests_per_rule: int = 10000
    max_consecutive_empty_cycles: int = 50

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunConfig":
        """Create run settings from a plain dictionary."""
        return cls(
            name=str(data["name"]),
            random_seed=int(data.get("random_seed", 42)),
            resume=bool(data.get("resume", True)),
            prompts_per_cycle=int(data.get("prompts_per_cycle", 4)),
            max_requests_per_rule=int(data.get("max_requests_per_rule", 10000)),
            max_consecutive_empty_cycles=int(data.get("max_consecutive_empty_cycles", 50)),
        )


@dataclass
class ApiConfig:
    """OpenAI-compatible chat completions API settings."""

    base_url: str
    model: str
    endpoint: str = "/chat/completions"
    api_key_env: str | None = None
    api_key: str | None = None
    timeout_sec: float = 120.0
    max_retries: int = 3
    retry_sleep_sec: float = 2.0
    concurrency: int = 4
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApiConfig":
        """Create API settings from a plain dictionary."""
        return cls(
            base_url=str(data["base_url"]),
            model=str(data["model"]),
            endpoint=str(data.get("endpoint", "/chat/completions")),
            api_key_env=data.get("api_key_env"),
            api_key=data.get("api_key"),
            timeout_sec=float(data.get("timeout_sec", 120.0)),
            max_retries=int(data.get("max_retries", 3)),
            retry_sleep_sec=float(data.get("retry_sleep_sec", 2.0)),
            concurrency=int(data.get("concurrency", 4)),
            headers={str(key): str(value) for key, value in dict(data.get("headers", {})).items()},
        )


@dataclass
class SamplingConfig:
    """Sampling parameters sent to the chat completions API."""

    temperature: float = 0.9
    top_p: float = 0.9
    max_tokens: int = 512
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    stop: list[str] = field(default_factory=list)
    extra_body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SamplingConfig":
        """Create sampling settings from a plain dictionary."""
        data = data or {}
        return cls(
            temperature=float(data.get("temperature", 0.9)),
            top_p=float(data.get("top_p", 0.9)),
            max_tokens=int(data.get("max_tokens", 512)),
            presence_penalty=data.get("presence_penalty"),
            frequency_penalty=data.get("frequency_penalty"),
            stop=[str(item) for item in data.get("stop", [])],
            extra_body=dict(data.get("extra_body", {})),
        )


@dataclass
class OutputConfig:
    """Filesystem output settings for dataset and report artifacts."""

    base_dir: Path
    flush_every: int = 100
    report_filename: str = "report.json"
    dataset_filename: str = "dataset.jsonl"
    per_rule_dir: str = "per_rule"
    rejection_sample_limit_per_rule: int = 100

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_dir: Path) -> "OutputConfig":
        """Create output settings and resolve the base directory."""
        base_dir = Path(str(data["base_dir"]))
        if not base_dir.is_absolute():
            base_dir = (config_dir / base_dir).resolve()
        return cls(
            base_dir=base_dir,
            flush_every=int(data.get("flush_every", 100)),
            report_filename=str(data.get("report_filename", "report.json")),
            dataset_filename=str(data.get("dataset_filename", "dataset.jsonl")),
            per_rule_dir=str(data.get("per_rule_dir", "per_rule")),
            rejection_sample_limit_per_rule=int(data.get("rejection_sample_limit_per_rule", 100)),
        )

    @property
    def report_path(self) -> Path:
        """Return the report JSON path."""
        return self.base_dir / self.report_filename

    @property
    def dataset_path(self) -> Path:
        """Return the combined dataset JSONL path."""
        return self.base_dir / self.dataset_filename

    @property
    def per_rule_path(self) -> Path:
        """Return the per-rule output directory path."""
        return self.base_dir / self.per_rule_dir


@dataclass
class ParserConfig:
    """Configuration for parsing raw model responses into text candidates."""

    type: str = "json_array"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ParserConfig":
        """Create parser settings from a plain dictionary."""
        data = data or {}
        return cls(type=str(data.get("type", "json_array")))


@dataclass
class PromptProfileConfig:
    """Prompt templates used to render chat messages."""

    system_template: str = DEFAULT_SYSTEM_TEMPLATE
    user_template: str = DEFAULT_USER_TEMPLATE
    output_contract_template: str = DEFAULT_OUTPUT_CONTRACT_TEMPLATE

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, config_dir: Path) -> "PromptProfileConfig":
        """Create prompt profile settings and load optional template files."""
        data = data or {}
        return cls(
            system_template=_read_template_value(data, "system_template", "system_template_path", DEFAULT_SYSTEM_TEMPLATE, config_dir),
            user_template=_read_template_value(data, "user_template", "user_template_path", DEFAULT_USER_TEMPLATE, config_dir),
            output_contract_template=_read_template_value(
                data,
                "output_contract_template",
                "output_contract_template_path",
                DEFAULT_OUTPUT_CONTRACT_TEMPLATE,
                config_dir,
            ),
        )


@dataclass
class DiversityProfileConfig:
    """A named set of diversity dimensions and per-prompt sample sizes."""

    name: str
    dimensions: dict[str, list[str]] = field(default_factory=dict)
    sample: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "DiversityProfileConfig":
        """Create a diversity profile from a plain dictionary."""
        raw_dimensions = dict(data.get("dimensions", {}))
        raw_sample = dict(data.get("sample", {}))
        return cls(
            name=name,
            dimensions={str(key): [str(item) for item in value] for key, value in raw_dimensions.items()},
            sample={str(key): int(value) for key, value in raw_sample.items()},
        )


@dataclass
class CheckConfig:
    """A single built-in check declaration for generated text."""

    type: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckConfig":
        """Create a check declaration from a plain dictionary."""
        params = dict(data)
        check_type = str(params.pop("type"))
        return cls(type=check_type, params=params)


@dataclass
class CallbackSpec:
    """External callback declaration using a Python file and function name."""

    path: Path
    function: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_dir: Path) -> "CallbackSpec":
        """Create a callback spec and resolve the callback path."""
        path = Path(str(data["path"]))
        if not path.is_absolute():
            path = (config_dir / path).resolve()
        return cls(path=path, function=str(data["function"]))

    def to_report(self) -> dict[str, str]:
        """Return a JSON-safe callback descriptor."""
        return {"path": str(self.path), "function": self.function}


@dataclass
class RuleCallbackConfig:
    """Callback lists that can be attached to a rule."""

    pre_extension: list[CallbackSpec] = field(default_factory=list)
    post_validation: list[CallbackSpec] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, config_dir: Path) -> "RuleCallbackConfig":
        """Create rule callback settings from a plain dictionary."""
        data = data or {}
        return cls(
            pre_extension=[CallbackSpec.from_dict(item, config_dir) for item in data.get("pre_extension", [])],
            post_validation=[CallbackSpec.from_dict(item, config_dir) for item in data.get("post_validation", [])],
        )


@dataclass
class ExampleConfig:
    """Positive and negative examples that define the rule intent."""

    positive: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExampleConfig":
        """Create example settings from a plain dictionary."""
        data = data or {}
        return cls(
            positive=[str(item) for item in data.get("positive", [])],
            negative=[str(item) for item in data.get("negative", [])],
        )


@dataclass
class RuleConfig:
    """Invariant definition of one target dataset slice."""

    id: str
    count: int
    goal: str
    batch_size: int = 10
    diversity_profile: str | None = None
    dedup_profile: str = "smart_text"
    examples: ExampleConfig = field(default_factory=ExampleConfig)
    checks: list[CheckConfig] = field(default_factory=list)
    callbacks: RuleCallbackConfig = field(default_factory=RuleCallbackConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_dir: Path) -> "RuleConfig":
        """Create a rule from a plain dictionary."""
        rule_id = str(data["id"])
        _validate_rule_id(rule_id)
        return cls(
            id=rule_id,
            count=int(data["count"]),
            goal=str(data["goal"]),
            batch_size=int(data.get("batch_size", 10)),
            diversity_profile=data.get("diversity_profile"),
            dedup_profile=str(data.get("dedup_profile", "smart_text")),
            examples=ExampleConfig.from_dict(data.get("examples")),
            checks=[CheckConfig.from_dict(item) for item in data.get("checks", [])],
            callbacks=RuleCallbackConfig.from_dict(data.get("callbacks"), config_dir),
        )


@dataclass
class NormalizationConfig:
    """Text normalization settings used by deduplication."""

    lowercase: bool = True
    collapse_spaces: bool = True
    trim_punctuation: bool = True
    replace_yo: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "NormalizationConfig":
        """Create normalization settings from a plain dictionary."""
        data = data or {}
        return cls(
            lowercase=bool(data.get("lowercase", True)),
            collapse_spaces=bool(data.get("collapse_spaces", True)),
            trim_punctuation=bool(data.get("trim_punctuation", True)),
            replace_yo=bool(data.get("replace_yo", True)),
        )


@dataclass
class PrefixLimitConfig:
    """Deduplication limit for overused text prefixes."""

    enabled: bool = True
    words: int = 4
    max_count: int = 8

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PrefixLimitConfig":
        """Create prefix limit settings from a plain dictionary."""
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            words=int(data.get("words", 4)),
            max_count=int(data.get("max_count", 8)),
        )


@dataclass
class NgramSimilarityConfig:
    """Deduplication settings for character n-gram Jaccard similarity."""

    enabled: bool = True
    ngram: int = 3
    threshold: float = 0.88
    max_compare: int = 1000

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "NgramSimilarityConfig":
        """Create n-gram similarity settings from a plain dictionary."""
        data = data or {}
        return cls(
            enabled=bool(data.get("enabled", True)),
            ngram=int(data.get("ngram", 3)),
            threshold=float(data.get("threshold", 0.88)),
            max_compare=int(data.get("max_compare", 1000)),
        )


@dataclass
class DedupProfileConfig:
    """Named deduplication policy used by one or more rules."""

    name: str
    scope: str = "rule"
    exact: bool = True
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    prefix_limit: PrefixLimitConfig = field(default_factory=PrefixLimitConfig)
    ngram_similarity: NgramSimilarityConfig = field(default_factory=NgramSimilarityConfig)

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "DedupProfileConfig":
        """Create a dedup profile from a plain dictionary."""
        return cls(
            name=name,
            scope=str(data.get("scope", "rule")),
            exact=bool(data.get("exact", True)),
            normalization=NormalizationConfig.from_dict(data.get("normalization")),
            prefix_limit=PrefixLimitConfig.from_dict(data.get("prefix_limit")),
            ngram_similarity=NgramSimilarityConfig.from_dict(data.get("ngram_similarity")),
        )


@dataclass
class ProjectConfig:
    """Full project configuration for one generator run."""

    config_path: Path
    run: RunConfig
    api: ApiConfig
    sampling: SamplingConfig
    output: OutputConfig
    parser: ParserConfig
    prompts: PromptProfileConfig
    diversity_profiles: dict[str, DiversityProfileConfig]
    dedup_profiles: dict[str, DedupProfileConfig]
    callbacks: RuleCallbackConfig
    rules: list[RuleConfig]

    @classmethod
    def from_dict(cls, data: dict[str, Any], config_path: Path) -> "ProjectConfig":
        """Create the full configuration from parsed YAML data."""
        config_dir = config_path.parent
        dedup_profiles = _load_dedup_profiles(dict(data.get("dedup_profiles", {})))
        return cls(
            config_path=config_path,
            run=RunConfig.from_dict(dict(data["run"])),
            api=ApiConfig.from_dict(dict(data["api"])),
            sampling=SamplingConfig.from_dict(data.get("sampling")),
            output=OutputConfig.from_dict(dict(data["output"]), config_dir),
            parser=ParserConfig.from_dict(data.get("parser")),
            prompts=PromptProfileConfig.from_dict(data.get("prompts"), config_dir),
            diversity_profiles=_load_diversity_profiles(dict(data.get("diversity_profiles", {}))),
            dedup_profiles=dedup_profiles,
            callbacks=RuleCallbackConfig.from_dict(data.get("callbacks"), config_dir),
            rules=[RuleConfig.from_dict(item, config_dir) for item in data.get("rules", [])],
        )


def _read_template_value(
    data: dict[str, Any],
    inline_key: str,
    path_key: str,
    default: str,
    config_dir: Path,
) -> str:
    """Read an inline template, a template file, or the provided default."""
    if data.get(path_key):
        path = Path(str(data[path_key]))
        if not path.is_absolute():
            path = (config_dir / path).resolve()
        return path.read_text(encoding="utf-8")
    if data.get(inline_key) is not None:
        return str(data[inline_key])
    return default


def _load_diversity_profiles(data: dict[str, Any]) -> dict[str, DiversityProfileConfig]:
    """Load all configured diversity profiles."""
    return {name: DiversityProfileConfig.from_dict(name, dict(value)) for name, value in data.items()}


def _load_dedup_profiles(data: dict[str, Any]) -> dict[str, DedupProfileConfig]:
    """Load configured dedup profiles and add the default profile if needed."""
    profiles = {name: DedupProfileConfig.from_dict(name, dict(value)) for name, value in data.items()}
    if "smart_text" not in profiles:
        profiles["smart_text"] = DedupProfileConfig(name="smart_text")
    return profiles


def _validate_rule_id(rule_id: str) -> None:
    """Validate that a rule id is safe to use in JSON and filenames."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", rule_id):
        raise ValueError(f"Rule id must match [A-Za-z0-9_.-]+: {rule_id}")
