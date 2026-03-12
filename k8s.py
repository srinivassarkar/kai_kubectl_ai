# k8s.py
# Runs kubectl commands and returns their output as plain text.
# One function per data type. No classes. No parsing.

import subprocess


def run_command(command):
    """
    Runs a shell command and returns output as a string.
    timeout=30 prevents hanging forever if the cluster connection drops.
    """
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"

    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s — is your cluster reachable? Try: kubectl get nodes"


def get_pod_describe(pod_name, namespace="default"):
    """
    kubectl describe pod <pod_name>
    Most information-rich command for pod diagnosis.
    Shows image, restart count, resource limits, conditions, and events.
    """
    return run_command(["kubectl", "describe", "pod", pod_name, "-n", namespace])


def get_pod_logs(pod_name, namespace="default"):
    """
    Gets logs from the pod, trying --previous first.
    --previous = logs from the last crashed container run.
    That's where the actual error message usually lives.
    """
    logs = run_command(["kubectl", "logs", pod_name, "--previous", "-n", namespace])

    if "Error" in logs or logs.strip() == "":
        logs = run_command(["kubectl", "logs", pod_name, "-n", namespace])

    return logs if logs.strip() else "No logs available for this pod."


def get_pod_events(pod_name, namespace="default"):
    """
    Gets events filtered to only those mentioning this specific pod.
    Filtering by pod_name only (not "Warning") prevents unrelated
    cluster warnings from polluting the AI's context.
    """
    all_events = run_command([
        "kubectl", "get", "events",
        "-n", namespace,
        "--sort-by=.lastTimestamp"
    ])

    relevant_lines = [
        line for line in all_events.splitlines()
        if pod_name in line
    ]

    return "\n".join(relevant_lines) if relevant_lines else "No events found for this pod."


def get_deployment_describe(deployment_name, namespace="default"):
    """kubectl describe deployment <name>"""
    return run_command(["kubectl", "describe", "deployment", deployment_name, "-n", namespace])


def get_deployment_pods(deployment_name, namespace="default"):
    """
    Gets all pods in the namespace and lets the AI find the relevant ones.
    We don't filter by label selector because deployment labels vary wildly
    in real clusters (app=X vs app.kubernetes.io/name=X etc).
    Safer to give the AI the full list — it matches by deployment name
    from the describe output it already has.
    """
    return run_command([
        "kubectl", "get", "pods",
        "-n", namespace,
        "-o", "wide"
    ])


def get_rollout_status(deployment_name, namespace="default"):
    """kubectl rollout status deployment/<name>"""
    return run_command([
        "kubectl", "rollout", "status",
        f"deployment/{deployment_name}",
        "-n", namespace
    ])


def get_cluster_nodes():
    """All nodes and their status."""
    return run_command(["kubectl", "get", "nodes", "-o", "wide"])


def get_all_pods():
    """All pods across all namespaces."""
    return run_command(["kubectl", "get", "pods", "-A", "-o", "wide"])


def get_cluster_events():
    """
    Warning events across the cluster, sorted by time.
    Normal events (Scheduled, Pulled, Started) are noise.
    Warnings are where problems live.
    """
    return run_command([
        "kubectl", "get", "events",
        "-A",
        "--field-selector", "type=Warning",
        "--sort-by=.lastTimestamp"
    ])


def is_cluster_reachable():
    """
    Quick check used by 'kai doctor'.
    Returns True if kubectl can reach the cluster, False if not.
    """
    result = run_command(["kubectl", "get", "nodes", "--request-timeout=5s"])
    return "Error" not in result and result.strip() != ""