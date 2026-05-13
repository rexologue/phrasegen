"""Main generation runner."""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from phrasegen.api.client import ChatMessage, OpenAICompatibleClient
from phrasegen.callbacks.contracts import PostValidationChain, PreExtensionChain
from phrasegen.callbacks.loader import CallbackLoader
from phrasegen.checks.registry import CheckRegistry, CheckRunner
from phrasegen.config.entities import ProjectConfig, RuleConfig
from phrasegen.dedup.policy import DedupManager
from phrasegen.io.jsonl import JsonlWriter, load_jsonl, truncate_file
from phrasegen.io.report import RunReport
from phrasegen.parsing.parsers import ParserFactory, ResponseParser
from phrasegen.prompts.renderer import DiversitySampler, PromptRenderer, RenderedPrompt


@dataclass
class PromptRequest:
    """One rendered API request with metadata used for accepted records."""

    rule: RuleConfig
    request_index: int
    prompt: RenderedPrompt
    user_prompt_after_callbacks: str
    callbacks_report: dict[str, list[dict[str, str]]]


@dataclass
class ApiResponse:
    """Raw API response for one prompt request."""

    request: PromptRequest
    raw_text: str


class GenerationRunner:
    """Coordinates API calls, validation, deduplication, and output writing."""

    def __init__(self, config: ProjectConfig) -> None:
        """Create all runtime services from project configuration."""
        self.config = config
        self.client = OpenAICompatibleClient(config.api)
        self.parser = ParserFactory().create(config.parser.type)
        self.check_registry = CheckRegistry()
        self.callback_loader = CallbackLoader()
        self.dedup = DedupManager(config.dedup_profiles)
        self.renderer = PromptRenderer(config.prompts)
        self.report = RunReport(
            path=config.output.report_path,
            run_name=config.run.name,
            model=config.api.model,
            rejection_sample_limit=config.output.rejection_sample_limit_per_rule,
        )

    def run(self) -> None:
        """Run all configured rules to completion or configured request limits."""
        self._prepare_output_dirs()
        self.report.mark_running()
        try:
            for rule in self.config.rules:
                self._run_rule(rule)
            self._flush_report_done()
        except Exception as exc:
            self.report.mark_failed(str(exc))
            raise

    def _prepare_output_dirs(self) -> None:
        """Prepare output files according to resume settings."""
        self.config.output.base_dir.mkdir(parents=True, exist_ok=True)
        self.config.output.per_rule_path.mkdir(parents=True, exist_ok=True)
        if not self.config.run.resume:
            truncate_file(self.config.output.dataset_path)
            for rule in self.config.rules:
                truncate_file(self._rule_path(rule))

    def _run_rule(self, rule: RuleConfig) -> None:
        """Generate and accept candidates for one rule."""
        rule_report = self.report.ensure_rule(rule.id, rule.count)
        rule_report.status = "running"
        rule_report.started_at_unix = time.time()
        self.report.touch()

        check_runner = CheckRunner(self.check_registry.build_many(rule.checks))
        pre_chain, post_chain, callbacks_report = self._build_callback_chains(rule)
        self._restore_rule_state(rule, rule_report)

        dataset_writer = JsonlWriter(self.config.output.dataset_path, self.config.output.flush_every)
        per_rule_writer = JsonlWriter(self._rule_path(rule), self.config.output.flush_every)
        diversity_sampler = DiversitySampler(self.config.diversity_profiles, self._rng_for_rule(rule))
        request_index = rule_report.api_requests
        consecutive_empty_cycles = 0

        while rule_report.accepted < rule.count:
            if request_index >= self.config.run.max_requests_per_rule:
                rule_report.status = "request_limit_reached"
                break
            prompt_requests = self._build_prompt_requests(
                rule=rule,
                check_runner=check_runner,
                pre_chain=pre_chain,
                callbacks_report=callbacks_report,
                diversity_sampler=diversity_sampler,
                start_request_index=request_index,
            )
            if not prompt_requests:
                rule_report.errors["no_prompt_requests"] += 1
                break
            request_index += len(prompt_requests)
            accepted_before = rule_report.accepted
            self._execute_prompt_requests(
                prompt_requests=prompt_requests,
                parser=self.parser,
                check_runner=check_runner,
                post_chain=post_chain,
                dataset_writer=dataset_writer,
                per_rule_writer=per_rule_writer,
            )
            dataset_writer.flush()
            per_rule_writer.flush()
            rule_report.updated_at_unix = time.time()
            self.report.touch()
            if rule_report.accepted == accepted_before:
                consecutive_empty_cycles += 1
            else:
                consecutive_empty_cycles = 0
            if consecutive_empty_cycles >= self.config.run.max_consecutive_empty_cycles:
                rule_report.status = "empty_cycle_limit_reached"
                break

        dataset_writer.flush()
        per_rule_writer.flush()
        if rule_report.accepted >= rule.count:
            rule_report.status = "done"
        rule_report.finished_at_unix = time.time()
        rule_report.updated_at_unix = rule_report.finished_at_unix
        self.report.touch()

    def _build_prompt_requests(
        self,
        rule: RuleConfig,
        check_runner: CheckRunner,
        pre_chain: PreExtensionChain,
        callbacks_report: dict[str, list[dict[str, str]]],
        diversity_sampler: DiversitySampler,
        start_request_index: int,
    ) -> list[PromptRequest]:
        """Build prompt requests for one generation cycle."""
        rule_report = self.report.rules[rule.id]
        remaining = max(rule.count - rule_report.accepted, 1)
        estimated_prompts = max(1, math.ceil(remaining / max(rule.batch_size, 1)))
        prompt_count = min(
            self.config.run.prompts_per_cycle,
            self.config.api.concurrency,
            estimated_prompts,
            self.config.run.max_requests_per_rule - start_request_index,
        )
        prompt_requests: list[PromptRequest] = []
        for offset in range(prompt_count):
            diversity = diversity_sampler.sample(rule.diversity_profile)
            rendered = self.renderer.render(
                rule=rule,
                batch_size=rule.batch_size,
                check_descriptions=check_runner.describe(),
                diversity=diversity,
            )
            user_prompt_after_callbacks = pre_chain.apply(rendered.user)
            prompt_requests.append(
                PromptRequest(
                    rule=rule,
                    request_index=start_request_index + offset + 1,
                    prompt=rendered,
                    user_prompt_after_callbacks=user_prompt_after_callbacks,
                    callbacks_report=callbacks_report,
                )
            )
        return prompt_requests

    def _execute_prompt_requests(
        self,
        prompt_requests: list[PromptRequest],
        parser: ResponseParser,
        check_runner: CheckRunner,
        post_chain: PostValidationChain,
        dataset_writer: JsonlWriter,
        per_rule_writer: JsonlWriter,
    ) -> None:
        """Execute API requests concurrently and process their responses."""
        if prompt_requests:
            self.report.rules[prompt_requests[0].rule.id].api_requests += len(prompt_requests)
        with ThreadPoolExecutor(max_workers=self.config.api.concurrency) as executor:
            futures = {executor.submit(self._call_api, request): request for request in prompt_requests}
            for future in as_completed(futures):
                request = futures[future]
                try:
                    response = ApiResponse(request=request, raw_text=future.result())
                except Exception as exc:
                    self._record_error(request.rule.id, "api_error", str(exc))
                    continue
                self._process_response(response, parser, check_runner, post_chain, dataset_writer, per_rule_writer)

    def _call_api(self, request: PromptRequest) -> str:
        """Call the configured API for one prompt request."""
        messages = [
            ChatMessage(role="system", content=request.prompt.system),
            ChatMessage(role="user", content=request.user_prompt_after_callbacks),
        ]
        return self.client.complete(messages=messages, sampling=self.config.sampling)

    def _process_response(
        self,
        response: ApiResponse,
        parser: ResponseParser,
        check_runner: CheckRunner,
        post_chain: PostValidationChain,
        dataset_writer: JsonlWriter,
        per_rule_writer: JsonlWriter,
    ) -> None:
        """Parse, validate, deduplicate, and write candidates from one response."""
        rule = response.request.rule
        rule_report = self.report.rules[rule.id]
        try:
            candidates = parser.parse(response.raw_text)
        except Exception as exc:
            self._record_rejection(rule.id, "parse_error", {"error": str(exc), "raw_text": response.raw_text})
            return
        rule_report.parsed_candidates += len(candidates)
        for candidate_index, candidate in enumerate(candidates, 1):
            if rule_report.accepted >= rule.count:
                break
            self._process_candidate(
                rule=rule,
                text=candidate,
                candidate_index=candidate_index,
                request=response.request,
                check_runner=check_runner,
                post_chain=post_chain,
                dataset_writer=dataset_writer,
                per_rule_writer=per_rule_writer,
            )

    def _process_candidate(
        self,
        rule: RuleConfig,
        text: str,
        candidate_index: int,
        request: PromptRequest,
        check_runner: CheckRunner,
        post_chain: PostValidationChain,
        dataset_writer: JsonlWriter,
        per_rule_writer: JsonlWriter,
    ) -> None:
        """Process one parsed text candidate."""
        rule_report = self.report.rules[rule.id]
        check_result = check_runner.validate(text)
        if not check_result.accepted:
            self._record_rejection(rule.id, check_result.reason, {"text": text})
            return
        try:
            post_result = post_chain.validate(text)
        except Exception as exc:
            self._record_error(rule.id, "post_validation_callback_error", str(exc))
            self._record_rejection(rule.id, "post_validation_callback_error", {"text": text, "error": str(exc)})
            return
        if not post_result.accepted:
            reason = post_result.reason or "post_validation_rejected"
            self._record_rejection(rule.id, f"post_validation:{reason}", {"text": text})
            return
        dedup_result = self.dedup.check(rule.id, rule.dedup_profile, text)
        if not dedup_result.accepted:
            self._record_rejection(rule.id, f"dedup:{dedup_result.reason}", {"text": text})
            return
        record = self._make_record(rule, text, candidate_index, request)
        dataset_writer.append(record)
        per_rule_writer.append(record)
        self.dedup.accept(rule.id, rule.dedup_profile, text)
        rule_report.accepted += 1

    def _make_record(
        self,
        rule: RuleConfig,
        text: str,
        candidate_index: int,
        request: PromptRequest,
    ) -> dict[str, Any]:
        """Create the JSONL record for one accepted text."""
        return {
            "rule_id": rule.id,
            "text": text,
            "meta": {
                "run_name": self.config.run.name,
                "source": "openai_compatible_api",
                "model": self.config.api.model,
                "accepted_at_unix": time.time(),
                "request_index": request.request_index,
                "candidate_index": candidate_index,
                "parser": self.parser.name,
                "diversity": request.prompt.diversity,
                "callbacks": request.callbacks_report,
            },
        }

    def _restore_rule_state(self, rule: RuleConfig, rule_report: Any) -> None:
        """Restore accepted count and dedup state from per-rule JSONL."""
        if not self.config.run.resume:
            return
        rows = load_jsonl(self._rule_path(rule))
        for row in rows:
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            self.dedup.add_existing(rule.id, rule.dedup_profile, text)
            rule_report.accepted += 1

    def _build_callback_chains(
        self,
        rule: RuleConfig,
    ) -> tuple[PreExtensionChain, PostValidationChain, dict[str, list[dict[str, str]]]]:
        """Load global and rule-level callbacks and return executable chains."""
        pre_specs = [*self.config.callbacks.pre_extension, *rule.callbacks.pre_extension]
        post_specs = [*self.config.callbacks.post_validation, *rule.callbacks.post_validation]
        pre_callbacks = [self.callback_loader.load_pre_extension(spec) for spec in pre_specs]
        post_callbacks = [self.callback_loader.load_post_validation(spec) for spec in post_specs]
        callbacks_report = {
            "pre_extension": [spec.to_report() for spec in pre_specs],
            "post_validation": [spec.to_report() for spec in post_specs],
        }
        return PreExtensionChain(pre_callbacks), PostValidationChain(post_callbacks), callbacks_report

    def _record_rejection(self, rule_id: str, reason: str, sample: dict[str, Any]) -> None:
        """Record a rejected candidate or response in the report."""
        rule_report = self.report.rules[rule_id]
        rule_report.rejected[reason] += 1
        self.report.add_rejection_sample(rule_id, {"reason": reason, **sample})

    def _record_error(self, rule_id: str, error_type: str, error: str) -> None:
        """Record a runtime error in the report."""
        rule_report = self.report.rules[rule_id]
        rule_report.errors[error_type] += 1
        self.report.add_rejection_sample(rule_id, {"reason": error_type, "error": error})

    def _rule_path(self, rule: RuleConfig) -> Any:
        """Return the per-rule JSONL path."""
        return self.config.output.per_rule_path / f"{rule.id}.jsonl"

    def _rng_for_rule(self, rule: RuleConfig) -> Any:
        """Create a deterministic random generator for a rule."""
        import random

        seed = f"{self.config.run.random_seed}:{rule.id}"
        return random.Random(seed)

    def _flush_report_done(self) -> None:
        """Mark report as done after all rules have finished."""
        if any(rule_report.status != "done" for rule_report in self.report.rules.values()):
            self.report.mark_finished("finished_with_incomplete_rules")
            return
        self.report.mark_done()
