# Klientų centro skambučių analizė – kursinio 2 dalis

Programa paima tikrus skambučių garso įrašus, paverčia juos tekstu ir su OpenAI modeliu įvertina
kiekvieną pokalbį. Tą patį darbą ji atlieka dviem būdais ir palygina, kuris greitesnis.

## Kaip veikia

Vienas skambutis:

1. **Garsas → tekstas (ASR).** WAV siunčiamas į OpenAI suderinamą API (dabar `parakeet`)
   5 minučių dalimis, o tekstai sujungiami.
2. **Tekstas → analizė (LLM).** Vienas OpenAI Agents SDK agentas (dabar `gpt-6.1-sol`) pagal
   `config/prompts.toml` instrukcijas grąžina:
   - santrauką lietuviškai;
   - temą (`information_request`, `order_or_booking`, `billing_or_payment`, `technical_issue`,
     `account_change`, `complaint`, `other`);
   - ar problema išspręsta (`resolved` / `unresolved` / `unknown`) ir tikslią citatą tam pagrįsti;
   - ar klientas nepatenkintas (`yes` / `no` / `unknown`).

   Programa patikrina, ar citata tikrai yra tekste (`quote_found`).

Du būdai tiems patiems 34 skambučiams:

| Būdas | Kaip dirba |
|---|---|
| **Paprastas Python** | skambučius apdoroja po vieną: siunčia garsą, laukia teksto, siunčia tekstą, laukia analizės |
| **Spark `local[4]`** | 4 darbininkai vienu metu apdoroja skirtingus skambučius |

Rezultatai netalpinami: abu būdai iš naujo siunčia visus skambučius. Palyginama:
- bendras laikas;
- ar sutampa ASR tekstai ir LLM išvados (tema, išspręsta, nepasitenkinimas).

## Paleidimas (PowerShell, projekto šaknyje)

```powershell
# 1. Aplinka (vieną kartą)
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # jei blokuojama: Set-ExecutionPolicy -Scope Process Bypass
python -m pip install -r requirements-part2.txt
python -m pip install -e .

# 2. Java Spark'ui (tik jei `java -version` neveikia; nustatoma tik šiai sesijai)
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.20.101-hotspot"
$env:Path = "$env:JAVA_HOME\bin;$env:Path"

# 3. Nustatymai: nukopijuok .env.example į .env ir įrašyk OPENAI_API_KEY
Copy-Item .env.example .env
notepad .env

# 4. Greitas bandymas su 2 trumpiausiais skambučiais (~1 min)
python -m call_mvp.cli compare --limit 2 --reports reports/bandymas --output data/bandymas

# 5. Visi 34 skambučiai (~355 min garso)
python -m call_mvp.cli compare

# 6. Testai (be interneto ir be modelio)
python -m pytest
```

Reikia `bendra_medziaga/manifest.csv` (skambučių sąrašo) ir WAV failų kataloge `dataset/`. Jei
`dataset/` yra kitur, nurodyk `--data-root` arba `DATA_ROOT` aplanką, kuriame yra `dataset/`.

## Nustatymai: kur ką keisti

| Failas | Kas ten | Pavyzdys |
|---|---|---|
| `.env` | API raktas, API adresas, duomenų aplankas (į Git nekeliamas) | `OPENAI_BASE_URL=https://api-lb.i4tech.lt/v1` |
| `config/models.toml` | ASR ir LLM modeliai, įrašo dalies ilgis, `temperature` | `model = "parakeet"`, `model = "gpt-6.1-sol"` |
| `config/prompts.toml` | LLM instrukcijos ir leidžiamų temų sąrašas | `topics = [...]`, `instructions = """..."""` |

Programa šiuos failus nuskaito vieną kartą ir tuos pačius nustatymus naudoja abiem būdais, taip pat
Spark darbininkuose. `reports/part2/palyginimas.json` įrašo modelius ir prompto kodą (`prompt_sha256`),
todėl matyti, kokiais nustatymais gauti rezultatai. Kitą nustatymų aplanką galima nurodyti `--config`.

## Rezultatai

| Failas | Kas viduje |
|---|---|
| `reports/part2/laikai.csv` | kiekvieno būdo bendras laikas, ASR ir LLM laikų sumos, pagreitis, klaidos |
| `reports/part2/laikai.png` | laikų grafikas |
| `reports/part2/skambuciai.csv` | viena eilutė skambučiui: abiejų būdų laikai, išvados ir ASR tekstų panašumas |
| `reports/part2/palyginimas.json` | santrauka: laikai, sutapimai, modeliai ir versijos |
| `data/results/python.csv`, `spark_local_4.csv` | kiekvieno skambučio analizė |
| `data/results/*.jsonl` | tas pats su visu ASR tekstu |

## Svarbu žinoti

- 34 įrašai yra viešo AppTek rinkinio pokalbiai (CC BY-SA 4.0). Garsas ir tekstas siunčiami į
  `OPENAI_BASE_URL` nurodytą API.
- Garsas mono, todėl kliento ir konsultanto balsai neatskirti. Neaiškiais atvejais modelis turi
  atsakyti `unknown`.
- `local[4]` reiškia 4 darbininkus viename kompiuteryje, ne kelių serverių klasterį.
- `whisper-1` per `api-lb.i4tech.lt` 2026-10-06 grąžino `502` net 1 min įrašui, todėl naudojamas
  `parakeet`. Tas pats serveris ~16 min įrašą atmetė, todėl garsas siunčiamas 5 min dalimis
  (dalies riba gali perkirsti žodį).
- Spark paleidžiant matomas `WARN ... winutils.exe` yra tikėtinas ir darbui netrukdo.

## Kodas

```
config/models.toml        modeliai
config/prompts.toml       LLM promptas ir temos
src/call_mvp/config.py    nuskaito models.toml ir prompts.toml
src/call_mvp/asr.py       garsas -> tekstas (API, 5 min dalys)
src/call_mvp/llm.py       tekstas -> OpenAI analizė (Agent + Runner, Pydantic schema)
src/call_mvp/pipeline.py  skambučių sąrašas ir vieno skambučio apdorojimas
src/call_mvp/compare.py   paprastas Python ir Spark, palyginimas, ataskaita
src/call_mvp/cli.py       komanda compare
tests/test_part2.py       paprasti testai
```
