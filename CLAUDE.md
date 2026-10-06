# Antroji kursinio dalis nuo nulio

Programos kūrimas dar nepradėtas. Sukurk mažą projektą naujame kodo aplanke pagal šaknies PROMPTAS.txt. Medžiaga pateikta bendra_medziaga. Nereikalauk anksčiau sugeneruoto kodo.

## Apimtis

- Vietinis Windows Python ir PySpark, be Docker.
- 2.1–2.3: didžiųjų duomenų technologija, apdorojimas ir atkuriamas našumo tyrimas.
- 34 tikrų WAV manifestas ir AppTek etaloniniai segmentai; viena eilutė skambučiui.
- Parquet/CSV, domain ir teksto apimties suvestinės, lygiavertis nuoseklus Python.
- 1k/10k/100k sintetinių struktūrinių eilučių apkrova; Python ir Spark local[1]/local[4], apšilimas ir trys kartojimai.
- Tikri matavimai, mediana, vienas grafikas ir lietuviškas README/išvados.

## Struktūra ir ryšys su trečia dalimi

Naudok src/call_mvp, minimalų pyproject.toml, requirements-part2.txt, tests, data/processed ir reports/part2. CLI: python -m call_mvp.cli prepare ir benchmark. Įdiegimas pip install -e .

Laukai ir katalogai nustatyti bendra_medziaga/PROJEKTO_STRUKTURA_IR_FORMATAS.txt. PySpark nėra bendrųjų būsimo ASR/LLM kodo importų priklausomybė. Trečia dalis vėliau kuria savo modulius ir atskirą requirements-part3.txt.

## Ribos

Nekurti ASR, OpenAI analizės, UI, Docker, DB, eilių ar debesijos. Raktų nereikia. Etalonai nėra mūsų modelio transkripcijos, reference_domain nėra LLM išvada, synthetic kopijos nėra nauji tikri skambučiai. local[4] nėra keli fiziniai serveriai.

## Darbo būdas

Kurti tikrus failus, pirmiausia maža apdorojimo patikra, tada tyrimas. Paketų ir Java/Python suderinamumą patikrinti vietoje, versijas užfiksuoti. Kelius konfigūruoti. Laikmatį stabdyti po tikro Spark skaičiavimo ir įrašymo.

Nesugalvoti duomenų, matavimų, testų ar pagreitėjimo. Trūkstamą aplinką įvardyti, nuo jos nepriklausomą kodą užbaigti. Originalių PDF/DOCX ir WAV nekeisti. Pateikti konkrečias PowerShell komandas ir tikrą 2.1–2.3 atitiktį.
