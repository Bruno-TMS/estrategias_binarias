#!/usr/bin/env python3
"""Script utilitário para consolidar o código-fonte do projeto em um único arquivo."""

from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "dump_projeto.txt"

TARGET_DIRS = ["api", "core", "deriv", "services", "utils"]
TARGET_ROOT_FILES = ["main.py", "ui_app.py", "requirements.txt", ".env.example"]

IGNORED_DIRS = {".git", ".venv", "__pycache__", "logs", "scripts"}
IGNORED_FILES = {
    ".env",
    "dump_projeto.txt",
    "desenvolvimento_projeto.txt",
    "trading_memory.db",
    "knv.csv",
    "journal.csv",
    "saida_terminal.txt",
}
IGNORED_EXTENSIONS = {".pyc", ".pyo", ".pyd", ".so", ".log"}


def is_ignored(path: Path) -> bool:
    """Verifica se um diretório ou arquivo deve ser ignorado."""
    if any(part in IGNORED_DIRS for part in path.parts):
        return True
    if path.name in IGNORED_FILES:
        return True
    if path.suffix in IGNORED_EXTENSIONS:
        return True
    if path.name.startswith(".env") and path.name != ".env.example":
        return True
    return False


def collect_files() -> list[Path]:
    """Coleta e ordena todos os arquivos a serem incluídos no dump."""
    files: list[Path] = []

    # Arquivos da raiz
    for filename in TARGET_ROOT_FILES:
        file_path = PROJECT_ROOT / filename
        if file_path.is_file() and not is_ignored(file_path):
            files.append(file_path)

    # Pastas do projeto
    for dir_name in TARGET_DIRS:
        dir_path = PROJECT_ROOT / dir_name
        if not dir_path.is_dir():
            continue
        for path in sorted(dir_path.rglob("*")):
            if path.is_file() and not is_ignored(path):
                files.append(path)

    return sorted(files, key=lambda p: str(p.relative_to(PROJECT_ROOT)))


def generate_dump(output_path: Path = OUTPUT_FILE) -> int:
    """Gera o arquivo de dump consolidando o conteúdo dos arquivos."""
    files = collect_files()
    total_files = len(files)

    with open(output_path, "w", encoding="utf-8") as out:
        out.write("================================================================================\n")
        out.write(f'Documento criado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}\n\n')
        out.write(f"DUMP DO PROJETO - ESTRATÉGIAS BINÁRIAS\n")
        out.write(f"Total de arquivos incluídos: {total_files}\n")
        out.write("================================================================================\n\n")

        for file_path in files:
            rel_path = file_path.relative_to(PROJECT_ROOT)
            out.write("=" * 80 + "\n")
            out.write(f"ARQUIVO: {rel_path}\n")
            out.write("=" * 80 + "\n")

            try:
                content = file_path.read_text(encoding="utf-8")
                out.write(content)
                if not content.endswith("\n"):
                    out.write("\n")
            except Exception as exc:
                out.write(f"[Erro ao ler arquivo {rel_path}: {exc}]\n")

            out.write("-" * 80 + "\n")
            out.write(f"FIM DO ARQUIVO: {rel_path}\n")
            out.write("=" * 80 + "\n\n")

    return total_files


def main():
    print(f"Gerando dump do projeto a partir de: {PROJECT_ROOT}")
    total = generate_dump(OUTPUT_FILE)
    rel_output = OUTPUT_FILE.relative_to(PROJECT_ROOT)
    print(f"Dump concluído com sucesso!")
    print(f"Arquivo gerado: {rel_output}")
    print(f"Total de arquivos consolidados: {total}")


if __name__ == "__main__":
    main()
