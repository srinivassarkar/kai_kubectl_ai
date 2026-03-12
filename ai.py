# ai.py
# Talks to Ollama's HTTP API.
# Build prompt → truncate if needed → send → return response.

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_HEALTH_URL = "http://localhost:11434"
MODEL = "mistral"

# Safety limit: Mistral has a context window limit.
# Huge logs (thousands of lines) slow responses and can overflow the context.
# 12000 characters is roughly 3000 tokens — plenty for diagnosis.
MAX_CHARS = 12000


def truncate(text):
    """
    Truncates text to MAX_CHARS if it's too long.
    Adds a [truncated] marker so the AI knows it's seeing partial data.

    Why does this matter?
    If someone runs 'kai logs huge-pod' and the logs are 50,000 lines,
    sending the full thing to Mistral would be very slow and might
    exceed the model's context window entirely. We cut it safely.
    """
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + "\n\n[output truncated — showing first 12000 characters]"
    return text


def check_ollama():
    """
    Checks if Ollama is reachable.
    Called before every command so we fail fast with a clear message
    instead of waiting 120s for a timeout deep in the code.
    """
    try:
        requests.get(OLLAMA_HEALTH_URL, timeout=2)
        return True
    except Exception:
        return False


def check_model():
    """
    Checks if the mistral model is available in Ollama.
    Returns True if available, False if it needs to be pulled.
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = response.json().get("models", [])
        return any("mistral" in m.get("name", "") for m in models)
    except Exception:
        return False


def ask_ollama(prompt):
    """
    Sends a prompt to Ollama and returns the full response as a string.
    stream=False = wait for complete response (simpler for CLI tools).
    """
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["response"]

    except requests.exceptions.ConnectionError:
        return (
            "Error: Cannot connect to Ollama.\n"
            "Check status: sudo systemctl status ollama\n"
            "Start it:     sudo systemctl start ollama"
        )
    except requests.exceptions.Timeout:
        return "Error: Ollama timed out. Model may still be loading — try again in 30 seconds."
    except Exception as e:
        # Check if it's a missing model error
        if "model" in str(e).lower() or "not found" in str(e).lower():
            return (
                f"Error: Model '{MODEL}' not found in Ollama.\n\n"
                f"Run this to install it:\n"
                f"  ollama pull {MODEL}"
            )
        return f"Unexpected error: {str(e)}"


def build_pod_prompt(pod_name, describe_output, logs_output, events_output):
    """
    Builds the pod diagnosis prompt with forced output format.

    "senior Kubernetes SRE debugging production clusters" — this framing
    makes the model respond with more confidence and specificity.
    Models mirror the authority level you give them in the system role.

    Forced format (Problem / Why / Fix) ensures every response is
    scannable and consistent — no essays, no questions back.
    """
    return f"""You are a senior Kubernetes SRE debugging production clusters. Be concise and specific.

Diagnose this pod and respond ONLY in this exact format:

Problem:
[one sentence — name the exact error: ImagePullBackOff, CrashLoopBackOff, OOMKilled, etc.]

Why it happens:
[2-3 sentences of root cause in plain English]

Fix command:
[exact kubectl command or minimal YAML change to resolve it]

---

Pod name: {pod_name}

kubectl describe pod:
{truncate(describe_output)}

Pod logs:
{truncate(logs_output)}

Pod events:
{truncate(events_output)}
"""


def build_deployment_prompt(deployment_name, describe_output, pods_output, rollout_output):
    return f"""You are a senior Kubernetes SRE debugging production clusters. Be concise and specific.

Diagnose this deployment and respond ONLY in this exact format:

Problem:
[one sentence — healthy or what is wrong]

Why it happens:
[2-3 sentences referencing specific fields from the data below]

Fix command:
[exact kubectl command or YAML change]

---

Deployment: {deployment_name}

kubectl describe deployment:
{truncate(describe_output)}

Pods in namespace:
{truncate(pods_output)}

Rollout status:
{truncate(rollout_output)}
"""


def build_logs_prompt(pod_name, logs_output):
    return f"""You are a senior Kubernetes SRE debugging production clusters. Be concise and specific.

Explain these logs and respond ONLY in this exact format:

What is happening:
[plain English summary of what the logs show]

Is anything wrong:
[yes or no — if yes, what specifically and why]

Next step:
[one concrete action to take]

---

Pod name: {pod_name}

Logs:
{truncate(logs_output)}
"""


def build_cluster_prompt(nodes_output, pods_output, events_output):
    return f"""You are a senior Kubernetes SRE debugging production clusters. Be concise and specific.

Analyze this cluster and respond ONLY in this exact format:

Node health:
[are all nodes Ready? list any that aren't]

Problem pods:
[each non-Running/non-Completed pod with its issue — or "None"]

Event patterns:
[repeated warnings or patterns — or "None"]

Top 3 fixes (priority order):
1. [most urgent]
2. [second]
3. [third]

---

Nodes:
{truncate(nodes_output)}

All pods:
{truncate(pods_output)}

Warning events:
{truncate(events_output)}
"""


def build_explain_describe_prompt(resource_type, name, describe_output):
    """
    Explains raw kubectl describe output in plain English.
    No diagnosis, no fix — just "what am I looking at?"

    This is useful for anyone learning Kubernetes who wants to understand
    what kubectl describe is actually telling them, field by field.
    """
    return f"""You are a senior Kubernetes SRE and a patient teacher.

A developer has run 'kubectl describe {resource_type} {name}' and wants to understand what the output means.

Explain this output in plain English. Respond ONLY in this exact format:

What this shows:
[2-3 sentence overview of what this resource is and its current state]

Key fields to notice:
[explain 3-5 of the most important fields in the output — what they mean and why they matter]

Anything concerning:
[flag anything that looks wrong or unusual — or "Nothing concerning" if it all looks healthy]

---

kubectl describe {resource_type} {name}:
{truncate(describe_output)}
"""


# Functions cli.py calls — one per command

def diagnose_pod(pod_name, describe, logs, events):
    return ask_ollama(build_pod_prompt(pod_name, describe, logs, events))

def diagnose_deployment(deployment_name, describe, pods, rollout):
    return ask_ollama(build_deployment_prompt(deployment_name, describe, pods, rollout))

def explain_logs(pod_name, logs):
    return ask_ollama(build_logs_prompt(pod_name, logs))

def analyze_cluster(nodes, pods, events):
    return ask_ollama(build_cluster_prompt(nodes, pods, events))

def explain_describe(resource_type, name, describe_output):
    return ask_ollama(build_explain_describe_prompt(resource_type, name, describe_output))