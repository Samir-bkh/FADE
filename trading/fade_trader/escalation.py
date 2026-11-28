"""Escalade vers le CERVEAU (Claude Opus 5.5).

Déclenchée quand la confiance de Jev < 0,60 ou que le régime bascule en crise.
Le verdict d'Opus ne peut que RESTREINDRE : veto, réduction, ou maintien.
Il ne peut jamais ouvrir, agrandir une position ou modifier une limite — cela
est imposé ici, en code, quel que soit le contenu de la réponse.

L'appel est asynchrone (thread) : la boucle réflexe ne l'attend pas. Tant
qu'une revue est en cours pour un symbole, les nouvelles entrées sont gelées.
Un échec, un timeout ou un refus du modèle vaut veto (fail-safe).
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"

SYSTEM = """Tu es le relecteur de risque d'un agent de trading crypto automatisé.
On te transmet un instantané de marché calculé en code, la décision du modèle
réflexe et le contexte de la thèse. Tu ne peux que restreindre : "veto"
(geler les entrées sur ce symbole jusqu'à expiration), "reduce" (réduire la
position d'une fraction), ou "hold" (aucun changement). Tu n'ouvres jamais de
position. Sois bref et factuel ; si l'information est insuffisante, choisis
la restriction la plus prudente."""


class ReviewVerdict(BaseModel):
    action: Literal["veto", "reduce", "hold"]
    reduce_fraction: float = Field(ge=0.0, le=1.0, description="part de la position à couper si action=reduce")
    freeze_minutes: int = Field(ge=0, le=1440, description="durée du gel des entrées")
    rationale: str


@dataclass(frozen=True)
class EnforcedVerdict:
    action: str
    reduce_fraction: float
    freeze_until_ms: int
    rationale: str
    source: str


def enforce(v: ReviewVerdict, now_ms: int, source: str = "opus") -> EnforcedVerdict:
    """Bornes appliquées par le code, indépendamment du modèle."""
    frac = v.reduce_fraction if v.action == "reduce" else 0.0
    freeze = max(v.freeze_minutes, 15 if v.action == "veto" else 0)
    return EnforcedVerdict(v.action, min(max(frac, 0.0), 1.0), now_ms + freeze * 60_000,
                           v.rationale[:500], source)


def fail_safe(now_ms: int, why: str) -> EnforcedVerdict:
    return EnforcedVerdict("veto", 0.0, now_ms + 60 * 60_000, f"fail-safe : {why}", "fail_safe")


class Escalator:
    def __init__(self, enabled: bool = True, cooldown_s: float = 300.0, timeout_s: float = 120.0):
        self.enabled = enabled
        self.cooldown_s = cooldown_s
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._pending: dict[str, threading.Thread] = {}
        self._results: dict[str, EnforcedVerdict] = {}
        self._last: dict[str, float] = {}
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic  # dépendance optionnelle [brain]
            self._client = anthropic.Anthropic(timeout=self.timeout_s, max_retries=1)
        return self._client

    def busy(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._pending

    def pop_result(self, symbol: str) -> EnforcedVerdict | None:
        with self._lock:
            return self._results.pop(symbol, None)

    def submit(self, symbol: str, now_ms: int, payload: dict) -> bool:
        """Retourne True si une revue a été lancée (False : cooldown ou déjà en cours)."""
        with self._lock:
            if symbol in self._pending:
                return False
            if time.monotonic() - self._last.get(symbol, -1e9) < self.cooldown_s:
                return False
            self._last[symbol] = time.monotonic()
            if not self.enabled:
                self._results[symbol] = fail_safe(now_ms, "escalade désactivée (pas de cerveau configuré)")
                return True
            t = threading.Thread(target=self._run, args=(symbol, now_ms, payload), daemon=True)
            self._pending[symbol] = t
        t.start()
        return True

    def _run(self, symbol: str, now_ms: int, payload: dict) -> None:
        try:
            verdict = self.review(now_ms, payload)
        except Exception as e:  # noqa: BLE001 — tout échec = veto
            verdict = fail_safe(now_ms, f"{type(e).__name__}")
        with self._lock:
            self._results[symbol] = verdict
            self._pending.pop(symbol, None)

    def review(self, now_ms: int, payload: dict) -> EnforcedVerdict:
        client = self._get_client()
        resp = client.messages.parse(
            model=MODEL,
            max_tokens=4000,
            output_config={"effort": "high"},
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            output_format=ReviewVerdict,
        )
        # Pas de modèle de repli : un refus produit déjà le comportement voulu (veto).
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            return fail_safe(now_ms, f"réponse inutilisable ({resp.stop_reason})")
        return enforce(resp.parsed_output, now_ms)
