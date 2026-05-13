"""Prompt rendering from rules, checks, and diversity context."""

from __future__ import annotations

import random
from dataclasses import dataclass

from phrasegen.config.entities import DiversityProfileConfig, PromptProfileConfig, RuleConfig
from phrasegen.utils.text import format_list, format_mapping


@dataclass
class RenderedPrompt:
    """Rendered chat prompt and metadata used for one API request."""

    system: str
    user: str
    diversity: dict[str, list[str]]


class DiversitySampler:
    """Samples configured diversity dimensions for each prompt."""

    def __init__(self, profiles: dict[str, DiversityProfileConfig], rng: random.Random) -> None:
        """Store diversity profiles and the run-level random generator."""
        self.profiles = profiles
        self.rng = rng

    def sample(self, profile_name: str | None) -> dict[str, list[str]]:
        """Sample one diversity pack for a profile name."""
        if not profile_name:
            return {}
        profile = self.profiles.get(profile_name)
        if profile is None:
            raise ValueError(f"Unknown diversity profile: {profile_name}")
        result: dict[str, list[str]] = {}
        for dimension, values in profile.dimensions.items():
            sample_size = min(int(profile.sample.get(dimension, 0)), len(values))
            if sample_size > 0:
                result[dimension] = self.rng.sample(values, k=sample_size)
        return result


class PromptRenderer:
    """Renders system and user prompts from templates."""

    def __init__(self, profile: PromptProfileConfig) -> None:
        """Store prompt templates."""
        self.profile = profile

    def render(
        self,
        rule: RuleConfig,
        batch_size: int,
        check_descriptions: list[str],
        diversity: dict[str, list[str]],
    ) -> RenderedPrompt:
        """Render one prompt for a rule and sampled diversity context."""
        output_contract = self.profile.output_contract_template.strip()
        user = self.profile.user_template.format(
            rule_id=rule.id,
            batch_size=batch_size,
            goal=rule.goal,
            positive_examples=format_list(rule.examples.positive),
            negative_examples=format_list(rule.examples.negative),
            checks=format_list(check_descriptions),
            diversity=format_mapping(diversity),
            output_contract=output_contract,
        )
        return RenderedPrompt(
            system=self.profile.system_template.strip(),
            user=user.strip(),
            diversity=diversity,
        )
