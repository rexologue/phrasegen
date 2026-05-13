"""Deduplication policy and state."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass

from phrasegen.config.entities import DedupProfileConfig
from phrasegen.dedup.normalization import TextNormalizer, char_ngrams, jaccard


@dataclass
class DedupResult:
    """Result of checking a text candidate against deduplication state."""

    accepted: bool
    reason: str = ""

    @classmethod
    def ok(cls) -> "DedupResult":
        """Create a successful dedup result."""
        return cls(accepted=True, reason="")

    @classmethod
    def reject(cls, reason: str) -> "DedupResult":
        """Create a failed dedup result."""
        return cls(accepted=False, reason=reason)


class DedupBucket:
    """Deduplication state for one scope, such as one rule or the whole dataset."""

    def __init__(self, profile: DedupProfileConfig) -> None:
        """Initialize empty dedup state for a profile."""
        self.profile = profile
        self.normalizer = TextNormalizer(profile.normalization)
        self.normalized_texts: set[str] = set()
        self.prefix_counts: Counter[str] = Counter()
        self.recent_normalized: deque[str] = deque(maxlen=max(1, profile.ngram_similarity.max_compare))

    def add_existing(self, text: str) -> None:
        """Add already accepted text to the dedup state."""
        normalized = self.normalizer.normalize(text)
        self.normalized_texts.add(normalized)
        if self.profile.prefix_limit.enabled:
            prefix = self.normalizer.prefix_key(text, self.profile.prefix_limit.words)
            self.prefix_counts[prefix] += 1
        self.recent_normalized.append(normalized)

    def check(self, text: str) -> DedupResult:
        """Check whether text is unique enough for this bucket."""
        normalized = self.normalizer.normalize(text)
        if self.profile.exact and normalized in self.normalized_texts:
            return DedupResult.reject("duplicate_exact")
        if self.profile.prefix_limit.enabled:
            prefix = self.normalizer.prefix_key(text, self.profile.prefix_limit.words)
            if self.prefix_counts[prefix] >= self.profile.prefix_limit.max_count:
                return DedupResult.reject("prefix_overuse")
        if self.profile.ngram_similarity.enabled and self._has_near_duplicate(normalized):
            return DedupResult.reject("ngram_near_duplicate")
        return DedupResult.ok()

    def accept(self, text: str) -> None:
        """Persist accepted text into the dedup state."""
        self.add_existing(text)

    def _has_near_duplicate(self, normalized: str) -> bool:
        """Return whether recent accepted text is too similar to the candidate."""
        candidate_ngrams = char_ngrams(normalized, self.profile.ngram_similarity.ngram)
        for existing in self.recent_normalized:
            existing_ngrams = char_ngrams(existing, self.profile.ngram_similarity.ngram)
            if jaccard(candidate_ngrams, existing_ngrams) >= self.profile.ngram_similarity.threshold:
                return True
        return False


class DedupManager:
    """Coordinates rule-level and global deduplication buckets."""

    def __init__(self, profiles: dict[str, DedupProfileConfig]) -> None:
        """Store profile definitions and prepare global buckets lazily."""
        self.profiles = profiles
        self.rule_buckets: dict[str, DedupBucket] = {}
        self.global_buckets: dict[str, DedupBucket] = {}

    def bucket_for_rule(self, rule_id: str, profile_name: str) -> DedupBucket:
        """Return the dedup bucket used by a rule."""
        profile = self._profile(profile_name)
        if profile.scope == "global":
            return self._global_bucket(profile_name)
        key = f"{rule_id}:{profile_name}"
        if key not in self.rule_buckets:
            self.rule_buckets[key] = DedupBucket(profile)
        return self.rule_buckets[key]

    def add_existing(self, rule_id: str, profile_name: str, text: str) -> None:
        """Add existing accepted text to the correct dedup bucket."""
        self.bucket_for_rule(rule_id, profile_name).add_existing(text)

    def check(self, rule_id: str, profile_name: str, text: str) -> DedupResult:
        """Run deduplication for a candidate text."""
        return self.bucket_for_rule(rule_id, profile_name).check(text)

    def accept(self, rule_id: str, profile_name: str, text: str) -> None:
        """Record an accepted candidate in the correct dedup bucket."""
        self.bucket_for_rule(rule_id, profile_name).accept(text)

    def _profile(self, profile_name: str) -> DedupProfileConfig:
        """Return a configured dedup profile by name."""
        profile = self.profiles.get(profile_name)
        if profile is None:
            raise ValueError(f"Unknown dedup profile: {profile_name}")
        return profile

    def _global_bucket(self, profile_name: str) -> DedupBucket:
        """Return a global bucket for a profile."""
        if profile_name not in self.global_buckets:
            self.global_buckets[profile_name] = DedupBucket(self._profile(profile_name))
        return self.global_buckets[profile_name]
