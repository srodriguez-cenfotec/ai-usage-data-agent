# AI Usage Data Agent

A local data-agent prototype for exploring the cleaned AI usage survey dataset.
In rule-based mode, questions are handled by transparent patterns. Optionally,
a local language model can translate broader English or Spanish questions into
a constrained query plan. In either mode, Python validates the plan and computes
the answer directly from the CSV; the model never receives the dataset rows or
executes SQL or code.

## Run it

Requires Python 3.9 or newer. From the repository root:

```bash
python3 app.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). To choose another port:

```bash
python3 app.py --port 8766
```

The app reads `data/AI_Usage_and_Impact_Cleaned.csv` when it starts. Restart
the app after changing the file.

## Optional local LLM mode

This mode uses llama.cpp's OpenAI-compatible local server, like the reference
project. Install a `llama-server` build and download a GGUF instruction model,
then start the model server in one terminal. For example, with Qwen 2.5 1.5B:

```bash
llama-server -m /path/to/qwen2.5-1.5b-instruct-q4_k_m.gguf --alias qwen-ai-usage --host 127.0.0.1 --port 8081 -c 4096
```

In another terminal, start this app with the same model alias:

```bash
python3 app.py --model qwen-ai-usage
```

The app contacts only `127.0.0.1:8081` in this mode. If llama-server is not
running or the model returns an invalid plan, the app reports the error rather
than silently switching modes. Stop the model server and run `python3 app.py`
to return to rules-only mode. Model downloads and llama.cpp installation are
separate from this repository.

## Example questions

- What is the average productivity score?
- Compare time saved by user type
- Which AI tools are most popular?
- What is average satisfaction by country?
- What is the average AI usage for students?
- ¿Cuál es la satisfacción promedio por país?

Supported measures include age, monthly income, AI usage hours, monthly AI
cost, productivity, accuracy, satisfaction, time saved, and work/study hours.
Questions can ask for averages, totals, counts, or groupings by user type,
country, gender, AI tool, AI purpose, education level, or recommendation.
Numeric summaries exclude missing values. Use the displayed scope and response
counts when interpreting comparisons. Plans are restricted to supported
measures, groupings, dataset category values, and aggregate operations. This is
a prototype: inspect the scope and sample sizes before drawing conclusions.

## Tests

```bash
python3 -m unittest discover -s tests -v
```