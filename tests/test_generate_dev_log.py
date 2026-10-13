"""Testes unitários para o script scripts/generate_dev_log.py."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from scripts.generate_dev_log import (
    HEADER_BANNER,
    append_dev_log,
    extract_existing_history,
    format_log_entry,
)


class TestGenerateDevLog(unittest.TestCase):
    """Testes para o utilitário de log incremental de desenvolvimento."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temp_dir.name) / "desenvolvimento_projeto.txt"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_format_log_entry_canonical_structure(self) -> None:
        """Verifica se o bloco gerado obedece estritamente ao layout canônico."""
        ts_str = "2026-10-03 13:00:00 UTC"
        pedido = "Instrução inicial do usuário para teste."
        resposta = "Relatório detalhado do Antigravity com status de sucesso."

        block = format_log_entry(ts_str, pedido, resposta)

        self.assertIn("=" * 80, block)
        self.assertIn(f"[REGISTRO DE DESENVOLVIMENTO - {ts_str}]", block)
        self.assertIn("-" * 80, block)
        self.assertIn("PEDIDO (SENHOR SUPREMO):", block)
        self.assertIn(pedido, block)
        self.assertIn("RESPOSTA / RELATÓRIO DE EXECUÇÃO (ANTIGRAVITY):", block)
        self.assertIn(resposta, block)

    def test_append_first_entry_creates_file_with_header(self) -> None:
        """Testa a criação do arquivo com o cabeçalho superior UTC na primeira entrada."""
        dt1 = datetime(2026, 10, 3, 10, 0, 0, tzinfo=timezone.utc)
        out_path, ts = append_dev_log(
            pedido="Primeiro pedido de teste",
            resposta="Primeira resposta de teste",
            output_path=self.log_file,
            timestamp=dt1,
        )

        self.assertTrue(self.log_file.is_file())
        content = self.log_file.read_text(encoding="utf-8")

        self.assertIn("HISTÓRICO CONSOLIDADO DE DESENVOLVIMENTO DO PROJETO", content)
        self.assertIn("Última Atualização: 2026-10-03 10:00:00 UTC", content)
        self.assertIn("[REGISTRO DE DESENVOLVIMENTO - 2026-10-03 10:00:00 UTC]", content)
        self.assertIn("Primeiro pedido de teste", content)
        self.assertIn("Primeira resposta de teste", content)

    def test_incremental_prepend_and_history_preservation(self) -> None:
        """Testa se a segunda entrada é inserida no topo e se a primeira é preservada abaixo."""
        dt1 = datetime(2026, 10, 3, 10, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 10, 3, 11, 30, 0, tzinfo=timezone.utc)

        # 1ª entrada
        append_dev_log(
            pedido="Pedido Antigo (Passo 1)",
            resposta="Resposta Antiga (Passo 1)",
            output_path=self.log_file,
            timestamp=dt1,
        )

        # 2ª entrada (mais recente)
        append_dev_log(
            pedido="Pedido Novo (Passo 2)",
            resposta="Resposta Nova (Passo 2)",
            output_path=self.log_file,
            timestamp=dt2,
        )

        content = self.log_file.read_text(encoding="utf-8")

        # Cabeçalho atualizado para o horário mais recente
        self.assertIn("Última Atualização: 2026-10-03 11:30:00 UTC", content)

        # Ordem cronológica invertida: Passo 2 deve aparecer ANTES do Passo 1
        pos_passo_2 = content.find("Pedido Novo (Passo 2)")
        pos_passo_1 = content.find("Pedido Antigo (Passo 1)")

        self.assertNotEqual(pos_passo_2, -1)
        self.assertNotEqual(pos_passo_1, -1)
        self.assertLess(pos_passo_2, pos_passo_1, "O registro mais recente deve anteceder o registro antigo.")

        # Preservação integral das respostas
        self.assertIn("Resposta Nova (Passo 2)", content)
        self.assertIn("Resposta Antiga (Passo 1)", content)

    def test_extract_existing_history(self) -> None:
        """Testa o extrator de histórico ao remover cabeçalhos prévios."""
        raw_content = (
            HEADER_BANNER.format(timestamp_utc="2026-10-03 09:00:00 UTC")
            + "=" * 80 + "\n"
            "[REGISTRO DE DESENVOLVIMENTO - 2026-10-03 09:00:00 UTC]\n"
            "-" * 80 + "\n"
            "Conteúdo salvo\n"
            + "=" * 80 + "\n"
        )
        extracted = extract_existing_history(raw_content)
        self.assertNotIn("HISTÓRICO CONSOLIDADO DE DESENVOLVIMENTO DO PROJETO", extracted)
        self.assertIn("[REGISTRO DE DESENVOLVIMENTO - 2026-10-03 09:00:00 UTC]", extracted)
        self.assertIn("Conteúdo salvo", extracted)


if __name__ == "__main__":
    unittest.main()

