"""Le modèle des agents survit à une panne passagère de Bedrock (agents/resistance.py).

Sans réseau : la classe mère est remplacée par un faux qui échoue ou répond selon un scénario.
"""

import asyncio

import pytest

from agents import resistance


class Indisponible(Exception):
    """Même texte que l'erreur relevée dans CloudWatch le 16 novembre 2026."""

    def __str__(self) -> str:
        return ("An error occurred (serviceUnavailableException) when calling the ConverseStream operation: "
                "Bedrock is unable to process your request.")


@pytest.fixture
def modele(monkeypatch):
    """Un ModeleResistant dont l'appel à Bedrock suit `scenario[identifiant]` : liste d'erreurs ou de None."""
    import strands.models

    scenario: dict[str, list] = {}
    appels: list[str] = []

    class FauxBedrock:
        def __init__(self, model_id, **reglages):
            self.model_id, self.reglages = model_id, reglages

        def update_config(self, model_id):
            self.model_id = model_id

        async def stream(self, *args, **kwargs):
            appels.append(self.model_id)
            suite = scenario.get(self.model_id) or [None]
            issue = suite.pop(0) if len(suite) > 1 else suite[0]
            if isinstance(issue, tuple):  # (événement émis, puis erreur) : panne au milieu d'une réponse
                yield issue[0]
                raise issue[1]
            if issue is not None:
                raise issue
            yield {"messageStop": {"stopReason": "end_turn"}}

    monkeypatch.setattr(strands.models, "BedrockModel", FauxBedrock)
    monkeypatch.setattr(resistance, "PAUSES", (0.0, 0.0, 0.0))
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    resistance.oublier_modeles()
    m = resistance.construire_modele()
    return m, scenario, appels


def _tout(m):
    async def lire():
        return [e async for e in m.stream([])]
    return asyncio.run(lire())


def test_reponses_non_diffusees_et_reprises(modele):
    m, _, _ = modele
    assert m.reglages["streaming"] is False
    assert m.reglages["boto_client_config"].retries == {"max_attempts": 4, "mode": "adaptive"}


def test_sans_panne_le_premier_modele_repond(modele):
    m, _, appels = modele
    assert _tout(m) and appels == [resistance.CHAINE_PAR_DEFAUT[0]]
    assert resistance.modeles_utilises() == [resistance.CHAINE_PAR_DEFAUT[0]]


def test_panne_du_premier_modele_le_suivant_repond(modele):
    m, scenario, appels = modele
    scenario[resistance.CHAINE_PAR_DEFAUT[0]] = [Indisponible()]
    assert _tout(m)
    assert appels == list(resistance.CHAINE_PAR_DEFAUT[:2])
    assert resistance.modeles_utilises() == [resistance.CHAINE_PAR_DEFAUT[1]]


def test_panne_generale_puis_retour_au_tour_suivant(modele):
    m, scenario, appels = modele
    for i in resistance.CHAINE_PAR_DEFAUT:
        scenario[i] = [Indisponible(), None]
    assert _tout(m)
    assert appels == list(resistance.CHAINE_PAR_DEFAUT) + [resistance.CHAINE_PAR_DEFAUT[0]]


def test_panne_durable_l_erreur_remonte_apres_tous_les_tours(modele):
    m, scenario, appels = modele
    for i in resistance.CHAINE_PAR_DEFAUT:
        scenario[i] = [Indisponible()]
    with pytest.raises(Indisponible):
        _tout(m)
    assert len(appels) == resistance.TOURS * len(resistance.CHAINE_PAR_DEFAUT)


def test_une_erreur_qui_n_est_pas_une_panne_remonte_tout_de_suite(modele):
    m, scenario, appels = modele
    scenario[resistance.CHAINE_PAR_DEFAUT[0]] = [ValueError("ValidationException: schéma d'outil invalide")]
    with pytest.raises(ValueError):
        _tout(m)
    assert len(appels) == 1


def test_une_reponse_commencee_ne_se_rejoue_pas(modele):
    m, scenario, appels = modele
    scenario[resistance.CHAINE_PAR_DEFAUT[0]] = [({"contentBlockDelta": {}}, Indisponible())]
    with pytest.raises(Indisponible):
        _tout(m)
    assert len(appels) == 1


def test_est_passagere_lit_aussi_la_cause_enveloppee():
    try:
        try:
            raise Indisponible()
        except Indisponible as e:
            raise RuntimeError("event loop cycle failed") from e
    except RuntimeError as enveloppe:
        assert resistance.est_passagere(enveloppe)
    assert resistance.est_passagere(Exception("ThrottlingException: Too many requests"))
    assert not resistance.est_passagere(Exception("AccessDeniedException: not authorized"))


def test_modele_regle_en_tete_de_chaine(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
    assert resistance.chaine_de_modeles() == ["us.anthropic.claude-sonnet-4-6", "global.anthropic.claude-sonnet-4-6",
                                              "global.anthropic.claude-sonnet-4-5-20250929-v1:0"]
