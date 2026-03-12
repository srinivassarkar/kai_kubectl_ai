# kai — kubectl AI

A local AI assistant that debugs Kubernetes for you.
No API keys. No cloud. Runs entirely on your machine.

## Quick Demo

```bash
$ kubectl get pods
NAME                       READY   STATUS             RESTARTS
nginx-broken-image-abc     0/1     ImagePullBackOff   0
nginx-crashloop-def        0/1     CrashLoopBackOff   4

$ kai diagnose pod nginx-broken-image-abc
→ Collecting describe output...
→ Collecting logs...
→ Collecting events...
⠋ AI analyzing pod...

Problem:
  ImagePullBackOff — image nginx:this-tag-does-not-exist not found

Why it happens:
  The image tag doesn't exist in Docker Hub. Kubernetes received
  a 404 and is backing off before retrying.

Fix command:
  kubectl set image deployment/nginx-broken-image nginx=nginx:latest
```

## Commands

```bash
kai doctor                         # check environment setup
kai diagnose pod <n>               # diagnose a failing pod
kai diagnose deployment <n>        # diagnose a failing deployment
kai logs <n>                       # explain pod logs
kai explain describe pod <n>       # explain kubectl describe output
kai analyze cluster                # full cluster health report
kai version

# All commands also work as kubectl plugin:
kubectl ai diagnose pod <n>
kubectl ai analyze cluster
```

## Requirements

- Python 3.9+
- Ollama: `sudo systemctl start ollama`
- Mistral model: `ollama pull mistral`
- kubectl connected to a cluster
- Docker + Kind for local testing

## Setup

```bash
git clone https://github.com/srinivassarkar/kubectl-ai
cd kubectl-ai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
chmod +x kai kubectl-ai
sudo ln -s $(pwd)/kai /usr/local/bin/kai
sudo ln -s $(pwd)/kubectl-ai /usr/local/bin/kubectl-ai
kai doctor
```

## First run note

First AI response takes 30–40 seconds (model loading into RAM).
Subsequent responses: 10–20 seconds.

## Stack

Python · Typer · Rich · Ollama · Mistral 7B · Kind · kubectl

## License

MIT