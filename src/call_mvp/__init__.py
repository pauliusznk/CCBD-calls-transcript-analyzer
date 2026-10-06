"""Klientų centro skambučių analizės kursinio MVP (2 dalis).

Skambutis: WAV -> ASR tekstas (asr.py) -> OpenAI analizė (llm.py).
Modeliai ir promptas – config/models.toml ir config/prompts.toml (config.py).
pipeline.py apdoroja vieną skambutį, compare.py tą patį darbą atlieka
paprastai (po vieną) ir su Spark (keli vienu metu) bei palygina laikus.
"""

__version__ = "0.3.0"
