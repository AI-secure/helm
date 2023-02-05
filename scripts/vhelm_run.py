from dataclasses import dataclass
from typing import List, Optional, Tuple
import argparse
import dacite
import os

from helm.common.general import parse_hocon, ensure_directory_exists
from helm.common.hierarchical_logger import hlog, htrack
from helm.proxy.models import get_models_with_tag, TEXT_TO_IMAGE_MODEL_TAG, Model


DEFAULT_NLP_RUN: str = "-a crfm_benchmarking -c 4 --memory 32g -w /u/scr/nlp/crfm/benchmarking/benchmarking"
DEFAULT_NLP_RUN_CPU_ARGS: str = f"{DEFAULT_NLP_RUN} -g 0 --exclude john17"
DEFAULT_NLP_RUN_GPU_ARGS: str = f"{DEFAULT_NLP_RUN} -g 1 --exclude jagupard[10-20]"
DEFAULT_HELM_ARGS: str = (
    "--num-train-trials 1 --local -n 1 --mongo-uri='mongodb://crfm-benchmarking:kindling-vespers@john13/crfm-models'"
)


# Copied from run_entry.py. Using the method directly results in an error.
@dataclass(frozen=True)
class RunEntry:
    """Represents something that we want to run."""

    # Gets expanded into a list of `RunSpec`s.
    description: str

    # Priority for this run spec (1 is highest priority, 5 is lowest priority)
    priority: int

    # Additional groups to add to the run spec
    groups: Optional[List[str]]


@dataclass(frozen=True)
class RunEntries:
    entries: List[RunEntry]


def merge_run_entries(run_entries1: RunEntries, run_entries2: RunEntries):
    return RunEntries(run_entries1.entries + run_entries2.entries)


def read_run_entries(paths: List[str]) -> RunEntries:
    """Read a HOCON file `path` and return the `RunEntry`s."""
    run_entries = RunEntries([])
    for path in paths:
        with open(path) as f:
            raw = parse_hocon(f.read())
        run_entries = merge_run_entries(run_entries, dacite.from_dict(RunEntries, raw))
        hlog(f"Read {len(run_entries.entries)} run entries from {path}")
    return run_entries


@htrack(None)
def queue_jobs(conf_path: str, suite: str, priority: int = 2, dry_run: bool = False):
    # Create a run directory at benchmark_output/runs/<suite>
    suite_path: str = os.path.join("benchmark_output", "runs", suite)
    ensure_directory_exists(suite_path)
    logs_path: str = os.path.join(suite_path, "logs")
    ensure_directory_exists(logs_path)
    confs_path: str = os.path.join(suite_path, "confs")
    ensure_directory_exists(confs_path)

    # Read the RunSpecs and split each RunSpec into it's own file
    confs: List[Tuple[str, str]] = []
    run_entries = read_run_entries([conf_path])
    for entry in run_entries.entries:
        if entry.priority > priority:
            continue

        description: str = entry.description
        conf_path = os.path.join(confs_path, f"{description}.conf")
        with open(conf_path, "w") as f:
            f.write(f'entries: [{{description: "{description}", priority: {priority}}}]')
        confs.append((description, conf_path))

    # Run all models on all RunSpecs
    models: List[Model] = get_models_with_tag(TEXT_TO_IMAGE_MODEL_TAG)
    for model in models:
        for description, conf_path in confs:
            # Construct command here
            job_name: str = f"{model.engine}_{description}"
            log_path: str = os.path.join(logs_path, f"{job_name}.log")
            command: str = (
                f"nlprun {DEFAULT_NLP_RUN_GPU_ARGS} --job-name {job_name} 'helm-run {DEFAULT_HELM_ARGS} "
                f"--suite {suite} --conf-paths {conf_path} --models-to-run {model.name} --priority {priority} "
                f"> {log_path} 2>&1'"
            )
            hlog(command)
            if not dry_run:
                os.system(command)

    # Inform what to run next: summarize + copy
    hlog("\n\nTo check the logs locally:\n")
    hlog(
        f"scp -r tonyhlee@scdt.stanford.edu:/nlp/scr2/nlp/crfm/benchmarking/benchmarking/"
        f"benchmark_output/runs/{suite}/logs ."
    )
    hlog(f"python3 scripts/vhelm_run.py --check")
    hlog("\n\nRun the following command once all the runs complete:\n")
    command: str = (
        f"helm-summarize --suite {suite} > {os.path.join(logs_path, 'summarize.log')} 2>&1 && "
        f"sh scripts/create-www-vhelm.sh {suite} > {os.path.join(logs_path, 'upload.log')} 2>&1"
    )
    hlog(f"nlprun {DEFAULT_NLP_RUN_CPU_ARGS} --job-name {suite}-summarize-upload '{command}'\n")


@htrack(None)
def check(suite: str):
    suite_path: str = os.path.join("benchmark_output", "runs", suite)
    logs_path: str = os.path.join(suite_path, "logs")

    for log_file in os.listdir(logs_path):
        if not log_file.endswith("log"):
            continue

        run_spec: str = log_file.replace(".log", "")
        log_path: str = os.path.join(logs_path, log_file)
        with open(log_path, "r") as f:
            log_content: str = f.read()
            if "Done.\n" not in log_content:
                hlog(f"Check on {run_spec}")
    hlog("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--conf-path",
        help="Where to read RunSpecs to run from",
        default="src/helm/benchmark/presentation/run_specs_vhelm.conf",
    )
    parser.add_argument("--suite", help="Name of the suite", default="vhelm")
    parser.add_argument("--priority", default=2)
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=None,
        help="Skips execution.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        default=None,
        help="Checks logs",
    )
    args = parser.parse_args()

    if args.check:
        check(args.suite)
    else:
        queue_jobs(args.conf_path, args.suite, args.priority, args.dry_run)
