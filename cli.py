# cli.py
# Defines CLI commands using Typer.
# Each @app.command() function = one command you can type.

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import k8s
import ai

app = typer.Typer(
    name="kai",
    help="kubectl AI — local AI assistant for Kubernetes debugging",
    add_completion=False
)

console = Console()


def check_connection():
    """
    Runs before every command that calls the AI.
    Fails fast with a clear message if Ollama isn't running.
    """
    if not ai.check_ollama():
        console.print("[red]✗ Ollama is not running.[/red]")
        console.print("  Start it: [yellow]sudo systemctl start ollama[/yellow]")
        raise typer.Exit(1)

    if not ai.check_model():
        console.print(f"[red]✗ Mistral model not found in Ollama.[/red]")
        console.print("  Install it: [yellow]ollama pull mistral[/yellow]")
        raise typer.Exit(1)


def print_diagnosis(title, content):
    """Prints AI response in a cyan bordered panel."""
    console.print()
    console.print(Panel(
        content,
        title=f"[bold cyan] KAI — {title}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    ))
    console.print()


def print_status(message):
    """Yellow arrow status line during data collection."""
    console.print(f"[yellow]→[/yellow] {message}")


@app.command()
def diagnose(
    resource_type: str = typer.Argument(..., help="Resource type (pod or deployment)"),
    name: str = typer.Argument(..., help="Name of the pod or deployment"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace")
):
    """
    Diagnose a failing pod or deployment.

    Examples:
        kai diagnose pod nginx-abc123
        kai diagnose deployment nginx-deploy
        kai diagnose pod nginx --namespace staging
    """
    check_connection()

    if resource_type.lower() == "pod":
        console.print(f"\n[bold]Diagnosing pod:[/bold] [cyan]{name}[/cyan]")
        print_status("Collecting describe output...")
        describe = k8s.get_pod_describe(name, namespace)
        print_status("Collecting logs...")
        logs = k8s.get_pod_logs(name, namespace)
        print_status("Collecting events...")
        events = k8s.get_pod_events(name, namespace)

        with console.status("[bold green]AI analyzing pod...[/bold green]"):
            result = ai.diagnose_pod(name, describe, logs, events)
        print_diagnosis(f"Pod Diagnosis: {name}", result)

    elif resource_type.lower() == "deployment":
        console.print(f"\n[bold]Diagnosing deployment:[/bold] [cyan]{name}[/cyan]")
        print_status("Collecting describe output...")
        describe = k8s.get_deployment_describe(name, namespace)
        print_status("Collecting pod status...")
        pods = k8s.get_deployment_pods(name, namespace)
        print_status("Checking rollout status...")
        rollout = k8s.get_rollout_status(name, namespace)

        with console.status("[bold green]AI analyzing deployment...[/bold green]"):
            result = ai.diagnose_deployment(name, describe, pods, rollout)
        print_diagnosis(f"Deployment Diagnosis: {name}", result)

    else:
        console.print(f"[red]Unknown resource type:[/red] {resource_type}")
        console.print("Use: pod or deployment")
        raise typer.Exit(1)


@app.command()
def logs(
    name: str = typer.Argument(..., help="Pod name"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace")
):
    """
    Explain what a pod's logs mean in plain English.

    Examples:
        kai logs nginx-abc123
        kai logs nginx-abc123 --namespace staging
    """
    check_connection()
    console.print(f"\n[bold]Explaining logs for pod:[/bold] [cyan]{name}[/cyan]")
    print_status("Collecting logs...")
    log_output = k8s.get_pod_logs(name, namespace)

    with console.status("[bold green]AI reading logs...[/bold green]"):
        result = ai.explain_logs(name, log_output)
    print_diagnosis(f"Log Explanation: {name}", result)


@app.command()
def explain(
    resource_type: str = typer.Argument(..., help="Resource type (describe)"),
    target_type: str = typer.Argument(..., help="Kubernetes resource type (pod, deployment, node)"),
    name: str = typer.Argument(..., help="Resource name"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace")
):
    """
    Explain kubectl describe output in plain English.

    Examples:
        kai explain describe pod nginx-abc123
        kai explain describe deployment nginx-deploy
        kai explain describe node worker-1
    """
    check_connection()

    if resource_type.lower() != "describe":
        console.print(f"[red]Unknown subcommand:[/red] {resource_type}")
        console.print("Currently supported: describe")
        console.print("Example: kai explain describe pod nginx")
        raise typer.Exit(1)

    console.print(f"\n[bold]Explaining:[/bold] kubectl describe {target_type} [cyan]{name}[/cyan]")
    print_status(f"Running kubectl describe {target_type} {name}...")

    describe_output = k8s.run_command(["kubectl", "describe", target_type, name, "-n", namespace])

    with console.status("[bold green]AI explaining output...[/bold green]"):
        result = ai.explain_describe(target_type, name, describe_output)

    print_diagnosis(f"Describe Explanation: {target_type}/{name}", result)


@app.command()
def analyze(
    target: str = typer.Argument(..., help="What to analyze (cluster)")
):
    """
    Analyze the entire cluster and report health status.

    Example:
        kai analyze cluster
    """
    check_connection()

    if target.lower() == "cluster":
        console.print(f"\n[bold]Analyzing cluster health...[/bold]")
        print_status("Collecting node status...")
        nodes = k8s.get_cluster_nodes()
        print_status("Collecting all pod status...")
        pods = k8s.get_all_pods()
        print_status("Collecting warning events...")
        events = k8s.get_cluster_events()

        with console.status("[bold green]AI analyzing cluster...[/bold green]"):
            result = ai.analyze_cluster(nodes, pods, events)
        print_diagnosis("Cluster Health Analysis", result)

    else:
        console.print(f"[red]Unknown target:[/red] {target}")
        console.print("Currently supported: cluster")
        raise typer.Exit(1)


@app.command()
def doctor():
    """
    Check that your environment is set up correctly.

    Verifies:
        - Ollama is running
        - Mistral model is installed
        - kubectl is reachable
        - Cluster is accessible

    Example:
        kai doctor
    """
    console.print("\n[bold]Running environment checks...[/bold]\n")

    # Use Rich Table for aligned output
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()

    all_good = True

    # Check 1 — Ollama
    if ai.check_ollama():
        table.add_row("[green]✔[/green]", "Ollama is running")
    else:
        table.add_row("[red]✗[/red]", "Ollama is NOT running — run: sudo systemctl start ollama")
        all_good = False

    # Check 2 — Mistral model
    if ai.check_model():
        table.add_row("[green]✔[/green]", "Mistral model is installed")
    else:
        table.add_row("[red]✗[/red]", "Mistral not found — run: ollama pull mistral")
        all_good = False

    # Check 3 — kubectl reachable
    import subprocess
    kubectl_check = subprocess.run(
        ["kubectl", "version", "--client", "--short"],
        capture_output=True, text=True, timeout=5
    )
    if kubectl_check.returncode == 0:
        table.add_row("[green]✔[/green]", "kubectl is installed")
    else:
        table.add_row("[red]✗[/red]", "kubectl not found — install from k8s.io/docs")
        all_good = False

    # Check 4 — Cluster accessible
    if k8s.is_cluster_reachable():
        table.add_row("[green]✔[/green]", "Cluster is accessible")
    else:
        table.add_row("[yellow]⚠[/yellow]", "Cluster not reachable — check kubeconfig or start kind cluster")

    console.print(table)
    console.print()

    if all_good:
        console.print("[bold green]All checks passed. kai is ready.[/bold green]")
    else:
        console.print("[bold red]Some checks failed. Fix the issues above before running kai.[/bold red]")


@app.command()
def version():
    """Show kai version."""
    console.print("kai version 1.0.0")
    console.print("kubectl AI — local Kubernetes debugging assistant")
    console.print("Model: Mistral 7B via Ollama")


if __name__ == "__main__":
    app()