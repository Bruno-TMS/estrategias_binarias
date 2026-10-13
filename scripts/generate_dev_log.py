#!/usr/bin/env python3
"""Script de Registro Incremental do Histórico de Desenvolvimento do Projeto.

Registra interações, pedidos e relatórios de execução no arquivo 'desenvolvimento_projeto.txt'
localizado na raiz do repositório, garantindo inserção incremental no topo (mais recente primeiro)
e preservação integral de todo o histórico pré-existente.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_FILE = PROJECT_ROOT / "desenvolvimento_projeto.txt"

DIVIDER_EQUALS = "=" * 80
DIVIDER_DASHES = "-" * 80

HEADER_BANNER = (
    f"{DIVIDER_EQUALS}\n"
    "HISTÓRICO CONSOLIDADO DE DESENVOLVIMENTO DO PROJETO\n"
    "Última Atualização: {timestamp_utc}\n"
    f"{DIVIDER_EQUALS}\n\n"
)

HEADER_MARKER = "HISTÓRICO CONSOLIDADO DE DESENVOLVIMENTO DO PROJETO"


def get_current_utc_timestamp() -> str:
    """Retorna o timestamp atual formatado em UTC ('YYYY-MM-DD HH:MM:SS UTC')."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def format_log_entry(timestamp_str: str, pedido: str, resposta: str) -> str:
    """Formata um bloco individual de registro conforme o padrão canônico."""
    cleaned_pedido = pedido.strip() if pedido else "[Nenhum texto informado]"
    cleaned_resposta = resposta.strip() if resposta else "[Nenhum relatório informado]"

    lines = [
        DIVIDER_EQUALS,
        f"[REGISTRO DE DESENVOLVIMENTO - {timestamp_str}]",
        DIVIDER_DASHES,
        "PEDIDO (SENHOR SUPREMO):",
        "",
        cleaned_pedido,
        "",
        "RESPOSTA / RELATÓRIO DE EXECUÇÃO (ANTIGRAVITY):",
        "",
        cleaned_resposta,
        DIVIDER_EQUALS,
    ]
    return "\n".join(lines)


def extract_existing_history(content: str) -> str:
    """Extrai as entradas anteriores do log removendo o cabeçalho superior antigo."""
    if not content or not content.strip():
        return ""

    if HEADER_MARKER in content:
        idx = content.find("[REGISTRO DE DESENVOLVIMENTO -")
        if idx != -1:
            start_idx = content.rfind(DIVIDER_EQUALS, 0, idx)
            if start_idx != -1:
                return content[start_idx:].strip()
            return content[idx:].strip()
        return ""

    return content.strip()


def append_dev_log(
    pedido: str,
    resposta: str,
    output_path: Path = DEFAULT_OUTPUT_FILE,
    timestamp: datetime | None = None,
) -> tuple[Path, str]:
    """Insere um novo registro de desenvolvimento no topo do arquivo.

    Preserva integralmente o histórico de entradas existentes e atualiza
    o cabeçalho superior com o timestamp UTC mais recente.
    """
    if timestamp is None:
        ts_dt = datetime.now(timezone.utc)
    else:
        if timestamp.tzinfo is None:
            ts_dt = timestamp.replace(tzinfo=timezone.utc)
        else:
            ts_dt = timestamp.astimezone(timezone.utc)

    ts_str = ts_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    new_entry = format_log_entry(ts_str, pedido, resposta)

    existing_history = ""
    if output_path.is_file():
        try:
            existing_content = output_path.read_text(encoding="utf-8")
            existing_history = extract_existing_history(existing_content)
        except Exception as exc:
            print(f"[AVISO] Não foi possível ler histórico existente em {output_path}: {exc}", file=sys.stderr)

    # Monta novo conteúdo: Cabeçalho com data mais recente + Nova Entrada + Histórico Anterior
    header = HEADER_BANNER.format(timestamp_utc=ts_str)

    if existing_history:
        final_content = f"{header}{new_entry}\n\n{existing_history}\n"
    else:
        final_content = f"{header}{new_entry}\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_content, encoding="utf-8")

    return output_path, ts_str


def parse_arguments() -> argparse.Namespace:
    """Configura e valida os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Gerador e atualizador incremental do log de desenvolvimento do projeto."
    )
    parser.add_argument(
        "--pedido",
        "-p",
        type=str,
        help="Texto da demanda ou instrução do usuário.",
    )
    parser.add_argument(
        "--resposta",
        "-r",
        type=str,
        help="Texto da resposta ou relatório de execução do Antigravity.",
    )
    parser.add_argument(
        "--pedido-file",
        type=Path,
        help="Caminho para arquivo de texto contendo o pedido do usuário.",
    )
    parser.add_argument(
        "--resposta-file",
        type=Path,
        help="Caminho para arquivo de texto contendo a resposta/relatório do Antigravity.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Caminho do arquivo de log (padrão: {DEFAULT_OUTPUT_FILE.name}).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Exibe as entradas de desenvolvimento existentes no arquivo.",
    )
    return parser.parse_args()


def main() -> int:
    """Ponto de entrada principal da CLI."""
    args = parse_arguments()

    if args.list:
        if not args.output.is_file():
            print(f"Arquivo {args.output} ainda não existe.")
            return 0
        content = args.output.read_text(encoding="utf-8")
        print(content)
        return 0

    # Resolução do texto do pedido
    pedido_text = args.pedido or ""
    if args.pedido_file and args.pedido_file.is_file():
        pedido_text = args.pedido_file.read_text(encoding="utf-8")

    # Resolução do texto da resposta
    resposta_text = args.resposta or ""
    if args.resposta_file and args.resposta_file.is_file():
        resposta_text = args.resposta_file.read_text(encoding="utf-8")

    if not pedido_text and not resposta_text:
        # Se executado interativamente sem argumentos e em terminal
        if sys.stdin.isatty():
            print("=== GERADOR DE LOG DE DESENVOLVIMENTO ===")
            print("Digite o texto do PEDIDO (finalize com Ctrl+D ou linha vazia seguida de EOF):")
            try:
                pedido_text = sys.stdin.read()
            except KeyboardInterrupt:
                print("\nOperação cancelada.")
                return 1
            print("\nDigite o texto da RESPOSTA/RELATÓRIO:")
            try:
                resposta_text = input("Resposta resumida: ")
            except KeyboardInterrupt:
                print("\nOperação cancelada.")
                return 1
        else:
            print(
                "Erro: É necessário informar ao menos --pedido ou --resposta (ou seus respectivos arquivos).",
                file=sys.stderr,
            )
            return 1

    try:
        out_file, ts = append_dev_log(
            pedido=pedido_text,
            resposta=resposta_text,
            output_path=args.output,
        )
        rel_path = out_file.relative_to(PROJECT_ROOT) if out_file.is_relative_to(PROJECT_ROOT) else out_file
        print(f"[SUCESSO] Registro de desenvolvimento gravado em: {rel_path}")
        print(f"[TIMESTAMP] {ts}")
        return 0
    except Exception as exc:
        print(f"[ERRO] Falha ao registrar log de desenvolvimento: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

