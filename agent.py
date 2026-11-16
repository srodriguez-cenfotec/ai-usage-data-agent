"""Rule-based question answering for the AI usage survey dataset."""

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from statistics import mean
from urllib.request import ProxyHandler, Request, build_opener


DATASET = Path(__file__).parent / "data" / "AI_Usage_and_Impact_Cleaned.csv"
MISSING = {"", "null", "none", "nan", "n/a"}

METRICS = {
    "Age": ("Age", ("age", "edad")),
    "Monthly_Income": ("Monthly income", ("monthly income", "income", "salario", "ingreso")),
    "AI_Usage_Hours_Per_Day": (
        "AI use (hours/day)",
        ("ai usage hours", "usage hours", "hours of ai", "ai usage", "usage of ai", "use of ai", "daily ai usage", "horas de uso", "horas usando ia", "uso de ia"),
    ),
    "Monthly_AI_Cost": ("Monthly AI cost", ("monthly ai cost", "ai cost", "cost", "costo", "gasto")),
    "Productivity_Score": (
        "Productivity score",
        ("productivity", "productivity score", "productividad"),
    ),
    "Accuracy_Rating": ("Accuracy rating", ("accuracy", "accuracy rating", "precision", "precisión")),
    "Satisfaction_Score": (
        "Satisfaction score",
        ("satisfaction", "satisfaction score", "satisfaccion", "satisfacción"),
    ),
    "Time_Saved_Hours_Per_Week": (
        "Time saved (hours/week)",
        ("time saved", "hours saved", "tiempo ahorrado", "horas ahorradas"),
    ),
    "Work_or_Study_Hours_Per_Day": (
        "Work/study (hours/day)",
        ("work or study hours", "work/study hours", "work hours", "study hours", "horas de trabajo", "horas de estudio"),
    ),
}

CATEGORIES = {
    "User_Type": ("User type", ("user type", "type of user", "tipo de usuario", "students", "student", "estudiantes", "estudiante", "professionals", "professional", "profesionales", "profesional")),
    "Country": ("Country", ("country", "countries", "country/region", "pais", "país", "paises", "países")),
    "Gender": ("Gender", ("gender", "genero", "género")),
    "AI_Tool": ("AI tool", ("ai tool", "tool", "tools", "herramienta", "herramientas", "ia")),
    "AI_Purpose": ("AI purpose", ("ai purpose", "purpose", "use case", "purpose of use", "proposito", "propósito", "uso")),
    "Education_Level": ("Education level", ("education level", "education", "nivel educativo", "educacion", "educación")),
    "Would_Recommend": ("Recommendation", ("recommend", "recommendation", "recomendaria", "recomendaría", "recomendacion", "recomendación")),
}


def _fold(value):
    value = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def _number(value):
    if value is None or _fold(value).strip() in MISSING:
        return None
    cleaned = re.sub(r"\s*(hours?|hrs?|horas?)\s*$", "", str(value).strip(), flags=re.IGNORECASE)
    try:
        return float(cleaned.replace(",", ""))
    except ValueError:
        return None


def _category_value(column, value):
    value = value.strip()
    folded = _fold(value)
    if column == "Gender":
        return {"m": "Male", "f": "Female", "non binary": "Non-binary"}.get(folded, value.title())
    if column == "AI_Tool":
        aliases = {
            "chat gpt": "ChatGPT", "chatgpt": "ChatGPT",
            "google gemini": "Google Gemini", "gemini": "Google Gemini",
            "copilot": "Microsoft Copilot", "microsoft copilot": "Microsoft Copilot",
            "claude": "Claude", "perplexity": "Perplexity AI", "perplexity ai": "Perplexity AI",
        }
        return aliases.get(folded, value.strip())
    if column == "User_Type":
        return {"student": "Student", "professional": "Professional"}.get(folded, value.title())
    if column == "Would_Recommend":
        return value.title()
    return value.strip()


def load_data(path=DATASET):
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "User_ID" not in reader.fieldnames:
            raise ValueError(f"{path} is missing the expected survey columns.")
        rows = []
        for raw in reader:
            row = {}
            for key, value in raw.items():
                value = (value or "").strip()
                if key in METRICS:
                    row[key] = _number(value)
                elif _fold(value) in MISSING:
                    row[key] = None
                elif key in CATEGORIES:
                    row[key] = _category_value(key, value)
                else:
                    row[key] = value
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no survey records.")
    return rows


def _contains(text, phrase):
    return re.search(r"(?<!\w)" + re.escape(_fold(phrase)) + r"(?!\w)", text) is not None


def _metric(question):
    folded = _fold(question)
    for column, (label, aliases) in METRICS.items():
        if any(_contains(folded, alias) for alias in aliases):
            return column, label
    return None, None


def _group_column(question):
    folded = _fold(question)
    for column, (_, aliases) in CATEGORIES.items():
        explicit = any(
            _contains(folded, marker + alias)
            for marker in ("by ", "per ", "por ", "entre ")
            for alias in aliases
        )
        if explicit:
            return column
    if any(_contains(folded, word) for word in ("popular", "most common", "top", "mas usado", "más usado", "mas popular", "más popular")):
        return "AI_Tool"
    if any(_contains(folded, word) for word in ("student", "students", "professional", "professionals", "estudiante", "estudiantes", "profesional", "profesionales")):
        return "User_Type"
    return None


def _filters(question, rows, group_column):
    folded = _fold(question)
    filters = {}
    for column in CATEGORIES:
        if column == group_column:
            continue
        values = sorted({row[column] for row in rows if row.get(column)}, key=lambda value: (-len(_fold(value)), _fold(value)))
        for value in values:
            aliases = [value]
            if column == "AI_Tool" and value == "ChatGPT":
                aliases += ["Chat GPT"]
            if column == "User_Type":
                aliases += {"Student": ["student", "students", "estudiante", "estudiantes"],
                            "Professional": ["professional", "professionals", "profesional", "profesionales"]}.get(value, [])
            if any(_contains(folded, alias) for alias in aliases):
                filters[column] = value
                break
    return filters


def _format(value):
    if value is None:
        return "—"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _answer_rules(question, rows):
    question = question.strip()
    if not question or len(question) > 500:
        raise ValueError("Enter a question of 1–500 characters.")
    metric, metric_label = _metric(question)
    group = _group_column(question)
    filters = _filters(question, rows, group)
    selected = [row for row in rows if all(row.get(column) == value for column, value in filters.items())]
    folded = _fold(question)
    asks_count = any(_contains(folded, word) for word in ("how many", "count", "number of", "cuantos", "cuantas", "cantidad"))
    if not metric and group == "AI_Tool" and any(
        _contains(folded, word)
        for word in ("popular", "most common", "top", "mas usado", "más usado", "mas popular", "más popular")
    ):
        asks_count = True
    asks_sum = any(_contains(folded, word) for word in ("total", "sum", "suma"))
    if not metric and not asks_count:
        raise ValueError("I couldn't identify a measure. Try asking about productivity, satisfaction, time saved, AI usage, cost, income, accuracy, age, or the number of respondents.")

    aggregation = "count" if asks_count and not metric else "sum" if asks_sum else "average"
    label = "Respondents" if aggregation == "count" else metric_label
    values_by_group = defaultdict(list)
    if group:
        for row in selected:
            key = row.get(group)
            value = row.get(metric) if metric else row.get("User_ID")
            if key is not None and value is not None:
                values_by_group[key].append(value)
        result_rows = []
        for key, values in values_by_group.items():
            value = len(values) if aggregation == "count" else sum(values) if aggregation == "sum" else mean(values)
            result_rows.append({"group": key, "value": round(value, 2), "responses": len(values)})
        result_rows.sort(key=lambda item: (-item["value"], _fold(item["group"])))
        if not result_rows:
            raise ValueError("No matching records have a value for that measure.")
        title = f"{label} by {CATEGORIES[group][0].lower()}"
        summary = f"{label}: {_format(result_rows[0]['value'])} for {result_rows[0]['group']} (highest group)."
        chart = [{"label": item["group"], "value": item["value"]} for item in result_rows[:10]]
        columns = [CATEGORIES[group][0], label, "Responses"]
        table = [[item["group"], _format(item["value"]), item["responses"]] for item in result_rows]
    else:
        values = [row.get(metric) for row in selected if row.get(metric) is not None] if metric else selected
        if not values:
            raise ValueError("No matching records have a value for that measure.")
        result = len(values) if aggregation == "count" else sum(values) if aggregation == "sum" else mean(values)
        title = label
        summary = f"{label}: {_format(result)} across {len(values)} responses."
        chart = [{"label": label, "value": round(result, 2)}]
        columns = ["Measure", "Result", "Responses"]
        table = [[label, _format(result), len(values)]]

    filter_text = ", ".join(f"{CATEGORIES[column][0]}: {value}" for column, value in filters.items())
    return {
        "title": title,
        "summary": summary,
        "filters": filter_text or "All available records",
        "columns": columns,
        "rows": table,
        "chart": chart,
        "chartLabel": label,
        "matched": len(selected),
        "available": len(rows),
    }


def _llm_plan(question, rows, model):
    options = {
        column: sorted({row[column] for row in rows if row.get(column)}, key=_fold)
        for column in CATEGORIES
    }
    schema = {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "enum": [*METRICS, "__records__", ""]},
            "aggregation": {"type": "string", "enum": ["count", "average", "sum", "max"]},
            "group_by": {"type": "string", "enum": ["", *CATEGORIES]},
            "filters": {
                "type": "object",
                "properties": {
                    column: {"type": "string", "enum": ["", *values]}
                    for column, values in options.items()
                },
                "required": list(CATEGORIES),
                "additionalProperties": False,
            },
        },
        "required": ["metric", "aggregation", "group_by", "filters"],
        "additionalProperties": False,
    }
    system = (
        "Translate the user's question into a query plan for the local AI usage survey. "
        "Return only the JSON object matching the supplied schema. Never write SQL, code, "
        "or invent data. Use a metric only when it is supported by the question. "
        "Use __records__ for counting respondents; otherwise use one of these numeric "
        f"column names: {', '.join(METRICS)}. Use an empty metric if the request is unsupported. "
        "Use count for how many, average for average/typical, sum for total, and max for highest. "
        "Choose group_by only when the question asks for a comparison or breakdown. "
        "Set filters only for values explicitly requested; all other filter values must be empty. "
        "The allowed category values are included in the schema. Do not infer causal relationships. "
        "The question may be in English or Spanish."
    )
    body = {
        "model": model,
        "response_format": {"type": "json_schema", "schema": schema},
        "stream": False,
        "temperature": 0,
        "max_tokens": 384,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
    }
    request = Request(
        "http://127.0.0.1:8081/v1/chat/completions",
        json.dumps(body, ensure_ascii=False).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    with build_opener(ProxyHandler({})).open(request, timeout=90) as response:
        payload = json.loads(response.read())
    try:
        plan = json.loads(payload["choices"][0]["message"]["content"])
        if set(plan) != {"metric", "aggregation", "group_by", "filters"}:
            raise ValueError("The local model returned an invalid query plan.")
        metric = plan["metric"]
        group = plan["group_by"]
        aggregation = plan["aggregation"]
        filters = plan["filters"]
        if metric not in {*METRICS, "__records__"}:
            raise ValueError("The local model could not map that question to a supported measure.")
        if aggregation not in {"count", "average", "sum", "max"}:
            raise ValueError("The local model selected an unsupported operation.")
        if group and group not in CATEGORIES:
            raise ValueError("The local model selected an unsupported grouping.")
        if not isinstance(filters, dict) or set(filters) != set(CATEGORIES):
            raise ValueError("The local model returned an invalid filter plan.")
        for column, value in filters.items():
            if value and value not in options[column]:
                raise ValueError("The local model selected a filter outside the dataset.")
        if metric == "__records__" and aggregation != "count":
            raise ValueError("Respondents can only be counted.")
        return metric, group, {key: value for key, value in filters.items() if value}, aggregation
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("The local model returned an invalid query plan.") from error


def _answer_plan(rows, plan, model):
    metric, group, filters, aggregation = plan
    selected = [row for row in rows if all(row.get(column) == value for column, value in filters.items())]
    label = "Respondents" if metric == "__records__" else METRICS[metric][0]

    def values_for(group_rows):
        if metric == "__records__":
            return [row["User_ID"] for row in group_rows if row.get("User_ID") is not None]
        return [row[metric] for row in group_rows if row.get(metric) is not None]

    def aggregate(group_rows):
        values = values_for(group_rows)
        if not values:
            return None, 0
        if aggregation == "count":
            value = len(values)
        elif aggregation == "sum":
            value = sum(values)
        elif aggregation == "max":
            value = max(values)
        else:
            value = mean(values)
        return round(value, 2), len(values)

    if group:
        grouped = defaultdict(list)
        for row in selected:
            if row.get(group) is not None:
                grouped[row[group]].append(row)
        result_rows = []
        for key, group_rows in grouped.items():
            value, responses = aggregate(group_rows)
            if value is not None:
                result_rows.append({"group": key, "value": value, "responses": responses})
        result_rows.sort(key=lambda item: (-item["value"], _fold(item["group"])))
        if not result_rows:
            raise ValueError("No matching records have a value for that measure.")
        title = f"{label} by {CATEGORIES[group][0].lower()}"
        summary = f"{label}: {_format(result_rows[0]['value'])} for {result_rows[0]['group']} (highest group)."
        chart = [{"label": item["group"], "value": item["value"]} for item in result_rows[:10]]
        columns = [CATEGORIES[group][0], label, "Responses"]
        table = [[item["group"], _format(item["value"]), item["responses"]] for item in result_rows]
    else:
        value, responses = aggregate(selected)
        if value is None:
            raise ValueError("No matching records have a value for that measure.")
        title = label
        summary = f"{label}: {_format(value)} across {responses} responses."
        chart = [{"label": label, "value": value}]
        columns = ["Measure", "Result", "Responses"]
        table = [[label, _format(value), responses]]

    scope = ", ".join(f"{CATEGORIES[key][0]}: {value}" for key, value in filters.items())
    return {
        "title": title,
        "summary": summary,
        "filters": scope or "All available records",
        "columns": columns,
        "rows": table,
        "chart": chart,
        "chartLabel": label,
        "matched": len(selected),
        "available": len(rows),
        "mode": f"Local LLM · {model}",
    }


def answer(question, rows, model=None):
    question = question.strip()
    if not question or len(question) > 500:
        raise ValueError("Enter a question of 1–500 characters.")
    if model:
        return _answer_plan(rows, _llm_plan(question, rows, model), model)
    result = _answer_rules(question, rows)
    result["mode"] = "Rules"
    return result
