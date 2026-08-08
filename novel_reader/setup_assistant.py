from __future__ import annotations

from dataclasses import dataclass
import sys

from novel_reader.system_diagnostics import (
    CheckResult,
    DistroInfo,
    format_doctor_report,
    overall_ok,
    run_diagnostics,
)


@dataclass(slots=True)
class SetupPlan:
    distro: DistroInfo
    required_commands: list[str]
    optional_commands: list[str]


def build_setup_plan(
    distro: DistroInfo,
    results: list[CheckResult],
) -> SetupPlan:
    required: list[str] = []
    optional: list[str] = []

    for item in results:
        if item.ok or not item.suggestion:
            continue
        target = required if item.required else optional
        if item.suggestion not in target:
            target.append(item.suggestion)

    return SetupPlan(
        distro=distro,
        required_commands=required,
        optional_commands=optional,
    )


def format_setup_plan(plan: SetupPlan) -> str:
    lines = [
        "Setup assistido do Novel Reader",
        "",
        "Nada será instalado automaticamente.",
        "Os comandos abaixo são apenas sugestões para você revisar e executar.",
        "",
    ]

    if plan.required_commands:
        lines.append("Dependências obrigatórias:")
        for command in plan.required_commands:
            lines.append(f"  {command}")
        lines.append("")
    else:
        lines.append("✓ Dependências obrigatórias parecem prontas.")
        lines.append("")

    if plan.optional_commands:
        lines.append("Recursos opcionais:")
        for command in plan.optional_commands:
            lines.append(f"  {command}")
        lines.append("")

    lines.append(
        "Depois de instalar o que desejar, execute novamente: "
        "novel-reader-cli --doctor"
    )
    return "\n".join(lines)


def run_setup(*, ansi: bool = True) -> int:
    distro, results = run_diagnostics()
    print(format_doctor_report(distro, results, ansi=ansi))
    print()
    print(format_setup_plan(build_setup_plan(distro, results)))
    return 0 if overall_ok(results) else 2
