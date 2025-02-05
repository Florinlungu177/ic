import logging
import os
import shutil
from os import environ
from os import getenv
from os import path
from typing import Optional

from ci import cwd
from ci import ENV
from ci import flatten
from ci import mkdir_p
from ci import sh
from ci import show_sccache_stats

CANISTERS = [
    "cycles-minting-canister",
    "genesis-token-canister",
    "governance-canister",
    "governance-mem-test-canister",
    "identity-canister",
    "inter_canister_error_handling",
    "json",
    "ledger-archive-node-canister",
    "ledger-canister",
    "mem-utils-test-canister",
    "memory-test-canister",
    "nan_canonicalized",
    "nns-ui-canister",
    "panics",
    "pmap_canister",
    "registry-canister",
    "root-canister",
    "sns-governance-canister",
    "stable",
    "statesync-test-canister",
    "test-notified",
    "time",
    "upgrade-test-canister",
    "wasm",
    "xnet-test-canister",
]

CANISTER_COPY_LIST = {"cow_safety.wasm": "rs/tests/src", "counter.wat": "rs/workload_generator/src"}

artifact_ext = getenv("ARTIFACT_EXT", "")
default_artifacts_dir = f"{ENV.top}/artifacts/canisters{artifact_ext}"


def _optimize_wasm(artifacts_dir, bin):
    src_filename = f"{ENV.cargo_target_dir}/wasm32-unknown-unknown/release/{bin}.wasm"
    if path.exists(src_filename):
        sh("ic-cdk-optimizer", "-o", f"{artifacts_dir}/{bin}.wasm", src_filename)
    else:
        raise Exception(f"ERROR: target canister Wasm binary does not exist: {src_filename}")


def _build_with_features(bin_name, features, target_bin_name: Optional[str] = None):
    target_bin_name = f"{bin_name}_{features}" if target_bin_name is None else target_bin_name
    sh(
        "cargo",
        "build",
        "--target",
        "wasm32-unknown-unknown",
        "--release",
        "--bin",
        bin_name,
        "--features",
        features,
    )
    os.rename(
        f"{ENV.cargo_target_dir}/wasm32-unknown-unknown/release/{bin_name}.wasm",
        f"{ENV.cargo_target_dir}/wasm32-unknown-unknown/release/{target_bin_name}.wasm",
    )


def run(artifacts_dir=default_artifacts_dir):
    mkdir_p(artifacts_dir)

    # TODO: get rid of this usage of git revision
    environ["VERSION"] = ENV.build_id

    # Make sure git-related non-determinism does't get through.
    if ENV.is_gitlab:
        date = sh("date", capture=True)
        sh(
            "git",
            "-c",
            "user.name=Gitlab CI",
            "-c",
            "user.email=infra+gitlab-automation@dfinity.org",
            "commit",
            "--allow-empty",
            "-m",
            f"Non-determinism detection commit at {date}",
        )

    with cwd("rs"):
        _build_with_features("ledger-canister", "notify-method")
        _build_with_features("governance-canister", "test")

        sh("cargo", "build", "--target", "wasm32-unknown-unknown", "--release", "--bin", "ledger-archive-node-canister")
        _optimize_wasm(artifacts_dir, "ledger-archive-node-canister")

        sh(
            "cargo",
            "build",
            "--target",
            "wasm32-unknown-unknown",
            "--release",
            *flatten([["--bin", b] for b in CANISTERS]),
        )

    with cwd("rs/nns/handlers/lifeline"):
        sh("cargo", "build", "--target", "wasm32-unknown-unknown")
        sh("ic-cdk-optimizer", "-o", f"{artifacts_dir}/lifeline.wasm", "gen/lifeline.wasm")

    logging.info("Building of Wasm canisters finished")

    for canister in ["ledger-canister_notify-method", "governance-canister_test"] + CANISTERS:
        _optimize_wasm(artifacts_dir, canister)

    for can, filepath in CANISTER_COPY_LIST.items():
        src_filename = f"{filepath}/{can}"
        if can.endswith(".wasm"):
            sh("ic-cdk-optimizer", "-o", f"{artifacts_dir}/{can}", f"{ENV.top}/{src_filename}")
        elif can.endswith(".wat"):
            shutil.copyfile(f"{ENV.top}/{src_filename}", f"{artifacts_dir}/{can}")
        else:
            logging.error(f"unknown (not .wat or .wasm) canister type: {src_filename}")
            exit(1)

    sh(f"sha256sum {artifacts_dir}/*", shell=True)
    sh(f"pigz -f --no-name {artifacts_dir}/*", shell=True)

    if ENV.is_gitlab:
        sh("gitlab-ci/src/artifacts/openssl-sign.sh", f"{ENV.top}/artifacts/canisters{artifact_ext}")

    show_sccache_stats()
